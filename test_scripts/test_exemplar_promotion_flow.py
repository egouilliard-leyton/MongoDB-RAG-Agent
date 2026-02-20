"""Integration tests for exemplar promotion flow end-to-end.

Tests the complete flow from rating a Q&A pair to automatic exemplar promotion.
This covers the integration between:
- src/api/routes/qa_pairs.py (rating endpoint)
- src/services/exemplar_service.py (promotion logic)
- src/services/qa_storage.py (storage operations)

Uses httpx.AsyncClient with ASGITransport for async testing.
"""

import pytest
from datetime import datetime
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from bson import ObjectId

from src.api.routes.qa_pairs import router
from src.api.middleware import error_handler_middleware
from src.services.exemplar_service import (
    ExemplarService,
    check_exemplar_eligibility,
    EXEMPLAR_CONFIDENCE_THRESHOLD,
    EXEMPLAR_MIN_CITATIONS,
)


# Create test app with just the qa_pairs router
test_app = FastAPI()
test_app.middleware("http")(error_handler_middleware)
test_app.include_router(router)


def create_test_client() -> AsyncClient:
    """Create an AsyncClient with ASGITransport for testing."""
    transport = ASGITransport(app=test_app)
    return AsyncClient(transport=transport, base_url="http://test")


class TestExemplarPromotionFlowEndToEnd:
    """End-to-end tests for exemplar promotion via rating update."""

    @pytest.fixture
    def eligible_qa_pair(self) -> Dict[str, Any]:
        """Create a Q&A pair that meets all exemplar criteria."""
        return {
            "_id": "507f1f77bcf86cd799439011",
            "session_id": "507f1f77bcf86cd799439012",
            "question": "What are the R&D tax relief criteria?",
            "original_answer": "Original answer text...",
            "final_answer": "The R&D tax relief criteria include...",
            "rating_good": True,
            "review": {
                "verdict": "good",
                "confidence": 0.9,  # >= 0.8 threshold
                "feedback": "Well sourced and accurate"
            },
            "citations": [
                {"id": 1, "source": "doc1.pdf", "chunk_id": "chunk1"},
                {"id": 2, "source": "doc2.pdf", "chunk_id": "chunk2"},
                {"id": 3, "source": "doc3.pdf", "chunk_id": "chunk3"}
            ],  # >= 2 citations
            "is_exemplar": False,
            "question_index": 0,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

    @pytest.fixture
    def ineligible_qa_pair_low_confidence(self) -> Dict[str, Any]:
        """Create a Q&A pair with confidence below threshold."""
        return {
            "_id": "507f1f77bcf86cd799439021",
            "session_id": "507f1f77bcf86cd799439012",
            "question": "Another question?",
            "final_answer": "Answer text...",
            "rating_good": True,
            "review": {
                "verdict": "good",
                "confidence": 0.7,  # Below 0.8 threshold
            },
            "citations": [
                {"id": 1, "source": "doc1.pdf"},
                {"id": 2, "source": "doc2.pdf"}
            ],
            "is_exemplar": False,
            "question_index": 0
        }

    @pytest.fixture
    def ineligible_qa_pair_few_citations(self) -> Dict[str, Any]:
        """Create a Q&A pair with fewer than minimum citations."""
        return {
            "_id": "507f1f77bcf86cd799439031",
            "session_id": "507f1f77bcf86cd799439012",
            "question": "Question with one citation?",
            "final_answer": "Answer with just one source...",
            "rating_good": True,
            "review": {
                "verdict": "good",
                "confidence": 0.9,
            },
            "citations": [
                {"id": 1, "source": "doc1.pdf"}  # Only 1 citation, need 2
            ],
            "is_exemplar": False,
            "question_index": 0
        }

    @pytest.fixture
    def ineligible_qa_pair_bad_verdict(self) -> Dict[str, Any]:
        """Create a Q&A pair with non-good verdict."""
        return {
            "_id": "507f1f77bcf86cd799439041",
            "session_id": "507f1f77bcf86cd799439012",
            "question": "Question with needs improvement?",
            "final_answer": "Answer that needs work...",
            "rating_good": True,
            "review": {
                "verdict": "needs_improvement",  # Not "good"
                "confidence": 0.9,
            },
            "citations": [
                {"id": 1, "source": "doc1.pdf"},
                {"id": 2, "source": "doc2.pdf"}
            ],
            "is_exemplar": False,
            "question_index": 0
        }

    @pytest.mark.asyncio
    async def test_rating_good_triggers_exemplar_promotion(
        self, eligible_qa_pair: Dict[str, Any]
    ) -> None:
        """Test that rating good on eligible Q&A pair triggers auto-promotion."""
        qa_pair_id = eligible_qa_pair["_id"]

        with patch("src.api.routes.qa_pairs.load_settings") as mock_settings, \
             patch("src.api.routes.qa_pairs.QAStorageService") as mock_qa_storage_cls, \
             patch("src.api.routes.qa_pairs.ExemplarService") as mock_exemplar_cls:

            mock_settings.return_value = MagicMock()

            # Mock QA storage
            mock_qa_storage = AsyncMock()
            mock_qa_storage.initialize = AsyncMock()
            mock_qa_storage.cleanup = AsyncMock()
            mock_qa_storage.update_rating = AsyncMock()
            mock_qa_storage_cls.return_value = mock_qa_storage

            # Mock Exemplar service - return True to indicate promotion
            mock_exemplar = AsyncMock()
            mock_exemplar.initialize = AsyncMock()
            mock_exemplar.cleanup = AsyncMock()
            mock_exemplar.check_and_promote_if_eligible = AsyncMock(return_value=True)
            mock_exemplar_cls.return_value = mock_exemplar

            async with create_test_client() as client:
                response = await client.put(
                    f"/api/qa-pairs/{qa_pair_id}/rating",
                    json={"rating_good": True}
                )

            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Q&A pair rating updated successfully"
            assert data["promoted_to_exemplar"] is True

            # Verify the promotion check was called
            mock_exemplar.check_and_promote_if_eligible.assert_called_once_with(qa_pair_id)

    @pytest.mark.asyncio
    async def test_rating_good_no_promotion_when_ineligible(
        self, ineligible_qa_pair_low_confidence: Dict[str, Any]
    ) -> None:
        """Test that rating good on ineligible Q&A pair does not promote."""
        qa_pair_id = ineligible_qa_pair_low_confidence["_id"]

        with patch("src.api.routes.qa_pairs.load_settings") as mock_settings, \
             patch("src.api.routes.qa_pairs.QAStorageService") as mock_qa_storage_cls, \
             patch("src.api.routes.qa_pairs.ExemplarService") as mock_exemplar_cls:

            mock_settings.return_value = MagicMock()

            mock_qa_storage = AsyncMock()
            mock_qa_storage.initialize = AsyncMock()
            mock_qa_storage.cleanup = AsyncMock()
            mock_qa_storage.update_rating = AsyncMock()
            mock_qa_storage_cls.return_value = mock_qa_storage

            # Mock Exemplar service - return False (ineligible)
            mock_exemplar = AsyncMock()
            mock_exemplar.initialize = AsyncMock()
            mock_exemplar.cleanup = AsyncMock()
            mock_exemplar.check_and_promote_if_eligible = AsyncMock(return_value=False)
            mock_exemplar_cls.return_value = mock_exemplar

            async with create_test_client() as client:
                response = await client.put(
                    f"/api/qa-pairs/{qa_pair_id}/rating",
                    json={"rating_good": True}
                )

            assert response.status_code == 200
            data = response.json()
            assert data["promoted_to_exemplar"] is False

    @pytest.mark.asyncio
    async def test_rating_bad_does_not_trigger_promotion(self) -> None:
        """Test that rating bad does not trigger promotion check."""
        qa_pair_id = "507f1f77bcf86cd799439011"

        with patch("src.api.routes.qa_pairs.load_settings") as mock_settings, \
             patch("src.api.routes.qa_pairs.QAStorageService") as mock_qa_storage_cls, \
             patch("src.api.routes.qa_pairs.ExemplarService") as mock_exemplar_cls:

            mock_settings.return_value = MagicMock()

            mock_qa_storage = AsyncMock()
            mock_qa_storage.initialize = AsyncMock()
            mock_qa_storage.cleanup = AsyncMock()
            mock_qa_storage.update_rating = AsyncMock()
            mock_qa_storage_cls.return_value = mock_qa_storage

            mock_exemplar = AsyncMock()
            mock_exemplar.initialize = AsyncMock()
            mock_exemplar.cleanup = AsyncMock()
            mock_exemplar.check_and_promote_if_eligible = AsyncMock()
            mock_exemplar_cls.return_value = mock_exemplar

            async with create_test_client() as client:
                response = await client.put(
                    f"/api/qa-pairs/{qa_pair_id}/rating",
                    json={"rating_good": False}
                )

            assert response.status_code == 200
            data = response.json()
            assert data["promoted_to_exemplar"] is False

            # Verify promotion check was NOT called for bad rating
            mock_exemplar.check_and_promote_if_eligible.assert_not_called()

    @pytest.mark.asyncio
    async def test_rating_null_does_not_trigger_promotion(self) -> None:
        """Test that rating null (reset) does not trigger promotion check."""
        qa_pair_id = "507f1f77bcf86cd799439011"

        with patch("src.api.routes.qa_pairs.load_settings") as mock_settings, \
             patch("src.api.routes.qa_pairs.QAStorageService") as mock_qa_storage_cls, \
             patch("src.api.routes.qa_pairs.ExemplarService") as mock_exemplar_cls:

            mock_settings.return_value = MagicMock()

            mock_qa_storage = AsyncMock()
            mock_qa_storage.initialize = AsyncMock()
            mock_qa_storage.cleanup = AsyncMock()
            mock_qa_storage.update_rating = AsyncMock()
            mock_qa_storage_cls.return_value = mock_qa_storage

            mock_exemplar = AsyncMock()
            mock_exemplar.initialize = AsyncMock()
            mock_exemplar.cleanup = AsyncMock()
            mock_exemplar.check_and_promote_if_eligible = AsyncMock()
            mock_exemplar_cls.return_value = mock_exemplar

            async with create_test_client() as client:
                response = await client.put(
                    f"/api/qa-pairs/{qa_pair_id}/rating",
                    json={"rating_good": None}
                )

            assert response.status_code == 200
            data = response.json()
            assert data["promoted_to_exemplar"] is False

            # Verify promotion check was NOT called for null rating
            mock_exemplar.check_and_promote_if_eligible.assert_not_called()


class TestExemplarEligibilityLogicIntegration:
    """Integration tests for exemplar eligibility logic."""

    def test_all_criteria_met(self) -> None:
        """Test that all criteria must be met for eligibility."""
        eligible = {
            "rating_good": True,
            "review": {"verdict": "good", "confidence": 0.85},
            "citations": [{"id": 1}, {"id": 2}]
        }

        assert check_exemplar_eligibility(eligible) is True

    def test_rating_false_fails(self) -> None:
        """Test that rating_good=False fails eligibility."""
        qa_pair = {
            "rating_good": False,
            "review": {"verdict": "good", "confidence": 0.9},
            "citations": [{"id": 1}, {"id": 2}]
        }

        assert check_exemplar_eligibility(qa_pair) is False

    def test_verdict_not_good_fails(self) -> None:
        """Test that non-good verdict fails eligibility."""
        qa_pair = {
            "rating_good": True,
            "review": {"verdict": "needs_improvement", "confidence": 0.9},
            "citations": [{"id": 1}, {"id": 2}]
        }

        assert check_exemplar_eligibility(qa_pair) is False

    def test_confidence_below_threshold_fails(self) -> None:
        """Test that confidence below threshold fails eligibility."""
        qa_pair = {
            "rating_good": True,
            "review": {"verdict": "good", "confidence": 0.79},  # Just below 0.8
            "citations": [{"id": 1}, {"id": 2}]
        }

        assert check_exemplar_eligibility(qa_pair) is False

    def test_confidence_at_threshold_passes(self) -> None:
        """Test that confidence exactly at threshold passes."""
        qa_pair = {
            "rating_good": True,
            "review": {"verdict": "good", "confidence": 0.8},  # Exactly 0.8
            "citations": [{"id": 1}, {"id": 2}]
        }

        assert check_exemplar_eligibility(qa_pair) is True

    def test_citations_below_minimum_fails(self) -> None:
        """Test that fewer than minimum citations fails eligibility."""
        qa_pair = {
            "rating_good": True,
            "review": {"verdict": "good", "confidence": 0.9},
            "citations": [{"id": 1}]  # Only 1, need 2
        }

        assert check_exemplar_eligibility(qa_pair) is False

    def test_citations_at_minimum_passes(self) -> None:
        """Test that exactly minimum citations passes."""
        qa_pair = {
            "rating_good": True,
            "review": {"verdict": "good", "confidence": 0.9},
            "citations": [{"id": 1}, {"id": 2}]  # Exactly 2
        }

        assert check_exemplar_eligibility(qa_pair) is True

    def test_missing_review_fails(self) -> None:
        """Test that missing review fails eligibility."""
        qa_pair = {
            "rating_good": True,
            "citations": [{"id": 1}, {"id": 2}]
        }

        assert check_exemplar_eligibility(qa_pair) is False

    def test_empty_citations_fails(self) -> None:
        """Test that empty citations list fails eligibility."""
        qa_pair = {
            "rating_good": True,
            "review": {"verdict": "good", "confidence": 0.9},
            "citations": []
        }

        assert check_exemplar_eligibility(qa_pair) is False


class TestExemplarServicePromotionLogic:
    """Tests for ExemplarService promotion and demotion logic."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock settings."""
        settings = MagicMock()
        settings.mongodb_uri = "mongodb://localhost:27017"
        settings.mongodb_database = "test_db"
        settings.mongodb_collection_qa_pairs = "qa_pairs"
        return settings

    @pytest.fixture
    def mock_collection(self) -> AsyncMock:
        """Create mock MongoDB collection."""
        return AsyncMock()

    @pytest.fixture
    def service_with_mocks(
        self, mock_settings: MagicMock, mock_collection: AsyncMock
    ) -> tuple[ExemplarService, AsyncMock]:
        """Create service with mocked dependencies."""
        service = ExemplarService(mock_settings)
        service.mongo_client = MagicMock()
        service.db = MagicMock()
        service.db.__getitem__ = MagicMock(return_value=mock_collection)
        return service, mock_collection

    @pytest.mark.asyncio
    async def test_promote_sets_is_exemplar_true(
        self, service_with_mocks: tuple[ExemplarService, AsyncMock]
    ) -> None:
        """Test that promotion sets is_exemplar=True."""
        service, mock_collection = service_with_mocks
        qa_pair_id = str(ObjectId())

        eligible_doc = {
            "_id": ObjectId(qa_pair_id),
            "rating_good": True,
            "review": {"verdict": "good", "confidence": 0.9},
            "citations": [{"id": 1}, {"id": 2}],
            "is_exemplar": False
        }
        mock_collection.find_one = AsyncMock(return_value=eligible_doc)
        mock_collection.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1)
        )

        result = await service.promote_to_exemplar(qa_pair_id)

        assert result is True

        # Verify update was called with is_exemplar=True
        update_call = mock_collection.update_one.call_args
        update_doc = update_call[0][1]
        assert update_doc["$set"]["is_exemplar"] is True
        assert "promoted_to_exemplar_at" in update_doc["$set"]

    @pytest.mark.asyncio
    async def test_promote_already_exemplar_returns_true(
        self, service_with_mocks: tuple[ExemplarService, AsyncMock]
    ) -> None:
        """Test that promoting an already-exemplar Q&A pair returns True."""
        service, mock_collection = service_with_mocks
        qa_pair_id = str(ObjectId())

        already_exemplar_doc = {
            "_id": ObjectId(qa_pair_id),
            "rating_good": True,
            "review": {"verdict": "good", "confidence": 0.9},
            "citations": [{"id": 1}, {"id": 2}],
            "is_exemplar": True  # Already an exemplar
        }
        mock_collection.find_one = AsyncMock(return_value=already_exemplar_doc)

        result = await service.promote_to_exemplar(qa_pair_id)

        assert result is True
        # Should not call update since already exemplar
        mock_collection.update_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_demote_clears_exemplar_status(
        self, service_with_mocks: tuple[ExemplarService, AsyncMock]
    ) -> None:
        """Test that demotion clears exemplar status and timestamp."""
        service, mock_collection = service_with_mocks
        qa_pair_id = str(ObjectId())

        mock_collection.update_one = AsyncMock(
            return_value=MagicMock(matched_count=1, modified_count=1)
        )

        result = await service.demote_from_exemplar(qa_pair_id)

        assert result is True

        # Verify update clears is_exemplar and promoted_to_exemplar_at
        update_call = mock_collection.update_one.call_args
        update_doc = update_call[0][1]
        assert update_doc["$set"]["is_exemplar"] is False
        assert "promoted_to_exemplar_at" in update_doc["$unset"]


class TestExemplarThresholdConstants:
    """Tests to verify threshold constants are correct."""

    def test_confidence_threshold_is_08(self) -> None:
        """Test that confidence threshold is 0.8 as specified in CR."""
        assert EXEMPLAR_CONFIDENCE_THRESHOLD == 0.8

    def test_min_citations_is_2(self) -> None:
        """Test that minimum citations is 2 as specified in CR."""
        assert EXEMPLAR_MIN_CITATIONS == 2


class TestRatingUpdateWithExemplarPromotion:
    """Tests for the complete rating update flow with exemplar promotion."""

    @pytest.mark.asyncio
    async def test_full_promotion_flow_with_rating(self) -> None:
        """Test complete flow: rate good -> check eligibility -> promote."""
        qa_pair_id = "507f1f77bcf86cd799439011"

        # This simulates the complete flow through the API
        with patch("src.api.routes.qa_pairs.load_settings") as mock_settings, \
             patch("src.api.routes.qa_pairs.QAStorageService") as mock_qa_storage_cls, \
             patch("src.api.routes.qa_pairs.ExemplarService") as mock_exemplar_cls:

            mock_settings.return_value = MagicMock()

            # Track the order of operations
            operations = []

            async def track_rating_update(*args, **kwargs):
                operations.append("rating_update")

            async def track_promotion_check(*args, **kwargs):
                operations.append("promotion_check")
                return True  # Eligible and promoted

            mock_qa_storage = AsyncMock()
            mock_qa_storage.initialize = AsyncMock()
            mock_qa_storage.cleanup = AsyncMock()
            mock_qa_storage.update_rating = AsyncMock(side_effect=track_rating_update)
            mock_qa_storage_cls.return_value = mock_qa_storage

            mock_exemplar = AsyncMock()
            mock_exemplar.initialize = AsyncMock()
            mock_exemplar.cleanup = AsyncMock()
            mock_exemplar.check_and_promote_if_eligible = AsyncMock(
                side_effect=track_promotion_check
            )
            mock_exemplar_cls.return_value = mock_exemplar

            async with create_test_client() as client:
                response = await client.put(
                    f"/api/qa-pairs/{qa_pair_id}/rating",
                    json={"rating_good": True}
                )

            assert response.status_code == 200
            data = response.json()
            assert data["promoted_to_exemplar"] is True

            # Verify order: rating update happens before promotion check
            assert operations == ["rating_update", "promotion_check"]

    @pytest.mark.asyncio
    async def test_rating_update_error_does_not_promote(self) -> None:
        """Test that if rating update fails, promotion is not attempted."""
        qa_pair_id = "507f1f77bcf86cd799439011"

        with patch("src.api.routes.qa_pairs.load_settings") as mock_settings, \
             patch("src.api.routes.qa_pairs.QAStorageService") as mock_qa_storage_cls, \
             patch("src.api.routes.qa_pairs.ExemplarService") as mock_exemplar_cls:

            mock_settings.return_value = MagicMock()

            mock_qa_storage = AsyncMock()
            mock_qa_storage.initialize = AsyncMock()
            mock_qa_storage.cleanup = AsyncMock()
            mock_qa_storage.update_rating = AsyncMock(
                side_effect=Exception("Database error")
            )
            mock_qa_storage_cls.return_value = mock_qa_storage

            mock_exemplar = AsyncMock()
            mock_exemplar.initialize = AsyncMock()
            mock_exemplar.cleanup = AsyncMock()
            mock_exemplar.check_and_promote_if_eligible = AsyncMock()
            mock_exemplar_cls.return_value = mock_exemplar

            async with create_test_client() as client:
                response = await client.put(
                    f"/api/qa-pairs/{qa_pair_id}/rating",
                    json={"rating_good": True}
                )

            # Should fail with error
            assert response.status_code == 500

            # Promotion should NOT have been attempted
            mock_exemplar.check_and_promote_if_eligible.assert_not_called()


# =============================================================================
# Run tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
