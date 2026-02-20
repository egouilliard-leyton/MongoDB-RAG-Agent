"""Exemplar service for managing high-quality Q&A pairs.

This service handles the identification, promotion, and management of exemplar
Q&A pairs - those that meet high quality thresholds and can be used to improve
future RAG responses.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from bson import ObjectId
from pymongo import AsyncMongoClient

from src.settings import Settings

logger = logging.getLogger(__name__)


# Exemplar threshold criteria
EXEMPLAR_CONFIDENCE_THRESHOLD = 0.8
EXEMPLAR_MIN_CITATIONS = 2


def check_exemplar_eligibility(qa_pair: Dict[str, Any]) -> bool:
    """
    Check if a Q&A pair meets the criteria to become an exemplar.

    Criteria:
    - rating_good == True (consultant rated as good)
    - review.verdict == "good" (review agent verdict is good)
    - review.confidence >= 0.8 (high confidence score)
    - citations count >= 2 (sufficient source references)

    Args:
        qa_pair: Q&A pair dictionary from MongoDB

    Returns:
        True if the Q&A pair meets all exemplar criteria, False otherwise
    """
    # Check rating_good is explicitly True
    if qa_pair.get("rating_good") is not True:
        return False

    # Check review exists and has good verdict
    review = qa_pair.get("review")
    if not review:
        return False

    verdict = review.get("verdict")
    if verdict != "good":
        return False

    # Check confidence threshold
    confidence = review.get("confidence", 0)
    if confidence < EXEMPLAR_CONFIDENCE_THRESHOLD:
        return False

    # Check minimum citations
    citations = qa_pair.get("citations") or []
    if len(citations) < EXEMPLAR_MIN_CITATIONS:
        return False

    return True


class ExemplarService:
    """Service for managing exemplar Q&A pairs in MongoDB."""

    def __init__(self, settings: Settings):
        """
        Initialize exemplar service.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.mongo_client: Optional[AsyncMongoClient] = None
        self.db: Optional[Any] = None

    async def initialize(self) -> None:
        """Initialize MongoDB connection."""
        if not self.mongo_client:
            self.mongo_client = AsyncMongoClient(
                self.settings.mongodb_uri,
                serverSelectionTimeoutMS=5000
            )
            self.db = self.mongo_client[self.settings.mongodb_database]
            await self.mongo_client.admin.command("ping")
            logger.info("Exemplar service initialized")

    async def cleanup(self) -> None:
        """Clean up MongoDB connection."""
        if self.mongo_client:
            await self.mongo_client.close()
            self.mongo_client = None
            self.db = None
            logger.info("Exemplar service cleaned up")

    async def get_qa_pair(self, qa_pair_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a Q&A pair by ID.

        Args:
            qa_pair_id: Q&A pair ID

        Returns:
            Q&A pair document or None if not found
        """
        await self.initialize()

        qa_pair = await self.db[self.settings.mongodb_collection_qa_pairs].find_one(
            {"_id": ObjectId(qa_pair_id)}
        )

        if qa_pair:
            qa_pair["_id"] = str(qa_pair["_id"])
            if qa_pair.get("session_id"):
                qa_pair["session_id"] = str(qa_pair["session_id"])

        return qa_pair

    async def promote_to_exemplar(self, qa_pair_id: str) -> bool:
        """
        Promote a Q&A pair to exemplar status.

        This method:
        1. Fetches the Q&A pair
        2. Verifies it meets exemplar eligibility criteria
        3. Sets is_exemplar = True if eligible

        Args:
            qa_pair_id: Q&A pair ID

        Returns:
            True if promotion was successful, False otherwise

        Raises:
            ValueError: If qa_pair_id is invalid or Q&A pair not found
        """
        await self.initialize()

        # Fetch the Q&A pair
        qa_pair = await self.get_qa_pair(qa_pair_id)
        if not qa_pair:
            raise ValueError(f"Q&A pair not found: {qa_pair_id}")

        # Check if already an exemplar
        if qa_pair.get("is_exemplar") is True:
            logger.debug(f"Q&A pair {qa_pair_id} is already an exemplar")
            return True

        # Check eligibility
        if not check_exemplar_eligibility(qa_pair):
            logger.debug(
                f"Q&A pair {qa_pair_id} does not meet exemplar criteria: "
                f"rating_good={qa_pair.get('rating_good')}, "
                f"review={qa_pair.get('review')}, "
                f"citations_count={len(qa_pair.get('citations') or [])}"
            )
            return False

        # Promote to exemplar
        result = await self.db[self.settings.mongodb_collection_qa_pairs].update_one(
            {"_id": ObjectId(qa_pair_id)},
            {
                "$set": {
                    "is_exemplar": True,
                    "promoted_to_exemplar_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )

        if result.modified_count > 0:
            logger.info(f"Promoted Q&A pair {qa_pair_id} to exemplar status")
            return True

        return False

    async def demote_from_exemplar(self, qa_pair_id: str) -> bool:
        """
        Remove exemplar status from a Q&A pair.

        Args:
            qa_pair_id: Q&A pair ID

        Returns:
            True if demotion was successful, False otherwise

        Raises:
            ValueError: If qa_pair_id is invalid or Q&A pair not found
        """
        await self.initialize()

        result = await self.db[self.settings.mongodb_collection_qa_pairs].update_one(
            {"_id": ObjectId(qa_pair_id)},
            {
                "$set": {
                    "is_exemplar": False,
                    "updated_at": datetime.utcnow()
                },
                "$unset": {
                    "promoted_to_exemplar_at": ""
                }
            }
        )

        if result.matched_count == 0:
            raise ValueError(f"Q&A pair not found: {qa_pair_id}")

        if result.modified_count > 0:
            logger.info(f"Demoted Q&A pair {qa_pair_id} from exemplar status")
            return True

        return False

    async def check_and_promote_if_eligible(self, qa_pair_id: str) -> bool:
        """
        Check a Q&A pair's eligibility and promote if it meets criteria.

        This is a convenience method that combines eligibility check and promotion.
        It's designed to be called after rating updates or other changes.

        Args:
            qa_pair_id: Q&A pair ID

        Returns:
            True if the Q&A pair was promoted (or already an exemplar), False otherwise
        """
        try:
            return await self.promote_to_exemplar(qa_pair_id)
        except ValueError as e:
            logger.warning(f"Failed to check/promote exemplar: {e}")
            return False

    async def get_exemplars(
        self,
        limit: int = 100,
        skip: int = 0,
        session_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve exemplar Q&A pairs.

        Args:
            limit: Maximum number of exemplars to return
            skip: Number of exemplars to skip
            session_id: Optional session ID to filter exemplars

        Returns:
            List of exemplar Q&A pair documents
        """
        await self.initialize()

        query: Dict[str, Any] = {"is_exemplar": True}
        if session_id:
            query["session_id"] = ObjectId(session_id)

        cursor = self.db[self.settings.mongodb_collection_qa_pairs].find(query).sort(
            "promoted_to_exemplar_at", -1
        ).skip(skip).limit(limit)

        exemplars = []
        async for exemplar in cursor:
            exemplar["_id"] = str(exemplar["_id"])
            if exemplar.get("session_id"):
                exemplar["session_id"] = str(exemplar["session_id"])
            exemplars.append(exemplar)

        return exemplars

    async def count_exemplars(self, session_id: Optional[str] = None) -> int:
        """
        Count the number of exemplar Q&A pairs.

        Args:
            session_id: Optional session ID to filter count

        Returns:
            Count of exemplar Q&A pairs
        """
        await self.initialize()

        query: Dict[str, Any] = {"is_exemplar": True}
        if session_id:
            query["session_id"] = ObjectId(session_id)

        return await self.db[self.settings.mongodb_collection_qa_pairs].count_documents(query)
