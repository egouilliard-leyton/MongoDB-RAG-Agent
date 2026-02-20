"""Project storage service for managing projects and their stage tracking."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId
from pymongo import AsyncMongoClient

from src.settings import Settings
from src.services.project_stages import is_valid_stage_key, allowed_transitions

logger = logging.getLogger(__name__)


class ProjectStorageService:
    """Service for managing projects in MongoDB."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.mongo_client: Optional[AsyncMongoClient] = None
        self.db: Optional[Any] = None

    @property
    def collection_name(self) -> str:
        return "projects"

    async def initialize(self) -> None:
        if not self.mongo_client:
            self.mongo_client = AsyncMongoClient(
                self.settings.mongodb_uri, serverSelectionTimeoutMS=5000
            )
            self.db = self.mongo_client[self.settings.mongodb_database]
            await self.mongo_client.admin.command("ping")
            logger.info("Project storage service initialized")

    async def cleanup(self) -> None:
        if self.mongo_client:
            await self.mongo_client.close()
            self.mongo_client = None
            self.db = None
            logger.info("Project storage service cleaned up")

    def _project_to_api(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        doc = dict(doc)
        doc["_id"] = str(doc["_id"])
        # Normalize stage timestamp if present
        if isinstance(doc.get("stage"), dict):
            if isinstance(doc["stage"].get("updated_at"), datetime):
                doc["stage"]["updated_at"] = doc["stage"]["updated_at"]
        return doc

    async def create_project(
        self,
        name: str,
        company_info: Optional[Dict[str, Any]] = None,
        initial_stage: str = "prep_docs",
        created_by: Optional[str] = None,
        tax_office_id: Optional[int] = None,
        region: Optional[str] = None,
        industry: Optional[str] = None,
    ) -> str:
        """
        Create a new project.

        Args:
            name: Project name.
            company_info: Optional company information payload.
            initial_stage: Initial project stage key.
            created_by: User who created the project.
            tax_office_id: Optional tax office ID (kodjednostki).
            region: Optional region (voivodeship) name.
            industry: Optional industry classification.

        Returns:
            String representation of the created project's ObjectId.
        """
        await self.initialize()

        if not is_valid_stage_key(initial_stage):
            raise ValueError(f"Invalid initial_stage: {initial_stage}")

        now = datetime.utcnow()
        project_doc: Dict[str, Any] = {
            "name": name,
            "company_info": company_info or {},
            "tax_office_id": tax_office_id,
            "region": region,
            "industry": industry,
            "created_at": now,
            "updated_at": now,
            "stage": {"key": initial_stage, "updated_at": now},
            "stage_history": [
                {
                    "at": now,
                    "from": None,
                    "to": initial_stage,
                    "event": "create",
                    "note": None,
                    "by": created_by,
                }
            ],
        }

        result = await self.db[self.collection_name].insert_one(project_doc)
        return str(result.inserted_id)

    async def list_projects(self, limit: int = 200) -> List[Dict[str, Any]]:
        await self.initialize()
        cursor = self.db[self.collection_name].find().sort("created_at", -1).limit(limit)
        projects: List[Dict[str, Any]] = []
        async for p in cursor:
            projects.append(self._project_to_api(p))
        return projects

    async def get_project(self, project_id: str) -> Dict[str, Any]:
        await self.initialize()
        doc = await self.db[self.collection_name].find_one({"_id": ObjectId(project_id)})
        if not doc:
            raise ValueError(f"Project not found: {project_id}")
        return self._project_to_api(doc)

    async def set_stage(
        self,
        project_id: str,
        to_stage: str,
        event: str,
        note: Optional[str] = None,
        by: Optional[str] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Update project stage.

        - If force=False: event must be valid from current stage (per transition table).
        - If force=True: any stage key is allowed (must still be a known stage).
        """
        await self.initialize()

        if not is_valid_stage_key(to_stage):
            raise ValueError(f"Unknown to_stage: {to_stage}")

        project = await self.db[self.collection_name].find_one(
            {"_id": ObjectId(project_id)}
        )
        if not project:
            raise ValueError(f"Project not found: {project_id}")

        current_stage = (project.get("stage") or {}).get("key") or "prep_docs"
        if not is_valid_stage_key(current_stage):
            current_stage = "prep_docs"

        if not force:
            allowed = allowed_transitions(current_stage)
            ok = any(a["event"] == event and a["to"] == to_stage for a in allowed)
            if not ok:
                raise ValueError(
                    f"Transition not allowed: {current_stage} --({event})-> {to_stage}"
                )

        now = datetime.utcnow()
        stage_history_entry = {
            "at": now,
            "from": current_stage,
            "to": to_stage,
            "event": event,
            "note": note,
            "by": by,
        }

        await self.db[self.collection_name].update_one(
            {"_id": ObjectId(project_id)},
            {
                "$set": {
                    "updated_at": now,
                    "stage": {"key": to_stage, "updated_at": now},
                },
                "$push": {"stage_history": stage_history_entry},
            },
        )

        return await self.get_project(project_id)

    async def get_stage_options(self, project_id: str) -> Dict[str, Any]:
        """Convenience helper for UI: allowed next + rollback stages."""
        project = await self.get_project(project_id)
        current_stage = (project.get("stage") or {}).get("key") or "prep_docs"
        next_actions = allowed_transitions(current_stage)

        history = project.get("stage_history") or []
        visited = []
        for h in history:
            to = h.get("to")
            if to and to not in visited:
                visited.append(to)
        rollback_targets = list(reversed(visited[:-1]))  # exclude current

        return {"next_actions": next_actions, "rollback_targets": rollback_targets}


