"""Unit tests for ExemplarService and exemplar eligibility logic."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any, Dict, List

from bson import ObjectId

from src.services.exemplar_service import (
    ExemplarService,
    check_exemplar_eligibility,
    EXEMPLAR_CONFIDENCE_THRESHOLD,
    EXEMPLAR_MIN_CITATIONS,
)


class TestExemplarEligibilityThresholds:
    """Tests for check_exemplar_eligibility threshold logic."""

    def test_meets_all_criteria(self) -> None:
        """Test Q&A pair that meets all exemplar criteria."""
        qa_pair: Dict[str, Any] = {
            "rating_good": True,
            "review": {
                "verdict": "good",
                "confidence": 0.9
            },
            "citations": [{"id": 1}, {"id": 2}, {"id": 3}]
        }

        assert check_exemplar_eligibility(qa_pair) is True

    def test_rating_not_true(self) -> None:
        """Test Q&A pair with rating_good not True fails."""
        qa_pair: Dict[str, Any] = {
            "rating_good": False,
            "review": {
                "verdict": "good",
                "confidence": 0.9
            },
            "citations": [{"id": 1}, {"id": 2}]
        }

        assert check_exemplar_eligibility(qa_pair) is False

    def test_rating_none(self) -> None:
        """Test Q&A pair with rating_good None fails."""
        qa_pair: Dict[str, Any] = {
            "rating_good": None,
            "review": {
                "verdict": "good",
                "confidence": 0.9
            },
            "citations": [{"id": 1}, {"id": 2}]
        }

        assert check_exemplar_eligibility(qa_pair) is False

    def test_rating_missing(self) -> None:
        """Test Q&A pair without rating_good field fails."""
        qa_pair: Dict[str, Any] = {
            "review": {
                "verdict": "good",
                "confidence": 0.9
            },
            "citations": [{"id": 1}, {"id": 2}]
        }

        assert check_exemplar_eligibility(qa_pair) is False

    def test_review_verdict_not_good(self) -> None:
        """Test Q&A pair with verdict not 'good' fails."""
        qa_pair: Dict[str, Any] = {
            "rating_good": True,
            "review": {
                "verdict": "needs_improvement",
                "confidence": 0.9
            },
            "citations": [{"id": 1}, {"id": 2}]
        }

        assert check_exemplar_eligibility(qa_pair) is False

    def test_review_missing(self) -> None:
        """Test Q&A pair without review field fails."""
        qa_pair: Dict[str, Any] = {
            "rating_good": True,
            "citations": [{"id": 1}, {"id": 2}]
        }

        assert check_exemplar_eligibility(qa_pair) is False

    def test_review_none(self) -> None:
        """Test Q&A pair with review=None fails."""
        qa_pair: Dict[str, Any] = {
            "rating_good": True,
            "review": None,
            "citations": [{"id": 1}, {"id": 2}]
        }

        assert check_exemplar_eligibility(qa_pair) is False

    def test_confidence_below_threshold(self) -> None:
        """Test Q&A pair with confidence below threshold fails."""
        qa_pair: Dict[str, Any] = {
            "rating_good": True,
            "review": {
                "verdict": "good",
                "confidence": 0.7  # Below 0.8 threshold
            },
            "citations": [{"id": 1}, {"id": 2}]
        }

        assert check_exemplar_eligibility(qa_pair) is False

    def test_confidence_exactly_at_threshold(self) -> None:
        """Test Q&A pair with confidence exactly at threshold passes."""
        qa_pair: Dict[str, Any] = {
            "rating_good": True,
            "review": {
                "verdict": "good",
                "confidence": EXEMPLAR_CONFIDENCE_THRESHOLD  # 0.8
            },
            "citations": [{"id": 1}, {"id": 2}]
        }

        assert check_exemplar_eligibility(qa_pair) is True

    def test_confidence_missing_defaults_to_zero(self) -> None:
        """Test Q&A pair without confidence field defaults to 0."""
        qa_pair: Dict[str, Any] = {
            "rating_good": True,
            "review": {
                "verdict": "good"
                # No confidence field
            },
            "citations": [{"id": 1}, {"id": 2}]
        }

        assert check_exemplar_eligibility(qa_pair) is False

    def test_citations_below_minimum(self) -> None:
        """Test Q&A pair with fewer than minimum citations fails."""
        qa_pair: Dict[str, Any] = {
            "rating_good": True,
            "review": {
                "verdict": "good",
                "confidence": 0.9
            },
            "citations": [{"id": 1}]  # Only 1, need 2
        }

        assert check_exemplar_eligibility(qa_pair) is False

    def test_citations_exactly_at_minimum(self) -> None:
        """Test Q&A pair with exactly minimum citations passes."""
        qa_pair: Dict[str, Any] = {
            "rating_good": True,
            "review": {
                "verdict": "good",
                "confidence": 0.9
            },
            "citations": [{"id": 1}, {"id": 2}]  # Exactly 2
        }

        assert check_exemplar_eligibility(qa_pair) is True

    def test_citations_empty(self) -> None:
        """Test Q&A pair with empty citations fails."""
        qa_pair: Dict[str, Any] = {
            "rating_good": True,
            "review": {
                "verdict": "good",
                "confidence": 0.9
            },
            "citations": []
        }

        assert check_exemplar_eligibility(qa_pair) is False

    def test_citations_none(self) -> None:
        """Test Q&A pair with citations=None fails."""
        qa_pair: Dict[str, Any] = {
            "rating_good": True,
            "review": {
                "verdict": "good",
                "confidence": 0.9
            },
            "citations": None
        }

        assert check_exemplar_eligibility(qa_pair) is False

    def test_citations_missing(self) -> None:
        """Test Q&A pair without citations field fails."""
        qa_pair: Dict[str, Any] = {
            "rating_good": True,
            "review": {
                "verdict": "good",
                "confidence": 0.9
            }
        }

        assert check_exemplar_eligibility(qa_pair) is False


class TestExemplarServiceInit:
    """Tests for ExemplarService initialization."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock settings."""
        settings = MagicMock()
        settings.mongodb_uri = "mongodb://localhost:27017"
        settings.mongodb_database = "test_db"
        settings.mongodb_collection_qa_pairs = "qa_pairs"
        return settings

    def test_init_sets_settings(self, mock_settings: MagicMock) -> None:
        """Test that init properly sets settings."""
        service = ExemplarService(mock_settings)
        assert service.settings == mock_settings
        assert service.mongo_client is None
        assert service.db is None


class TestExemplarServiceGetQAPair:
    """Tests for getting Q&A pairs."""

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
    async def test_get_qa_pair_found(
        self, service_with_mocks: tuple[ExemplarService, AsyncMock]
    ) -> None:
        """Test getting Q&A pair when found."""
        service, mock_collection = service_with_mocks
        qa_pair_id = ObjectId()
        session_id = ObjectId()
        mock_doc: Dict[str, Any] = {
            "_id": qa_pair_id,
            "session_id": session_id,
            "question": "Test question?",
            "answer": "Test answer",
            "rating_good": True
        }
        mock_collection.find_one = AsyncMock(return_value=mock_doc)

        result = await service.get_qa_pair(str(qa_pair_id))

        assert result is not None
        assert result["_id"] == str(qa_pair_id)
        assert result["session_id"] == str(session_id)
        mock_collection.find_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_qa_pair_not_found(
        self, service_with_mocks: tuple[ExemplarService, AsyncMock]
    ) -> None:
        """Test getting Q&A pair when not found."""
        service, mock_collection = service_with_mocks
        mock_collection.find_one = AsyncMock(return_value=None)

        result = await service.get_qa_pair(str(ObjectId()))

        assert result is None


class TestExemplarServicePromotion:
    """Tests for exemplar promotion functionality."""

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
    async def test_promote_to_exemplar_eligible(
        self, service_with_mocks: tuple[ExemplarService, AsyncMock]
    ) -> None:
        """Test promoting eligible Q&A pair to exemplar."""
        service, mock_collection = service_with_mocks
        qa_pair_id = ObjectId()

        # Mock find_one to return eligible Q&A pair
        mock_doc: Dict[str, Any] = {
            "_id": qa_pair_id,
            "rating_good": True,
            "review": {"verdict": "good", "confidence": 0.9},
            "citations": [{"id": 1}, {"id": 2}],
            "is_exemplar": False
        }
        mock_collection.find_one = AsyncMock(return_value=mock_doc)

        # Mock update_one
        mock_collection.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1)
        )

        result = await service.promote_to_exemplar(str(qa_pair_id))

        assert result is True
        mock_collection.update_one.assert_called_once()

        # Verify update includes is_exemplar and promoted_to_exemplar_at
        call_args = mock_collection.update_one.call_args
        update_doc = call_args[0][1]
        assert update_doc["$set"]["is_exemplar"] is True
        assert "promoted_to_exemplar_at" in update_doc["$set"]

    @pytest.mark.asyncio
    async def test_promote_to_exemplar_not_eligible(
        self, service_with_mocks: tuple[ExemplarService, AsyncMock]
    ) -> None:
        """Test promoting ineligible Q&A pair fails."""
        service, mock_collection = service_with_mocks
        qa_pair_id = ObjectId()

        # Mock find_one to return ineligible Q&A pair (rating_good=False)
        mock_doc: Dict[str, Any] = {
            "_id": qa_pair_id,
            "rating_good": False,  # Not eligible
            "review": {"verdict": "good", "confidence": 0.9},
            "citations": [{"id": 1}, {"id": 2}]
        }
        mock_collection.find_one = AsyncMock(return_value=mock_doc)

        result = await service.promote_to_exemplar(str(qa_pair_id))

        assert result is False
        mock_collection.update_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_promote_to_exemplar_already_exemplar(
        self, service_with_mocks: tuple[ExemplarService, AsyncMock]
    ) -> None:
        """Test promoting already exemplar Q&A pair returns True."""
        service, mock_collection = service_with_mocks
        qa_pair_id = ObjectId()

        # Mock find_one to return Q&A pair already marked as exemplar
        mock_doc: Dict[str, Any] = {
            "_id": qa_pair_id,
            "rating_good": True,
            "review": {"verdict": "good", "confidence": 0.9},
            "citations": [{"id": 1}, {"id": 2}],
            "is_exemplar": True  # Already exemplar
        }
        mock_collection.find_one = AsyncMock(return_value=mock_doc)

        result = await service.promote_to_exemplar(str(qa_pair_id))

        assert result is True
        mock_collection.update_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_promote_to_exemplar_not_found(
        self, service_with_mocks: tuple[ExemplarService, AsyncMock]
    ) -> None:
        """Test promoting non-existent Q&A pair raises ValueError."""
        service, mock_collection = service_with_mocks
        mock_collection.find_one = AsyncMock(return_value=None)

        with pytest.raises(ValueError) as exc_info:
            await service.promote_to_exemplar(str(ObjectId()))

        assert "Q&A pair not found" in str(exc_info.value)


class TestExemplarServiceDemotion:
    """Tests for exemplar demotion functionality."""

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
    async def test_demote_from_exemplar_success(
        self, service_with_mocks: tuple[ExemplarService, AsyncMock]
    ) -> None:
        """Test demoting Q&A pair from exemplar."""
        service, mock_collection = service_with_mocks
        qa_pair_id = ObjectId()

        mock_collection.update_one = AsyncMock(
            return_value=MagicMock(matched_count=1, modified_count=1)
        )

        result = await service.demote_from_exemplar(str(qa_pair_id))

        assert result is True
        mock_collection.update_one.assert_called_once()

        # Verify update sets is_exemplar=False and unsets promoted_to_exemplar_at
        call_args = mock_collection.update_one.call_args
        update_doc = call_args[0][1]
        assert update_doc["$set"]["is_exemplar"] is False
        assert "promoted_to_exemplar_at" in update_doc["$unset"]

    @pytest.mark.asyncio
    async def test_demote_from_exemplar_not_found(
        self, service_with_mocks: tuple[ExemplarService, AsyncMock]
    ) -> None:
        """Test demoting non-existent Q&A pair raises ValueError."""
        service, mock_collection = service_with_mocks

        mock_collection.update_one = AsyncMock(
            return_value=MagicMock(matched_count=0, modified_count=0)
        )

        with pytest.raises(ValueError) as exc_info:
            await service.demote_from_exemplar(str(ObjectId()))

        assert "Q&A pair not found" in str(exc_info.value)


class TestExemplarServiceListing:
    """Tests for listing exemplar Q&A pairs."""

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
    async def test_get_exemplars(
        self, service_with_mocks: tuple[ExemplarService, AsyncMock]
    ) -> None:
        """Test getting exemplar Q&A pairs."""
        service, mock_collection = service_with_mocks

        mock_exemplars: List[Dict[str, Any]] = [
            {
                "_id": ObjectId(),
                "session_id": ObjectId(),
                "question": "Question 1",
                "is_exemplar": True
            },
            {
                "_id": ObjectId(),
                "session_id": ObjectId(),
                "question": "Question 2",
                "is_exemplar": True
            }
        ]

        async def async_generator():
            for exemplar in mock_exemplars:
                yield exemplar

        mock_cursor = MagicMock()
        mock_cursor.sort = MagicMock(return_value=mock_cursor)
        mock_cursor.skip = MagicMock(return_value=mock_cursor)
        mock_cursor.limit = MagicMock(return_value=mock_cursor)
        mock_cursor.__aiter__ = lambda self: async_generator()
        mock_collection.find = MagicMock(return_value=mock_cursor)

        results = await service.get_exemplars(limit=10, skip=0)

        assert len(results) == 2
        assert all(isinstance(r["_id"], str) for r in results)
        mock_collection.find.assert_called_once_with({"is_exemplar": True})

    @pytest.mark.asyncio
    async def test_get_exemplars_by_session(
        self, service_with_mocks: tuple[ExemplarService, AsyncMock]
    ) -> None:
        """Test getting exemplar Q&A pairs filtered by session."""
        service, mock_collection = service_with_mocks
        session_id = ObjectId()

        async def async_generator():
            return
            yield  # Empty generator

        mock_cursor = MagicMock()
        mock_cursor.sort = MagicMock(return_value=mock_cursor)
        mock_cursor.skip = MagicMock(return_value=mock_cursor)
        mock_cursor.limit = MagicMock(return_value=mock_cursor)
        mock_cursor.__aiter__ = lambda self: async_generator()
        mock_collection.find = MagicMock(return_value=mock_cursor)

        await service.get_exemplars(session_id=str(session_id))

        # Verify session filter was applied
        call_args = mock_collection.find.call_args[0][0]
        assert call_args["is_exemplar"] is True
        assert call_args["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_count_exemplars(
        self, service_with_mocks: tuple[ExemplarService, AsyncMock]
    ) -> None:
        """Test counting exemplar Q&A pairs."""
        service, mock_collection = service_with_mocks
        mock_collection.count_documents = AsyncMock(return_value=42)

        count = await service.count_exemplars()

        assert count == 42
        mock_collection.count_documents.assert_called_once_with({"is_exemplar": True})

    @pytest.mark.asyncio
    async def test_count_exemplars_by_session(
        self, service_with_mocks: tuple[ExemplarService, AsyncMock]
    ) -> None:
        """Test counting exemplar Q&A pairs filtered by session."""
        service, mock_collection = service_with_mocks
        session_id = ObjectId()
        mock_collection.count_documents = AsyncMock(return_value=5)

        count = await service.count_exemplars(session_id=str(session_id))

        assert count == 5
        call_args = mock_collection.count_documents.call_args[0][0]
        assert call_args["is_exemplar"] is True
        assert call_args["session_id"] == session_id


class TestExemplarServiceCheckAndPromote:
    """Tests for check_and_promote_if_eligible convenience method."""

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
    async def test_check_and_promote_eligible(
        self, service_with_mocks: tuple[ExemplarService, AsyncMock]
    ) -> None:
        """Test check_and_promote_if_eligible with eligible pair."""
        service, mock_collection = service_with_mocks
        qa_pair_id = ObjectId()

        mock_doc: Dict[str, Any] = {
            "_id": qa_pair_id,
            "rating_good": True,
            "review": {"verdict": "good", "confidence": 0.9},
            "citations": [{"id": 1}, {"id": 2}],
            "is_exemplar": False
        }
        mock_collection.find_one = AsyncMock(return_value=mock_doc)
        mock_collection.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1)
        )

        result = await service.check_and_promote_if_eligible(str(qa_pair_id))

        assert result is True

    @pytest.mark.asyncio
    async def test_check_and_promote_not_found(
        self, service_with_mocks: tuple[ExemplarService, AsyncMock]
    ) -> None:
        """Test check_and_promote_if_eligible with non-existent pair."""
        service, mock_collection = service_with_mocks
        mock_collection.find_one = AsyncMock(return_value=None)

        result = await service.check_and_promote_if_eligible(str(ObjectId()))

        # Should return False instead of raising exception
        assert result is False


class TestExemplarThresholdConstants:
    """Tests for exemplar threshold constants."""

    def test_confidence_threshold_value(self) -> None:
        """Test that confidence threshold is set to expected value."""
        assert EXEMPLAR_CONFIDENCE_THRESHOLD == 0.8

    def test_min_citations_value(self) -> None:
        """Test that minimum citations is set to expected value."""
        assert EXEMPLAR_MIN_CITATIONS == 2


# =============================================================================
# Run tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
