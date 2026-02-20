"""Unit tests for AnalyticsService and related aggregations."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from typing import Any, Dict, List

from src.services.analytics_service import AnalyticsService


class TestAnalyticsServiceInit:
    """Tests for AnalyticsService initialization."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock settings."""
        settings = MagicMock()
        settings.mongodb_uri = "mongodb://localhost:27017"
        settings.mongodb_database = "test_db"
        settings.mongodb_collection_projects = "projects"
        settings.mongodb_collection_qa_sessions = "qa_sessions"
        settings.mongodb_collection_qa_pairs = "qa_pairs"
        settings.mongodb_collection_tax_offices = "tax_offices"
        return settings

    def test_init_sets_settings(self, mock_settings: MagicMock) -> None:
        """Test that init properly sets settings."""
        service = AnalyticsService(mock_settings)
        assert service.settings == mock_settings
        assert service.mongo_client is None
        assert service.db is None


class TestAnalyticsServiceCounts:
    """Tests for count aggregation methods."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock settings."""
        settings = MagicMock()
        settings.mongodb_uri = "mongodb://localhost:27017"
        settings.mongodb_database = "test_db"
        settings.mongodb_collection_projects = "projects"
        settings.mongodb_collection_qa_sessions = "qa_sessions"
        settings.mongodb_collection_qa_pairs = "qa_pairs"
        settings.mongodb_collection_tax_offices = "tax_offices"
        return settings

    @pytest.fixture
    def mock_collection(self) -> AsyncMock:
        """Create mock MongoDB collection."""
        return AsyncMock()

    @pytest.fixture
    def service_with_mocks(
        self, mock_settings: MagicMock, mock_collection: AsyncMock
    ) -> tuple[AnalyticsService, AsyncMock]:
        """Create service with mocked dependencies."""
        service = AnalyticsService(mock_settings)
        service.mongo_client = MagicMock()
        service.db = MagicMock()
        service.db.__getitem__ = MagicMock(return_value=mock_collection)
        return service, mock_collection

    @pytest.mark.asyncio
    async def test_get_project_count(
        self, service_with_mocks: tuple[AnalyticsService, AsyncMock]
    ) -> None:
        """Test getting project count."""
        service, mock_collection = service_with_mocks
        mock_collection.count_documents = AsyncMock(return_value=42)

        count = await service.get_project_count()

        assert count == 42
        mock_collection.count_documents.assert_called_once_with({})

    @pytest.mark.asyncio
    async def test_get_session_count(
        self, service_with_mocks: tuple[AnalyticsService, AsyncMock]
    ) -> None:
        """Test getting session count."""
        service, mock_collection = service_with_mocks
        mock_collection.count_documents = AsyncMock(return_value=100)

        count = await service.get_session_count()

        assert count == 100
        mock_collection.count_documents.assert_called_once_with({})


class TestAnalyticsServiceSuccessRate:
    """Tests for success rate calculation."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock settings."""
        settings = MagicMock()
        settings.mongodb_uri = "mongodb://localhost:27017"
        settings.mongodb_database = "test_db"
        settings.mongodb_collection_projects = "projects"
        settings.mongodb_collection_qa_sessions = "qa_sessions"
        settings.mongodb_collection_qa_pairs = "qa_pairs"
        settings.mongodb_collection_tax_offices = "tax_offices"
        return settings

    @pytest.fixture
    def mock_collection(self) -> AsyncMock:
        """Create mock MongoDB collection."""
        return AsyncMock()

    @pytest.fixture
    def service_with_mocks(
        self, mock_settings: MagicMock, mock_collection: AsyncMock
    ) -> tuple[AnalyticsService, AsyncMock]:
        """Create service with mocked dependencies."""
        service = AnalyticsService(mock_settings)
        service.mongo_client = MagicMock()
        service.db = MagicMock()
        service.db.__getitem__ = MagicMock(return_value=mock_collection)
        return service, mock_collection

    @pytest.mark.asyncio
    async def test_get_success_rate_with_data(
        self, service_with_mocks: tuple[AnalyticsService, AsyncMock]
    ) -> None:
        """Test success rate calculation with data."""
        service, mock_collection = service_with_mocks

        mock_results: List[Dict[str, Any]] = [
            {"_id": "successful", "count": 8},
            {"_id": "unsuccessful", "count": 2}
        ]

        # aggregate() returns a cursor that needs to_list()
        mock_cursor = AsyncMock()
        mock_cursor.to_list = AsyncMock(return_value=mock_results)
        mock_collection.aggregate = AsyncMock(return_value=mock_cursor)

        result = await service.get_success_rate()

        assert result["total_with_outcome"] == 10
        assert result["successful"] == 8
        assert result["unsuccessful"] == 2
        assert result["success_rate"] == 80.0

    @pytest.mark.asyncio
    async def test_get_success_rate_no_data(
        self, service_with_mocks: tuple[AnalyticsService, AsyncMock]
    ) -> None:
        """Test success rate calculation with no data."""
        service, mock_collection = service_with_mocks

        mock_cursor = AsyncMock()
        mock_cursor.to_list = AsyncMock(return_value=[])
        mock_collection.aggregate = AsyncMock(return_value=mock_cursor)

        result = await service.get_success_rate()

        assert result["total_with_outcome"] == 0
        assert result["successful"] == 0
        assert result["unsuccessful"] == 0
        assert result["success_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_get_success_rate_only_successful(
        self, service_with_mocks: tuple[AnalyticsService, AsyncMock]
    ) -> None:
        """Test success rate with only successful outcomes."""
        service, mock_collection = service_with_mocks

        mock_results: List[Dict[str, Any]] = [
            {"_id": "successful", "count": 10}
        ]

        mock_cursor = AsyncMock()
        mock_cursor.to_list = AsyncMock(return_value=mock_results)
        mock_collection.aggregate = AsyncMock(return_value=mock_cursor)

        result = await service.get_success_rate()

        assert result["success_rate"] == 100.0


class TestAnalyticsServiceDistributions:
    """Tests for distribution aggregation methods."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock settings."""
        settings = MagicMock()
        settings.mongodb_uri = "mongodb://localhost:27017"
        settings.mongodb_database = "test_db"
        settings.mongodb_collection_projects = "projects"
        settings.mongodb_collection_qa_sessions = "qa_sessions"
        settings.mongodb_collection_qa_pairs = "qa_pairs"
        settings.mongodb_collection_tax_offices = "tax_offices"
        return settings

    @pytest.fixture
    def mock_collection(self) -> AsyncMock:
        """Create mock MongoDB collection."""
        return AsyncMock()

    @pytest.fixture
    def service_with_mocks(
        self, mock_settings: MagicMock, mock_collection: AsyncMock
    ) -> tuple[AnalyticsService, AsyncMock]:
        """Create service with mocked dependencies."""
        service = AnalyticsService(mock_settings)
        service.mongo_client = MagicMock()
        service.db = MagicMock()
        service.db.__getitem__ = MagicMock(return_value=mock_collection)
        return service, mock_collection

    @pytest.mark.asyncio
    async def test_get_distribution_by_region(
        self, service_with_mocks: tuple[AnalyticsService, AsyncMock]
    ) -> None:
        """Test region distribution aggregation."""
        service, mock_collection = service_with_mocks

        mock_results: List[Dict[str, Any]] = [
            {"region": "mazowieckie", "count": 15},
            {"region": "śląskie", "count": 10},
            {"region": "małopolskie", "count": 5}
        ]

        mock_cursor = AsyncMock()
        mock_cursor.to_list = AsyncMock(return_value=mock_results)
        mock_collection.aggregate = AsyncMock(return_value=mock_cursor)

        results = await service.get_distribution_by_region()

        assert len(results) == 3
        assert results[0]["region"] == "mazowieckie"
        assert results[0]["count"] == 15

    @pytest.mark.asyncio
    async def test_get_distribution_by_region_empty(
        self, service_with_mocks: tuple[AnalyticsService, AsyncMock]
    ) -> None:
        """Test region distribution with no data."""
        service, mock_collection = service_with_mocks

        mock_cursor = AsyncMock()
        mock_cursor.to_list = AsyncMock(return_value=[])
        mock_collection.aggregate = AsyncMock(return_value=mock_cursor)

        results = await service.get_distribution_by_region()

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_get_distribution_by_industry(
        self, service_with_mocks: tuple[AnalyticsService, AsyncMock]
    ) -> None:
        """Test industry distribution aggregation."""
        service, mock_collection = service_with_mocks

        mock_results: List[Dict[str, Any]] = [
            {"industry": "Branża IT", "count": 20},
            {"industry": "Branża budowlana", "count": 15},
            {"industry": "Branża produkcji maszyn", "count": 8}
        ]

        mock_cursor = AsyncMock()
        mock_cursor.to_list = AsyncMock(return_value=mock_results)
        mock_collection.aggregate = AsyncMock(return_value=mock_cursor)

        results = await service.get_distribution_by_industry()

        assert len(results) == 3
        assert results[0]["industry"] == "Branża IT"
        assert results[0]["count"] == 20

    @pytest.mark.asyncio
    async def test_get_distribution_by_tax_office(
        self, service_with_mocks: tuple[AnalyticsService, AsyncMock]
    ) -> None:
        """Test tax office distribution aggregation."""
        service, mock_collection = service_with_mocks

        mock_results: List[Dict[str, Any]] = [
            {
                "tax_office_id": 101,
                "count": 10,
                "nazwa_urzedu": "Urząd Skarbowy Warszawa-Centrum",
                "miasto": "Warszawa"
            },
            {
                "tax_office_id": 201,
                "count": 5,
                "nazwa_urzedu": "Urząd Skarbowy Kraków-Podgórze",
                "miasto": "Kraków"
            }
        ]

        mock_cursor = AsyncMock()
        mock_cursor.to_list = AsyncMock(return_value=mock_results)
        mock_collection.aggregate = AsyncMock(return_value=mock_cursor)

        results = await service.get_distribution_by_tax_office(limit=10)

        assert len(results) == 2
        assert results[0]["tax_office_id"] == 101
        assert results[0]["nazwa_urzedu"] == "Urząd Skarbowy Warszawa-Centrum"


class TestAnalyticsServiceQualityMetrics:
    """Tests for Q&A quality metrics."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock settings."""
        settings = MagicMock()
        settings.mongodb_uri = "mongodb://localhost:27017"
        settings.mongodb_database = "test_db"
        settings.mongodb_collection_projects = "projects"
        settings.mongodb_collection_qa_sessions = "qa_sessions"
        settings.mongodb_collection_qa_pairs = "qa_pairs"
        settings.mongodb_collection_tax_offices = "tax_offices"
        return settings

    @pytest.fixture
    def mock_collection(self) -> AsyncMock:
        """Create mock MongoDB collection."""
        return AsyncMock()

    @pytest.fixture
    def service_with_mocks(
        self, mock_settings: MagicMock, mock_collection: AsyncMock
    ) -> tuple[AnalyticsService, AsyncMock]:
        """Create service with mocked dependencies."""
        service = AnalyticsService(mock_settings)
        service.mongo_client = MagicMock()
        service.db = MagicMock()
        service.db.__getitem__ = MagicMock(return_value=mock_collection)
        return service, mock_collection

    @pytest.mark.asyncio
    async def test_get_qa_quality_metrics(
        self, service_with_mocks: tuple[AnalyticsService, AsyncMock]
    ) -> None:
        """Test Q&A quality metrics calculation."""
        service, mock_collection = service_with_mocks

        mock_results: List[Dict[str, Any]] = [
            {
                "total": [{"count": 100}],
                "rated_good": [{"count": 60}],
                "rated_bad": [{"count": 20}],
                "exemplars": [{"count": 5}]
            }
        ]

        mock_cursor = AsyncMock()
        mock_cursor.to_list = AsyncMock(return_value=mock_results)
        mock_collection.aggregate = AsyncMock(return_value=mock_cursor)

        result = await service.get_qa_quality_metrics()

        assert result["total_qa_pairs"] == 100
        assert result["rated_count"] == 80
        assert result["good_count"] == 60
        assert result["bad_count"] == 20
        assert result["unrated_count"] == 20
        assert result["good_ratio"] == 75.0
        assert result["exemplar_count"] == 5

    @pytest.mark.asyncio
    async def test_get_qa_quality_metrics_empty(
        self, service_with_mocks: tuple[AnalyticsService, AsyncMock]
    ) -> None:
        """Test Q&A quality metrics with empty database."""
        service, mock_collection = service_with_mocks

        mock_cursor = AsyncMock()
        mock_cursor.to_list = AsyncMock(return_value=[])
        mock_collection.aggregate = AsyncMock(return_value=mock_cursor)

        result = await service.get_qa_quality_metrics()

        assert result["total_qa_pairs"] == 0
        assert result["rated_count"] == 0
        assert result["good_count"] == 0
        assert result["bad_count"] == 0
        assert result["unrated_count"] == 0
        assert result["good_ratio"] == 0.0
        assert result["exemplar_count"] == 0

    @pytest.mark.asyncio
    async def test_get_qa_quality_metrics_no_ratings(
        self, service_with_mocks: tuple[AnalyticsService, AsyncMock]
    ) -> None:
        """Test Q&A quality metrics with no rated pairs."""
        service, mock_collection = service_with_mocks

        mock_results: List[Dict[str, Any]] = [
            {
                "total": [{"count": 50}],
                "rated_good": [],
                "rated_bad": [],
                "exemplars": []
            }
        ]

        mock_cursor = AsyncMock()
        mock_cursor.to_list = AsyncMock(return_value=mock_results)
        mock_collection.aggregate = AsyncMock(return_value=mock_cursor)

        result = await service.get_qa_quality_metrics()

        assert result["total_qa_pairs"] == 50
        assert result["rated_count"] == 0
        assert result["unrated_count"] == 50
        assert result["good_ratio"] == 0.0


class TestAnalyticsServiceTrends:
    """Tests for trends over time."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock settings."""
        settings = MagicMock()
        settings.mongodb_uri = "mongodb://localhost:27017"
        settings.mongodb_database = "test_db"
        settings.mongodb_collection_projects = "projects"
        settings.mongodb_collection_qa_sessions = "qa_sessions"
        settings.mongodb_collection_qa_pairs = "qa_pairs"
        settings.mongodb_collection_tax_offices = "tax_offices"
        return settings

    @pytest.fixture
    def mock_collection(self) -> AsyncMock:
        """Create mock MongoDB collection."""
        return AsyncMock()

    @pytest.fixture
    def service_with_mocks(
        self, mock_settings: MagicMock, mock_collection: AsyncMock
    ) -> tuple[AnalyticsService, AsyncMock]:
        """Create service with mocked dependencies."""
        service = AnalyticsService(mock_settings)
        service.mongo_client = MagicMock()
        service.db = MagicMock()
        service.db.__getitem__ = MagicMock(return_value=mock_collection)
        return service, mock_collection

    @pytest.mark.asyncio
    async def test_get_trends_over_time(
        self, service_with_mocks: tuple[AnalyticsService, AsyncMock]
    ) -> None:
        """Test trends over time aggregation."""
        service, mock_collection = service_with_mocks

        mock_project_trends: List[Dict[str, Any]] = [
            {"date": "2026-01-20", "count": 5},
            {"date": "2026-01-21", "count": 8},
            {"date": "2026-01-22", "count": 3}
        ]
        mock_session_trends: List[Dict[str, Any]] = [
            {"date": "2026-01-20", "count": 10},
            {"date": "2026-01-21", "count": 15}
        ]
        mock_qa_trends: List[Dict[str, Any]] = [
            {"date": "2026-01-20", "count": 30},
            {"date": "2026-01-21", "count": 45}
        ]

        # Create cursors for each collection call
        mock_cursor1 = AsyncMock()
        mock_cursor1.to_list = AsyncMock(return_value=mock_project_trends)
        mock_cursor2 = AsyncMock()
        mock_cursor2.to_list = AsyncMock(return_value=mock_session_trends)
        mock_cursor3 = AsyncMock()
        mock_cursor3.to_list = AsyncMock(return_value=mock_qa_trends)

        mock_collection.aggregate = AsyncMock(
            side_effect=[mock_cursor1, mock_cursor2, mock_cursor3]
        )

        result = await service.get_trends_over_time(days=7, granularity="day")

        assert result["period_days"] == 7
        assert result["granularity"] == "day"
        assert len(result["projects"]) == 3
        assert len(result["sessions"]) == 2
        assert len(result["qa_pairs"]) == 2

    @pytest.mark.asyncio
    async def test_get_trends_over_time_weekly(
        self, service_with_mocks: tuple[AnalyticsService, AsyncMock]
    ) -> None:
        """Test trends with weekly granularity."""
        service, mock_collection = service_with_mocks

        mock_trends: List[Dict[str, Any]] = [
            {"date": "2026-W03", "count": 25},
            {"date": "2026-W04", "count": 30}
        ]

        mock_cursor = AsyncMock()
        mock_cursor.to_list = AsyncMock(return_value=mock_trends)
        mock_collection.aggregate = AsyncMock(return_value=mock_cursor)

        result = await service.get_trends_over_time(days=14, granularity="week")

        assert result["granularity"] == "week"


class TestAnalyticsServiceOutcomeDistribution:
    """Tests for outcome distribution."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock settings."""
        settings = MagicMock()
        settings.mongodb_uri = "mongodb://localhost:27017"
        settings.mongodb_database = "test_db"
        settings.mongodb_collection_projects = "projects"
        settings.mongodb_collection_qa_sessions = "qa_sessions"
        settings.mongodb_collection_qa_pairs = "qa_pairs"
        settings.mongodb_collection_tax_offices = "tax_offices"
        return settings

    @pytest.fixture
    def mock_collection(self) -> AsyncMock:
        """Create mock MongoDB collection."""
        return AsyncMock()

    @pytest.fixture
    def service_with_mocks(
        self, mock_settings: MagicMock, mock_collection: AsyncMock
    ) -> tuple[AnalyticsService, AsyncMock]:
        """Create service with mocked dependencies."""
        service = AnalyticsService(mock_settings)
        service.mongo_client = MagicMock()
        service.db = MagicMock()
        service.db.__getitem__ = MagicMock(return_value=mock_collection)
        return service, mock_collection

    @pytest.mark.asyncio
    async def test_get_outcome_distribution(
        self, service_with_mocks: tuple[AnalyticsService, AsyncMock]
    ) -> None:
        """Test outcome distribution aggregation."""
        service, mock_collection = service_with_mocks

        mock_results: List[Dict[str, Any]] = [
            {"_id": "successful", "count": 50},
            {"_id": "partial", "count": 20},
            {"_id": "negative", "count": 10},
            {"_id": None, "count": 20}
        ]

        mock_cursor = AsyncMock()
        mock_cursor.to_list = AsyncMock(return_value=mock_results)
        mock_collection.aggregate = AsyncMock(return_value=mock_cursor)

        result = await service.get_outcome_distribution()

        assert result["successful"] == 50
        assert result["partial"] == 20
        assert result["negative"] == 10
        assert result["unset"] == 20

    @pytest.mark.asyncio
    async def test_get_outcome_distribution_empty(
        self, service_with_mocks: tuple[AnalyticsService, AsyncMock]
    ) -> None:
        """Test outcome distribution with no data."""
        service, mock_collection = service_with_mocks

        mock_cursor = AsyncMock()
        mock_cursor.to_list = AsyncMock(return_value=[])
        mock_collection.aggregate = AsyncMock(return_value=mock_cursor)

        result = await service.get_outcome_distribution()

        assert result["successful"] == 0
        assert result["partial"] == 0
        assert result["negative"] == 0
        assert result["unset"] == 0


class TestAnalyticsServiceDashboardSummary:
    """Tests for dashboard summary."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock settings."""
        settings = MagicMock()
        settings.mongodb_uri = "mongodb://localhost:27017"
        settings.mongodb_database = "test_db"
        settings.mongodb_collection_projects = "projects"
        settings.mongodb_collection_qa_sessions = "qa_sessions"
        settings.mongodb_collection_qa_pairs = "qa_pairs"
        settings.mongodb_collection_tax_offices = "tax_offices"
        return settings

    @pytest.fixture
    def mock_collection(self) -> AsyncMock:
        """Create mock MongoDB collection."""
        return AsyncMock()

    @pytest.fixture
    def service_with_mocks(
        self, mock_settings: MagicMock, mock_collection: AsyncMock
    ) -> tuple[AnalyticsService, AsyncMock]:
        """Create service with mocked dependencies."""
        service = AnalyticsService(mock_settings)
        service.mongo_client = MagicMock()
        service.db = MagicMock()
        service.db.__getitem__ = MagicMock(return_value=mock_collection)
        return service, mock_collection

    @pytest.mark.asyncio
    async def test_get_dashboard_summary(
        self, service_with_mocks: tuple[AnalyticsService, AsyncMock]
    ) -> None:
        """Test dashboard summary aggregation."""
        service, mock_collection = service_with_mocks

        # Mock count_documents for projects and sessions
        mock_collection.count_documents = AsyncMock(side_effect=[10, 50])

        # Mock aggregate for success rate
        success_rate_results: List[Dict[str, Any]] = [
            {"_id": "successful", "count": 30},
            {"_id": "unsuccessful", "count": 10}
        ]
        success_cursor = AsyncMock()
        success_cursor.to_list = AsyncMock(return_value=success_rate_results)

        # Mock aggregate for quality metrics
        quality_results: List[Dict[str, Any]] = [
            {
                "total": [{"count": 100}],
                "rated_good": [{"count": 60}],
                "rated_bad": [{"count": 20}],
                "exemplars": [{"count": 5}]
            }
        ]
        quality_cursor = AsyncMock()
        quality_cursor.to_list = AsyncMock(return_value=quality_results)

        mock_collection.aggregate = AsyncMock(
            side_effect=[success_cursor, quality_cursor]
        )

        result = await service.get_dashboard_summary()

        assert "counts" in result
        assert result["counts"]["projects"] == 10
        assert result["counts"]["sessions"] == 50
        assert "success_rate" in result
        assert "quality_metrics" in result
        assert "generated_at" in result


class TestAnalyticsServiceSessionDistribution:
    """Tests for session distribution by region."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock settings."""
        settings = MagicMock()
        settings.mongodb_uri = "mongodb://localhost:27017"
        settings.mongodb_database = "test_db"
        settings.mongodb_collection_projects = "projects"
        settings.mongodb_collection_qa_sessions = "qa_sessions"
        settings.mongodb_collection_qa_pairs = "qa_pairs"
        settings.mongodb_collection_tax_offices = "tax_offices"
        return settings

    @pytest.fixture
    def mock_collection(self) -> AsyncMock:
        """Create mock MongoDB collection."""
        return AsyncMock()

    @pytest.fixture
    def service_with_mocks(
        self, mock_settings: MagicMock, mock_collection: AsyncMock
    ) -> tuple[AnalyticsService, AsyncMock]:
        """Create service with mocked dependencies."""
        service = AnalyticsService(mock_settings)
        service.mongo_client = MagicMock()
        service.db = MagicMock()
        service.db.__getitem__ = MagicMock(return_value=mock_collection)
        return service, mock_collection

    @pytest.mark.asyncio
    async def test_get_session_distribution_by_region(
        self, service_with_mocks: tuple[AnalyticsService, AsyncMock]
    ) -> None:
        """Test session distribution by region aggregation."""
        service, mock_collection = service_with_mocks

        mock_results: List[Dict[str, Any]] = [
            {"region": "mazowieckie", "count": 25},
            {"region": "śląskie", "count": 15},
            {"region": "dolnośląskie", "count": 10}
        ]

        mock_cursor = AsyncMock()
        mock_cursor.to_list = AsyncMock(return_value=mock_results)
        mock_collection.aggregate = AsyncMock(return_value=mock_cursor)

        results = await service.get_session_distribution_by_region()

        assert len(results) == 3
        assert results[0]["region"] == "mazowieckie"
        assert results[0]["count"] == 25


# =============================================================================
# Run tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
