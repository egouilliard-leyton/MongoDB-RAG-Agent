"""Outcome tracking service for Q&A sessions and pairs."""

import logging
from typing import List, Optional
from datetime import datetime, timedelta
from bson import ObjectId

from src.services.qa_storage import QAStorageService
from src.settings import Settings

logger = logging.getLogger(__name__)


class OutcomeTracker:
    """Service for tracking and managing outcome statuses."""

    def __init__(self, settings: Settings):
        """
        Initialize outcome tracker.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.qa_storage: Optional[QAStorageService] = None

    async def _get_qa_storage(self) -> QAStorageService:
        """Get or create QAStorageService instance."""
        if not self.qa_storage:
            self.qa_storage = QAStorageService(self.settings)
            await self.qa_storage.initialize()
        return self.qa_storage

    async def check_auto_success(self, session_id: str) -> bool:
        """
        Check if a session should be auto-marked as successful.

        Args:
            session_id: Session ID

        Returns:
            True if session should be auto-marked as successful
        """
        qa_storage = await self._get_qa_storage()
        session = await qa_storage.get_session(session_id)

        # Check if already has outcome status
        if session.get("outcome_status") is not None:
            return False

        # Check if session was exported
        exported_at = session.get("exported_at")
        if not exported_at:
            return False

        # Check if enough days have passed
        if isinstance(exported_at, str):
            # Handle string datetime if needed
            try:
                exported_at = datetime.fromisoformat(exported_at.replace('Z', '+00:00'))
            except Exception:
                logger.warning(f"Could not parse exported_at for session {session_id}")
                return False

        days_since_export = (datetime.utcnow() - exported_at.replace(tzinfo=None)).days
        if days_since_export < self.settings.qa_auto_success_days:
            return False

        # Check if follow-up session exists
        has_follow_up = await self.check_follow_up_exists(session_id)
        if has_follow_up:
            return False

        return True

    async def mark_qa_pair_outcome(
        self, qa_pair_id: str, outcome: str
    ) -> None:
        """
        Mark outcome status for a Q&A pair.

        Args:
            qa_pair_id: Q&A pair ID
            outcome: Outcome status ("successful" or "unsuccessful")
        """
        if outcome not in ("successful", "unsuccessful"):
            raise ValueError(f"Invalid outcome status: {outcome}")

        qa_storage = await self._get_qa_storage()

        await qa_storage.db[qa_storage.settings.mongodb_collection_qa_pairs].update_one(
            {"_id": ObjectId(qa_pair_id)},
            {
                "$set": {
                    "outcome_status": outcome,
                    "updated_at": datetime.utcnow()
                }
            }
        )

        logger.info(f"Marked Q&A pair {qa_pair_id} outcome: {outcome}")

    async def mark_session_outcome(
        self, session_id: str, outcome: str, determined_by: str
    ) -> None:
        """
        Mark outcome status for a session.

        Args:
            session_id: Session ID
            outcome: Outcome status ("successful" or "unsuccessful")
            determined_by: Who determined the outcome ("user" or "auto")
        """
        qa_storage = await self._get_qa_storage()
        await qa_storage.mark_session_outcome(
            session_id=session_id,
            outcome=outcome,
            determined_by=determined_by
        )

    async def check_follow_up_exists(self, session_id: str) -> bool:
        """
        Check if a follow-up session exists for the given session.

        Args:
            session_id: Session ID

        Returns:
            True if follow-up session exists
        """
        qa_storage = await self._get_qa_storage()

        count = await qa_storage.db[qa_storage.settings.mongodb_collection_qa_sessions].count_documents(
            {"metadata.parent_session_id": session_id}
        )

        return count > 0

    async def get_sessions_for_auto_success_check(self) -> List[str]:
        """
        Get list of session IDs that should be checked for auto-success.

        Returns:
            List of session IDs
        """
        qa_storage = await self._get_qa_storage()

        # Calculate cutoff date
        cutoff_date = datetime.utcnow() - timedelta(days=self.settings.qa_auto_success_days)

        # Find sessions that:
        # - Have outcome_status == None
        # - Have exported_at set and older than cutoff_date
        # - Have no follow-up sessions
        query = {
            "outcome_status": None,
            "exported_at": {"$exists": True, "$lte": cutoff_date}
        }

        cursor = qa_storage.db[qa_storage.settings.mongodb_collection_qa_sessions].find(query)
        
        session_ids = []
        async for session in cursor:
            session_id = str(session["_id"])
            # Check if follow-up exists
            has_follow_up = await self.check_follow_up_exists(session_id)
            if not has_follow_up:
                session_ids.append(session_id)

        return session_ids

