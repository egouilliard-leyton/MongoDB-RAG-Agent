"""Q&A storage service for managing sessions and Q&A pairs."""

import logging
from typing import Optional, Dict, List, Any
from datetime import datetime
from bson import ObjectId
from pymongo import AsyncMongoClient
from pymongo.errors import OperationFailure

from src.settings import Settings
from src.dependencies import AgentDependencies

logger = logging.getLogger(__name__)


class QAStorageService:
    """Service for managing Q&A sessions and pairs in MongoDB."""

    def __init__(self, settings: Settings):
        """
        Initialize Q&A storage service.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.mongo_client: Optional[AsyncMongoClient] = None
        self.db: Optional[Any] = None
        self._embedding_deps: Optional[AgentDependencies] = None

    async def initialize(self) -> None:
        """Initialize MongoDB connection."""
        if not self.mongo_client:
            self.mongo_client = AsyncMongoClient(
                self.settings.mongodb_uri,
                serverSelectionTimeoutMS=5000
            )
            self.db = self.mongo_client[self.settings.mongodb_database]
            await self.mongo_client.admin.command("ping")
            logger.info("Q&A storage service initialized")

    async def cleanup(self) -> None:
        """Clean up MongoDB connection."""
        if self.mongo_client:
            await self.mongo_client.close()
            self.mongo_client = None
            self.db = None
            logger.info("Q&A storage service cleaned up")

    async def _get_embedding_deps(self) -> AgentDependencies:
        """Get or create AgentDependencies for embedding generation."""
        if not self._embedding_deps:
            self._embedding_deps = AgentDependencies()
            await self._embedding_deps.initialize()
        return self._embedding_deps

    async def create_session(
        self,
        name: str,
        user_role: str,
        company_info: Optional[Dict[str, Any]] = None,
        project_id: Optional[str] = None,
        tax_office_id: Optional[int] = None,
        region: Optional[str] = None,
    ) -> str:
        """
        Create a new Q&A session.

        Args:
            name: Session name
            user_role: User role ("junior" or "senior")
            company_info: Optional company information dictionary
            project_id: Optional project ID to scope the session
            tax_office_id: Optional tax office ID (kodjednostki)
            region: Optional region (voivodeship)

        Returns:
            Session ID as string
        """
        await self.initialize()

        project_oid: Optional[ObjectId] = None
        if project_id:
            try:
                project_oid = ObjectId(project_id)
            except Exception:
                # Keep it unset if invalid; API layer also validates.
                project_oid = None

        session_doc = {
            "session_name": name,
            "user_role": user_role,
            "status": "active",
            "outcome_status": None,
            "project_id": project_oid,
            "tax_office_id": tax_office_id,
            "region": region,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "metadata": {
                "company_info": company_info or {},
                "round_number": 1,
                "parent_session_id": None
            }
        }

        result = await self.db[self.settings.mongodb_collection_qa_sessions].insert_one(session_doc)
        session_id = str(result.inserted_id)
        logger.info(f"Created Q&A session: {session_id} ({name})")
        return session_id

    async def get_session(self, session_id: str) -> Dict[str, Any]:
        """
        Retrieve a session by ID.

        Args:
            session_id: Session ID

        Returns:
            Session document as dictionary

        Raises:
            ValueError: If session not found
        """
        await self.initialize()

        session = await self.db[self.settings.mongodb_collection_qa_sessions].find_one(
            {"_id": ObjectId(session_id)}
        )

        if not session:
            raise ValueError(f"Session not found: {session_id}")

        # Convert ObjectId to string
        session["_id"] = str(session["_id"])
        if session.get("project_id") is not None:
            session["project_id"] = str(session["project_id"])
        return session

    async def list_sessions(self, limit: int = 100, skip: int = 0) -> List[Dict[str, Any]]:
        """
        List Q&A sessions ordered by created_at descending.

        Args:
            limit: Maximum number of sessions to return
            skip: Number of sessions to skip

        Returns:
            List of session documents
        """
        await self.initialize()

        cursor = self.db[self.settings.mongodb_collection_qa_sessions].find().sort(
            "created_at", -1
        ).skip(skip).limit(limit)

        sessions = []
        async for session in cursor:
            session["_id"] = str(session["_id"])
            if session.get("project_id") is not None:
                session["project_id"] = str(session["project_id"])
            sessions.append(session)

        return sessions

    async def save_qa_pair(
        self,
        session_id: str,
        question: str,
        answer: str,
        citations: List[Dict[str, Any]],
        question_index: int,
        user_role: str,
        review: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Save a Q&A pair.

        Args:
            session_id: Session ID
            question: Question text
            answer: Answer text
            citations: List of citation dictionaries
            question_index: Index of question within session
            user_role: User role ("junior" or "senior")

        Returns:
            Q&A pair ID as string, or None for junior users
        """
        # Junior users don't save Q&A pairs
        if user_role == "junior":
            return None

        await self.initialize()

        # Generate question embedding
        embedding_deps = await self._get_embedding_deps()
        question_embedding = await embedding_deps.get_embedding(question)

        qa_pair_doc = {
            "session_id": ObjectId(session_id),
            "question": question,
            "original_answer": answer,
            "edited_answer": None,
            "final_answer": answer,
            # Feedback / review
            "rating_good": None,  # null = not reviewed
            "rated_at": None,
            "rated_by": None,
            # Editing audit
            "was_edited": False,
            "edited_at": None,
            # Review agent output (optional)
            "review": review,
            "citations": citations,
            "question_embedding": question_embedding,
            "question_index": question_index,
            "outcome_status": None,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        result = await self.db[self.settings.mongodb_collection_qa_pairs].insert_one(qa_pair_doc)
        qa_pair_id = str(result.inserted_id)

        # Update session updated_at
        await self.db[self.settings.mongodb_collection_qa_sessions].update_one(
            {"_id": ObjectId(session_id)},
            {"$set": {"updated_at": datetime.utcnow()}}
        )

        logger.info(f"Saved Q&A pair: {qa_pair_id} (session: {session_id}, index: {question_index})")
        return qa_pair_id

    async def update_answer(self, qa_pair_id: str, edited_answer: str) -> None:
        """
        Update the edited answer and final answer for a Q&A pair.

        Args:
            qa_pair_id: Q&A pair ID
            edited_answer: Edited answer text
        """
        await self.initialize()

        await self.db[self.settings.mongodb_collection_qa_pairs].update_one(
            {"_id": ObjectId(qa_pair_id)},
            {
                "$set": {
                    "edited_answer": edited_answer,
                    "final_answer": edited_answer,
                    "was_edited": True,
                    "edited_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )

        logger.info(f"Updated Q&A pair answer: {qa_pair_id}")

    async def update_rating(
        self,
        qa_pair_id: str,
        rating_good: Optional[bool],
        rated_by: Optional[str] = None
    ) -> None:
        """
        Update consultant rating for a Q&A pair.

        Args:
            qa_pair_id: Q&A pair ID
            rating_good: true=good, false=bad, None=clear/unreviewed
            rated_by: Optional identifier for who rated
        """
        await self.initialize()

        now = datetime.utcnow()
        set_doc: Dict[str, Any] = {
            "rating_good": rating_good,
            "updated_at": now,
        }

        if rating_good is None:
            set_doc["rated_at"] = None
            set_doc["rated_by"] = None
        else:
            set_doc["rated_at"] = now
            if rated_by is not None:
                set_doc["rated_by"] = rated_by

        await self.db[self.settings.mongodb_collection_qa_pairs].update_one(
            {"_id": ObjectId(qa_pair_id)},
            {"$set": set_doc}
        )

        logger.info(f"Updated Q&A pair rating: {qa_pair_id} -> {rating_good}")

    async def get_session_qa_pairs(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get all Q&A pairs for a session, ordered by question_index.

        Args:
            session_id: Session ID

        Returns:
            List of Q&A pair documents
        """
        await self.initialize()

        cursor = self.db[self.settings.mongodb_collection_qa_pairs].find(
            {"session_id": ObjectId(session_id)}
        ).sort("question_index", 1)

        qa_pairs = []
        async for pair in cursor:
            pair["_id"] = str(pair["_id"])
            pair["session_id"] = str(pair["session_id"])
            qa_pairs.append(pair)

        return qa_pairs

    async def generate_question_embedding(self, question: str) -> List[float]:
        """
        Generate embedding for a question.

        Args:
            question: Question text

        Returns:
            Embedding vector as list of floats
        """
        embedding_deps = await self._get_embedding_deps()
        return await embedding_deps.get_embedding(question)

    def _create_qa_summary(self, qa_pairs: List[Dict[str, Any]]) -> str:
        """
        Create a concise summary of Q&A pairs for inclusion in follow-up session metadata.

        Args:
            qa_pairs: List of Q&A pair dictionaries

        Returns:
            Formatted summary string
        """
        if not qa_pairs:
            return "No previous Q&A pairs."

        summary_parts = [
            f"Previous Round Summary: {len(qa_pairs)} Q&A pair(s)",
            ""
        ]

        # Count outcomes
        successful_count = sum(1 for qa in qa_pairs if qa.get("outcome_status") == "successful")
        unsuccessful_count = sum(1 for qa in qa_pairs if qa.get("outcome_status") == "unsuccessful")
        pending_count = len(qa_pairs) - successful_count - unsuccessful_count

        summary_parts.append(f"Outcome Status: {successful_count} successful, {unsuccessful_count} unsuccessful, {pending_count} pending")
        summary_parts.append("")

        # List questions with brief context
        summary_parts.append("Questions from previous round:")
        for i, qa_pair in enumerate(qa_pairs[:10], 1):  # Limit to first 10
            question = qa_pair.get("question", "Unknown question")
            outcome = qa_pair.get("outcome_status", "pending")
            summary_parts.append(f"{i}. {question[:100]}{'...' if len(question) > 100 else ''} [{outcome}]")

        if len(qa_pairs) > 10:
            summary_parts.append(f"... and {len(qa_pairs) - 10} more question(s)")

        return "\n".join(summary_parts)

    async def create_follow_up_session(
        self,
        parent_session_id: str,
        new_questions: List[str],
        user_role: str
    ) -> str:
        """
        Create a follow-up session with incremented round number.

        Args:
            parent_session_id: Parent session ID
            new_questions: List of new questions for follow-up
            user_role: User role

        Returns:
            New session ID as string
        """
        await self.initialize()

        # Get parent session to determine round number
        parent_session = await self.get_session(parent_session_id)
        parent_round = parent_session.get("metadata", {}).get("round_number", 1)
        new_round = parent_round + 1

        # Get parent session name and inherited fields
        parent_name = parent_session.get("session_name", "Unknown")
        project_id = parent_session.get("project_id")
        tax_office_id = parent_session.get("tax_office_id")
        region = parent_session.get("region")

        # Fetch previous Q&A pairs from parent session
        previous_qa_pairs = await self.get_session_qa_pairs(parent_session_id)

        # Create summary of previous round
        previous_summary = self._create_qa_summary(previous_qa_pairs)

        # Create follow-up session
        session_doc = {
            "session_name": f"{parent_name} (Round {new_round})",
            "user_role": user_role,
            "status": "active",
            "outcome_status": None,
            "project_id": ObjectId(project_id) if project_id else None,
            "tax_office_id": tax_office_id,
            "region": region,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "metadata": {
                "company_info": parent_session.get("metadata", {}).get("company_info", {}),
                "round_number": new_round,
                "parent_session_id": parent_session_id,
                "previous_qa_summary": previous_summary,
                "previous_qa_pairs_count": len(previous_qa_pairs)
            }
        }

        result = await self.db[self.settings.mongodb_collection_qa_sessions].insert_one(session_doc)
        new_session_id = str(result.inserted_id)

        logger.info(
            f"Created follow-up session: {new_session_id} "
            f"(parent: {parent_session_id}, round: {new_round})"
        )

        return new_session_id

    async def update_review(self, qa_pair_id: str, review: Optional[Dict[str, Any]]) -> None:
        """Persist review agent output for a Q&A pair."""
        await self.initialize()
        await self.db[self.settings.mongodb_collection_qa_pairs].update_one(
            {"_id": ObjectId(qa_pair_id)},
            {
                "$set": {
                    "review": review,
                    "updated_at": datetime.utcnow(),
                }
            },
        )

    async def update_session_review_summary(self, session_id: str, review_summary: Dict[str, Any]) -> None:
        """Persist session-level review summary under metadata.review_summary."""
        await self.initialize()
        await self.db[self.settings.mongodb_collection_qa_sessions].update_one(
            {"_id": ObjectId(session_id)},
            {
                "$set": {
                    "metadata.review_summary": review_summary,
                    "updated_at": datetime.utcnow(),
                }
            },
        )

    async def mark_session_outcome(
        self,
        session_id: str,
        outcome: str,
        determined_by: str
    ) -> None:
        """
        Mark session outcome status.

        Args:
            session_id: Session ID
            outcome: Outcome status ("successful" or "unsuccessful")
            determined_by: Who determined the outcome ("user" or "auto")
        """
        await self.initialize()

        update_doc = {
            "outcome_status": outcome,
            "updated_at": datetime.utcnow()
        }

        if determined_by == "user":
            update_doc["metadata.determined_by"] = "user"
        elif determined_by == "auto":
            update_doc["metadata.determined_by"] = "auto"

        await self.db[self.settings.mongodb_collection_qa_sessions].update_one(
            {"_id": ObjectId(session_id)},
            {"$set": update_doc}
        )

        logger.info(f"Marked session outcome: {session_id} -> {outcome} (by {determined_by})")

    async def get_parent_session_qa_pairs(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get Q&A pairs from the parent session of a follow-up session.

        Args:
            session_id: Current session ID (follow-up session)

        Returns:
            List of Q&A pair dictionaries from parent session
        """
        await self.initialize()

        # Get current session to find parent
        session = await self.get_session(session_id)
        parent_session_id = session.get("metadata", {}).get("parent_session_id")

        if not parent_session_id:
            logger.debug(f"Session {session_id} has no parent session")
            return []

        # Fetch Q&A pairs from parent session
        parent_qa_pairs = await self.get_session_qa_pairs(parent_session_id)

        logger.info(
            f"Retrieved {len(parent_qa_pairs)} Q&A pairs from parent session "
            f"{parent_session_id} for follow-up session {session_id}"
        )

        return parent_qa_pairs

    async def set_outcome(self, qa_pair_id: str, outcome_status: str) -> None:
        """
        Set the outcome status for a Q&A pair.

        Args:
            qa_pair_id: Q&A pair ID
            outcome_status: Outcome status ('successful', 'partial', or 'negative')

        Raises:
            ValueError: If qa_pair_id is invalid or Q&A pair not found
        """
        await self.initialize()

        result = await self.db[self.settings.mongodb_collection_qa_pairs].update_one(
            {"_id": ObjectId(qa_pair_id)},
            {
                "$set": {
                    "outcome_status": outcome_status,
                    "updated_at": datetime.utcnow()
                }
            }
        )

        if result.matched_count == 0:
            raise ValueError(f"Q&A pair not found: {qa_pair_id}")

        logger.info(f"Set Q&A pair outcome: {qa_pair_id} -> {outcome_status}")

