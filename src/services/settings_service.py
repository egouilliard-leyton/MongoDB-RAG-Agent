"""Settings service for managing application configuration in MongoDB."""

import logging
import time
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from pymongo import AsyncMongoClient

from src.settings import Settings

logger = logging.getLogger(__name__)

# Fields that belong to GlobalSettings (stored in MongoDB)
SETTINGS_FIELDS = [
    "main_system_prompt",
    "follow_up_context_prompt",
    "qa_history_prompt",
    "stage_defaults",
    "default_match_count",
    "max_match_count",
    "enable_question_decomposition",
    "enable_iterative_refinement",
    "enable_qa_history_search",
    "rrf_k_constant",
    "qa_history_match_count",
    "llm_model",
    "llm_base_url",
    "embedding_model",
    "show_full_citations",
]


class SettingsService:
    """Service for managing application settings with version history in MongoDB."""

    def __init__(self, settings: Settings) -> None:
        """
        Initialize settings service.

        Args:
            settings: Application settings (env-based).
        """
        self.settings = settings
        self.mongo_client: Optional[AsyncMongoClient] = None
        self.db: Optional[Any] = None

    async def initialize(self) -> None:
        """Initialize MongoDB connection."""
        if not self.mongo_client:
            self.mongo_client = AsyncMongoClient(
                self.settings.mongodb_uri,
                serverSelectionTimeoutMS=5000,
            )
            self.db = self.mongo_client[self.settings.mongodb_database]
            await self.mongo_client.admin.command("ping")
            logger.info("Settings service initialized")

    async def cleanup(self) -> None:
        """Clean up MongoDB connection."""
        if self.mongo_client:
            await self.mongo_client.close()
            self.mongo_client = None
            self.db = None
            logger.info("Settings service cleaned up")

    @property
    def _collection(self) -> Any:
        """Get the app_settings collection."""
        return self.db[self.settings.mongodb_collection_app_settings]

    async def get_current(self) -> Dict[str, Any]:
        """
        Get the current active settings.

        Seeds from environment on first call if no config exists.

        Returns:
            Settings document as dictionary.
        """
        await self.initialize()

        doc = await self._collection.find_one({"type": "global_config"})
        if not doc:
            doc = await self._seed_from_env()

        doc["_id"] = str(doc["_id"])
        return doc

    async def update(self, changes: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update settings with partial changes.

        Archives the current config as a version document, increments version,
        and writes the new config.

        Args:
            changes: Dictionary of field names to new values.

        Returns:
            Updated settings document.
        """
        await self.initialize()

        current = await self._collection.find_one({"type": "global_config"})
        if not current:
            current = await self._seed_from_env()

        old_version = current.get("version", 1)
        new_version = old_version + 1

        # Determine which fields actually changed
        changed_fields = []
        for key, value in changes.items():
            if key in SETTINGS_FIELDS:
                old_val = current.get(key)
                # For nested dicts, compare after serialization
                if key == "stage_defaults" and isinstance(value, dict):
                    if value != old_val:
                        changed_fields.append(key)
                elif value != old_val:
                    changed_fields.append(key)

        if not changed_fields:
            # No actual changes; return current
            current["_id"] = str(current["_id"])
            return current

        # Archive current as a version document
        snapshot = {k: current[k] for k in SETTINGS_FIELDS if k in current}
        summary = "Updated " + ", ".join(changed_fields[:5])
        if len(changed_fields) > 5:
            summary += f" (+{len(changed_fields) - 5} more)"

        version_doc = {
            "type": "version",
            "version": old_version,
            "snapshot": snapshot,
            "changed_fields": changed_fields,
            "summary": summary[:200],
            "created_at": datetime.utcnow(),
        }
        await self._collection.insert_one(version_doc)

        # Apply changes to current config
        update_fields: Dict[str, Any] = {
            "version": new_version,
            "updated_at": datetime.utcnow(),
        }
        for key in changed_fields:
            update_fields[key] = changes[key]

        await self._collection.update_one(
            {"type": "global_config"},
            {"$set": update_fields},
        )

        # Return updated doc
        updated = await self._collection.find_one({"type": "global_config"})
        updated["_id"] = str(updated["_id"])
        return updated

    async def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get settings version history.

        Args:
            limit: Maximum number of versions to return.

        Returns:
            List of version documents, newest first.
        """
        await self.initialize()

        cursor = (
            self._collection.find({"type": "version"})
            .sort("version", -1)
            .limit(limit)
        )

        versions: List[Dict[str, Any]] = []
        async for doc in cursor:
            versions.append({
                "version": doc["version"],
                "changed_fields": doc.get("changed_fields", []),
                "summary": doc.get("summary", ""),
                "created_at": doc["created_at"],
            })

        return versions

    async def restore(self, version: int) -> Dict[str, Any]:
        """
        Restore a historical version as the new active config.

        Args:
            version: Version number to restore.

        Returns:
            Updated settings document.

        Raises:
            ValueError: If version not found.
        """
        await self.initialize()

        version_doc = await self._collection.find_one({
            "type": "version",
            "version": version,
        })

        if not version_doc:
            raise ValueError(f"Version {version} not found")

        snapshot = version_doc["snapshot"]

        # Use update() to properly archive and increment version
        return await self.update(snapshot)

    async def test_prompt(self, prompt: str, test_question: str) -> Dict[str, Any]:
        """
        Test a prompt against a sample question using the LLM.

        Args:
            prompt: System prompt to test.
            test_question: Question to answer.

        Returns:
            Dict with 'answer' and 'latency_ms'.
        """
        from pydantic_ai import Agent
        from src.providers import get_llm_model

        start = time.time()
        try:
            llm = get_llm_model()
            test_agent = Agent(llm, system_prompt=prompt)
            result = await test_agent.run(test_question)
            answer = str(result.output) if hasattr(result, "output") else str(result)
        except Exception as e:
            logger.warning(f"Prompt test failed: {e}")
            answer = f"Error: {str(e)}"

        latency_ms = int((time.time() - start) * 1000)
        return {"answer": answer, "latency_ms": latency_ms}

    async def get_suggestions(self) -> List[Dict[str, Any]]:
        """
        Analyze Q&A history and generate parameter tuning suggestions.

        Returns:
            List of suggestion dictionaries. Empty if insufficient data.
        """
        await self.initialize()

        current = await self._collection.find_one({"type": "global_config"})
        if not current:
            return []

        # Query last 30 days of rated Q&A pairs
        cutoff = datetime.utcnow() - timedelta(days=30)
        qa_collection = self.db[self.settings.mongodb_collection_qa_pairs]

        rated_pairs = await qa_collection.count_documents({
            "rating_good": {"$ne": None},
            "created_at": {"$gte": cutoff},
        })

        if rated_pairs < 5:
            return []

        # Count bad ratings
        bad_count = await qa_collection.count_documents({
            "rating_good": False,
            "created_at": {"$gte": cutoff},
        })

        suggestions: List[Dict[str, Any]] = []

        # Suggest increasing match_count if bad ratio is high
        if rated_pairs > 0 and bad_count / rated_pairs > 0.3:
            current_mc = current.get("default_match_count", 10)
            if current_mc < 20:
                suggestions.append({
                    "suggestion_id": "increase_match_count",
                    "parameter": "default_match_count",
                    "current_value": current_mc,
                    "suggested_value": min(current_mc + 5, 50),
                    "confidence": round(min(bad_count / rated_pairs, 0.95), 2),
                    "rationale": (
                        f"{bad_count}/{rated_pairs} answers rated poorly. "
                        "Increasing search results may improve coverage."
                    ),
                })

        # Suggest enabling QA history if disabled and there are successful pairs
        if not current.get("enable_qa_history_search", True):
            successful = await qa_collection.count_documents({
                "outcome_status": "successful",
                "created_at": {"$gte": cutoff},
            })
            if successful > 10:
                suggestions.append({
                    "suggestion_id": "enable_qa_history",
                    "parameter": "enable_qa_history_search",
                    "current_value": False,
                    "suggested_value": True,
                    "confidence": 0.8,
                    "rationale": (
                        f"{successful} successful Q&A pairs available. "
                        "Enabling history search could improve answer quality."
                    ),
                })

        return suggestions

    async def apply_suggestion(self, suggestion_id: str) -> Dict[str, Any]:
        """
        Apply a suggestion by regenerating it and applying the change.

        Args:
            suggestion_id: Suggestion identifier.

        Returns:
            Updated settings document.

        Raises:
            ValueError: If suggestion not found or expired.
        """
        suggestions = await self.get_suggestions()
        match = next((s for s in suggestions if s["suggestion_id"] == suggestion_id), None)

        if not match:
            raise ValueError(f"Suggestion '{suggestion_id}' not found or expired")

        return await self.update({match["parameter"]: match["suggested_value"]})

    async def _seed_from_env(self) -> Dict[str, Any]:
        """
        Build and insert default settings from env values and prompt constants.

        Returns:
            The inserted document.
        """
        from src.prompts import MAIN_SYSTEM_PROMPT, FOLLOW_UP_CONTEXT_PROMPT, QA_HISTORY_PROMPT

        now = datetime.utcnow()
        default_doc = {
            "type": "global_config",
            "version": 1,
            "main_system_prompt": MAIN_SYSTEM_PROMPT,
            "follow_up_context_prompt": FOLLOW_UP_CONTEXT_PROMPT,
            "qa_history_prompt": QA_HISTORY_PROMPT,
            "stage_defaults": {
                "system_prompt_append": None,
                "search_params": {
                    "match_count": None,
                    "rrf_k": None,
                    "qa_history_match_count": None,
                },
            },
            "default_match_count": self.settings.default_match_count,
            "max_match_count": self.settings.max_match_count,
            "enable_question_decomposition": self.settings.enable_question_decomposition,
            "enable_iterative_refinement": self.settings.enable_iterative_refinement,
            "enable_qa_history_search": True,
            "rrf_k_constant": 60,
            "qa_history_match_count": 3,
            "llm_model": self.settings.llm_model,
            "llm_base_url": self.settings.llm_base_url or "https://openrouter.ai/api/v1",
            "embedding_model": self.settings.embedding_model,
            "show_full_citations": self.settings.show_full_citations,
            "created_at": now,
            "updated_at": now,
        }

        result = await self._collection.insert_one(default_doc)
        default_doc["_id"] = result.inserted_id

        # Also insert initial version
        snapshot = {k: default_doc[k] for k in SETTINGS_FIELDS if k in default_doc}
        version_doc = {
            "type": "version",
            "version": 1,
            "snapshot": snapshot,
            "changed_fields": [],
            "summary": "Initial seed from environment",
            "created_at": now,
        }
        await self._collection.insert_one(version_doc)

        logger.info("Seeded app_settings from environment and prompt constants")
        return default_doc
