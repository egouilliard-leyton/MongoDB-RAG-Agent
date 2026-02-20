"""Integration tests for dashboard API endpoints.

Tests the dashboard routes defined in src/api/routes/dashboard.py.
Uses httpx.AsyncClient with ASGITransport for async testing.
"""

import pytest
from datetime import datetime
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from src.api.routes.dashboard import router
from src.api.middleware import error_handler_middleware


# Create test app with just the dashboard router
test_app = FastAPI()
test_app.middleware("http")(error_handler_middleware)
test_app.include_router(router)


def create_test_client() -> AsyncClient:
    """Create an AsyncClient with ASGITransport for testing."""
    transport = ASGITransport(app=test_app)
    return AsyncClient(transport=transport, base_url="http://test")


class TestDashboardAPISummaryEndpoint:
    """Tests for GET /api/dashboard/summary endpoint."""

    @pytest.fixture
    def mock_summary(self) -> Dict[str, Any]:
        """Create mock dashboard summary data."""
        return {
            "counts": {
                "projects": 42,
                "sessions": 150,
                "qa_pairs": 500
            },
            "success_rate": {
                "total_with_outcome": 100,
                "successful": 75,
                "unsuccessful": 25,
                "success_rate": 75.0
            },
            "quality_metrics": {
                "total_qa_pairs": 500,
                "rated_count": 300,
                "good_count": 250,
                "bad_count": 50,
                "unrated_count": 200,
                "good_ratio": 83.33,
                "exemplar_count": 25
            },
            "generated_at": datetime.utcnow().isoformat()
        }

    @pytest.mark.asyncio
    async def test_get_dashboard_summary_success(
        self, mock_summary: Dict[str, Any]
    ) -> None:
        """Test getting dashboard summary."""
        with patch("src.api.routes.dashboard.load_settings") as mock_settings, \
             patch("src.api.routes.dashboard.AnalyticsService") as mock_service_cls:

            mock_settings.return_value = MagicMock()
            mock_service = AsyncMock()
            mock_service.initialize = AsyncMock()
            mock_service.cleanup = AsyncMock()
            mock_service.get_dashboard_summary = AsyncMock(return_value=mock_summary)
            mock_service_cls.return_value = mock_service

            async with create_test_client() as client:
                response = await client.get("/api/dashboard/summary")

            assert response.status_code == 200
            data = response.json()
            assert "counts" in data
            assert "success_rate" in data
            assert "quality_metrics" in data
            assert data["counts"]["projects"] == 42
            assert data["counts"]["sessions"] == 150
            assert data["success_rate"]["success_rate"] == 75.0

    @pytest.mark.asyncio
    async def test_get_dashboard_summary_empty_data(self) -> None:
        """Test getting dashboard summary with no data."""
        empty_summary = {
            "counts": {
                "projects": 0,
                "sessions": 0,
                "qa_pairs": 0
            },
            "success_rate": {
                "total_with_outcome": 0,
                "successful": 0,
                "unsuccessful": 0,
                "success_rate": 0.0
            },
            "quality_metrics": {
                "total_qa_pairs": 0,
                "rated_count": 0,
                "good_count": 0,
                "bad_count": 0,
                "unrated_count": 0,
                "good_ratio": 0.0,
                "exemplar_count": 0
            },
            "generated_at": datetime.utcnow().isoformat()
        }

        with patch("src.api.routes.dashboard.load_settings") as mock_settings, \
             patch("src.api.routes.dashboard.AnalyticsService") as mock_service_cls:

            mock_settings.return_value = MagicMock()
            mock_service = AsyncMock()
            mock_service.initialize = AsyncMock()
            mock_service.cleanup = AsyncMock()
            mock_service.get_dashboard_summary = AsyncMock(return_value=empty_summary)
            mock_service_cls.return_value = mock_service

            async with create_test_client() as client:
                response = await client.get("/api/dashboard/summary")

            assert response.status_code == 200
            data = response.json()
            assert data["counts"]["projects"] == 0
            assert data["counts"]["sessions"] == 0
            assert data["success_rate"]["success_rate"] == 0.0


class TestDashboardAPIRegionDistributionEndpoint:
    """Tests for GET /api/dashboard/distribution/region endpoint."""

    @pytest.fixture
    def mock_region_distribution(self) -> Dict[str, Any]:
        """Create mock region distribution data."""
        return {
            "projects": [
                {"region": "mazowieckie", "count": 15},
                {"region": "śląskie", "count": 10},
                {"region": "małopolskie", "count": 8}
            ],
            "sessions": [
                {"region": "mazowieckie", "count": 50},
                {"region": "śląskie", "count": 30},
                {"region": "małopolskie", "count": 20}
            ]
        }

    @pytest.mark.asyncio
    async def test_get_distribution_by_region_success(self) -> None:
        """Test getting project and session distribution by region."""
        project_distribution = [
            {"region": "mazowieckie", "count": 15},
            {"region": "śląskie", "count": 10}
        ]
        session_distribution = [
            {"region": "mazowieckie", "count": 50},
            {"region": "śląskie", "count": 30}
        ]

        with patch("src.api.routes.dashboard.load_settings") as mock_settings, \
             patch("src.api.routes.dashboard.AnalyticsService") as mock_service_cls:

            mock_settings.return_value = MagicMock()
            mock_service = AsyncMock()
            mock_service.initialize = AsyncMock()
            mock_service.cleanup = AsyncMock()
            mock_service.get_distribution_by_region = AsyncMock(
                return_value=project_distribution
            )
            mock_service.get_session_distribution_by_region = AsyncMock(
                return_value=session_distribution
            )
            mock_service_cls.return_value = mock_service

            async with create_test_client() as client:
                response = await client.get("/api/dashboard/distribution/region")

            assert response.status_code == 200
            data = response.json()
            assert "projects" in data
            assert "sessions" in data
            assert len(data["projects"]) == 2
            assert len(data["sessions"]) == 2
            assert data["projects"][0]["region"] == "mazowieckie"

    @pytest.mark.asyncio
    async def test_get_distribution_by_region_empty(self) -> None:
        """Test getting distribution with no data."""
        with patch("src.api.routes.dashboard.load_settings") as mock_settings, \
             patch("src.api.routes.dashboard.AnalyticsService") as mock_service_cls:

            mock_settings.return_value = MagicMock()
            mock_service = AsyncMock()
            mock_service.initialize = AsyncMock()
            mock_service.cleanup = AsyncMock()
            mock_service.get_distribution_by_region = AsyncMock(return_value=[])
            mock_service.get_session_distribution_by_region = AsyncMock(return_value=[])
            mock_service_cls.return_value = mock_service

            async with create_test_client() as client:
                response = await client.get("/api/dashboard/distribution/region")

            assert response.status_code == 200
            data = response.json()
            assert data["projects"] == []
            assert data["sessions"] == []


class TestDashboardAPIIndustryDistributionEndpoint:
    """Tests for GET /api/dashboard/distribution/industry endpoint."""

    @pytest.mark.asyncio
    async def test_get_distribution_by_industry_success(self) -> None:
        """Test getting project distribution by industry."""
        industry_distribution = [
            {"industry": "Branża IT", "count": 20},
            {"industry": "Branża budowlana", "count": 15},
            {"industry": "Branża produkcji maszyn", "count": 8}
        ]

        with patch("src.api.routes.dashboard.load_settings") as mock_settings, \
             patch("src.api.routes.dashboard.AnalyticsService") as mock_service_cls:

            mock_settings.return_value = MagicMock()
            mock_service = AsyncMock()
            mock_service.initialize = AsyncMock()
            mock_service.cleanup = AsyncMock()
            mock_service.get_distribution_by_industry = AsyncMock(
                return_value=industry_distribution
            )
            mock_service_cls.return_value = mock_service

            async with create_test_client() as client:
                response = await client.get("/api/dashboard/distribution/industry")

            assert response.status_code == 200
            data = response.json()
            assert "industries" in data
            assert len(data["industries"]) == 3
            assert data["industries"][0]["industry"] == "Branża IT"
            assert data["industries"][0]["count"] == 20

    @pytest.mark.asyncio
    async def test_get_distribution_by_industry_empty(self) -> None:
        """Test getting distribution with no industry data."""
        with patch("src.api.routes.dashboard.load_settings") as mock_settings, \
             patch("src.api.routes.dashboard.AnalyticsService") as mock_service_cls:

            mock_settings.return_value = MagicMock()
            mock_service = AsyncMock()
            mock_service.initialize = AsyncMock()
            mock_service.cleanup = AsyncMock()
            mock_service.get_distribution_by_industry = AsyncMock(return_value=[])
            mock_service_cls.return_value = mock_service

            async with create_test_client() as client:
                response = await client.get("/api/dashboard/distribution/industry")

            assert response.status_code == 200
            data = response.json()
            assert data["industries"] == []


class TestDashboardAPITaxOfficeDistributionEndpoint:
    """Tests for GET /api/dashboard/distribution/tax-office endpoint."""

    @pytest.mark.asyncio
    async def test_get_distribution_by_tax_office_success(self) -> None:
        """Test getting project distribution by tax office."""
        tax_office_distribution = [
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

        with patch("src.api.routes.dashboard.load_settings") as mock_settings, \
             patch("src.api.routes.dashboard.AnalyticsService") as mock_service_cls:

            mock_settings.return_value = MagicMock()
            mock_service = AsyncMock()
            mock_service.initialize = AsyncMock()
            mock_service.cleanup = AsyncMock()
            mock_service.get_distribution_by_tax_office = AsyncMock(
                return_value=tax_office_distribution
            )
            mock_service_cls.return_value = mock_service

            async with create_test_client() as client:
                response = await client.get("/api/dashboard/distribution/tax-office")

            assert response.status_code == 200
            data = response.json()
            assert "tax_offices" in data
            assert len(data["tax_offices"]) == 2
            assert data["tax_offices"][0]["tax_office_id"] == 101
            assert data["tax_offices"][0]["nazwa_urzedu"] == "Urząd Skarbowy Warszawa-Centrum"
            mock_service.get_distribution_by_tax_office.assert_called_once_with(limit=20)

    @pytest.mark.asyncio
    async def test_get_distribution_by_tax_office_with_limit(self) -> None:
        """Test getting distribution with custom limit."""
        with patch("src.api.routes.dashboard.load_settings") as mock_settings, \
             patch("src.api.routes.dashboard.AnalyticsService") as mock_service_cls:

            mock_settings.return_value = MagicMock()
            mock_service = AsyncMock()
            mock_service.initialize = AsyncMock()
            mock_service.cleanup = AsyncMock()
            mock_service.get_distribution_by_tax_office = AsyncMock(return_value=[])
            mock_service_cls.return_value = mock_service

            async with create_test_client() as client:
                response = await client.get("/api/dashboard/distribution/tax-office?limit=50")

            assert response.status_code == 200
            mock_service.get_distribution_by_tax_office.assert_called_once_with(limit=50)

    @pytest.mark.asyncio
    async def test_get_distribution_by_tax_office_limit_validation(self) -> None:
        """Test that limit is validated (max 100)."""
        async with create_test_client() as client:
            response = await client.get("/api/dashboard/distribution/tax-office?limit=200")

        assert response.status_code == 422  # Validation error


class TestDashboardAPITrendsEndpoint:
    """Tests for GET /api/dashboard/trends endpoint."""

    @pytest.fixture
    def mock_trends(self) -> Dict[str, Any]:
        """Create mock trends data."""
        return {
            "period_days": 30,
            "granularity": "day",
            "start_date": "2026-01-01",
            "projects": [
                {"date": "2026-01-20", "count": 5},
                {"date": "2026-01-21", "count": 8},
                {"date": "2026-01-22", "count": 3}
            ],
            "sessions": [
                {"date": "2026-01-20", "count": 15},
                {"date": "2026-01-21", "count": 20}
            ],
            "qa_pairs": [
                {"date": "2026-01-20", "count": 50},
                {"date": "2026-01-21", "count": 65}
            ]
        }

    @pytest.mark.asyncio
    async def test_get_trends_default_params(
        self, mock_trends: Dict[str, Any]
    ) -> None:
        """Test getting trends with default parameters."""
        with patch("src.api.routes.dashboard.load_settings") as mock_settings, \
             patch("src.api.routes.dashboard.AnalyticsService") as mock_service_cls:

            mock_settings.return_value = MagicMock()
            mock_service = AsyncMock()
            mock_service.initialize = AsyncMock()
            mock_service.cleanup = AsyncMock()
            mock_service.get_trends_over_time = AsyncMock(return_value=mock_trends)
            mock_service_cls.return_value = mock_service

            async with create_test_client() as client:
                response = await client.get("/api/dashboard/trends")

            assert response.status_code == 200
            data = response.json()
            assert "period_days" in data
            assert "granularity" in data
            assert "projects" in data
            assert "sessions" in data
            assert "qa_pairs" in data
            mock_service.get_trends_over_time.assert_called_once_with(
                days=30, granularity="day"
            )

    @pytest.mark.asyncio
    async def test_get_trends_custom_days(
        self, mock_trends: Dict[str, Any]
    ) -> None:
        """Test getting trends with custom days parameter."""
        mock_trends["period_days"] = 7

        with patch("src.api.routes.dashboard.load_settings") as mock_settings, \
             patch("src.api.routes.dashboard.AnalyticsService") as mock_service_cls:

            mock_settings.return_value = MagicMock()
            mock_service = AsyncMock()
            mock_service.initialize = AsyncMock()
            mock_service.cleanup = AsyncMock()
            mock_service.get_trends_over_time = AsyncMock(return_value=mock_trends)
            mock_service_cls.return_value = mock_service

            async with create_test_client() as client:
                response = await client.get("/api/dashboard/trends?days=7")

            assert response.status_code == 200
            mock_service.get_trends_over_time.assert_called_once_with(
                days=7, granularity="day"
            )

    @pytest.mark.asyncio
    async def test_get_trends_weekly_granularity(
        self, mock_trends: Dict[str, Any]
    ) -> None:
        """Test getting trends with weekly granularity."""
        mock_trends["granularity"] = "week"

        with patch("src.api.routes.dashboard.load_settings") as mock_settings, \
             patch("src.api.routes.dashboard.AnalyticsService") as mock_service_cls:

            mock_settings.return_value = MagicMock()
            mock_service = AsyncMock()
            mock_service.initialize = AsyncMock()
            mock_service.cleanup = AsyncMock()
            mock_service.get_trends_over_time = AsyncMock(return_value=mock_trends)
            mock_service_cls.return_value = mock_service

            async with create_test_client() as client:
                response = await client.get("/api/dashboard/trends?granularity=week")

            assert response.status_code == 200
            mock_service.get_trends_over_time.assert_called_once_with(
                days=30, granularity="week"
            )

    @pytest.mark.asyncio
    async def test_get_trends_monthly_granularity(
        self, mock_trends: Dict[str, Any]
    ) -> None:
        """Test getting trends with monthly granularity."""
        mock_trends["granularity"] = "month"

        with patch("src.api.routes.dashboard.load_settings") as mock_settings, \
             patch("src.api.routes.dashboard.AnalyticsService") as mock_service_cls:

            mock_settings.return_value = MagicMock()
            mock_service = AsyncMock()
            mock_service.initialize = AsyncMock()
            mock_service.cleanup = AsyncMock()
            mock_service.get_trends_over_time = AsyncMock(return_value=mock_trends)
            mock_service_cls.return_value = mock_service

            async with create_test_client() as client:
                response = await client.get("/api/dashboard/trends?granularity=month")

            assert response.status_code == 200
            mock_service.get_trends_over_time.assert_called_once_with(
                days=30, granularity="month"
            )

    @pytest.mark.asyncio
    async def test_get_trends_invalid_granularity(self) -> None:
        """Test that invalid granularity returns validation error."""
        async with create_test_client() as client:
            response = await client.get("/api/dashboard/trends?granularity=invalid")

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_get_trends_days_validation(self) -> None:
        """Test that days parameter is validated (max 365)."""
        async with create_test_client() as client:
            response = await client.get("/api/dashboard/trends?days=500")

        assert response.status_code == 422  # Validation error


class TestDashboardAPIQualityEndpoint:
    """Tests for GET /api/dashboard/quality endpoint."""

    @pytest.fixture
    def mock_quality_metrics(self) -> Dict[str, Any]:
        """Create mock quality metrics data."""
        return {
            "total_qa_pairs": 500,
            "rated_count": 350,
            "good_count": 300,
            "bad_count": 50,
            "unrated_count": 150,
            "good_ratio": 85.71,
            "exemplar_count": 30
        }

    @pytest.fixture
    def mock_outcome_distribution(self) -> Dict[str, int]:
        """Create mock outcome distribution data."""
        return {
            "successful": 200,
            "partial": 75,
            "negative": 25,
            "unset": 200
        }

    @pytest.mark.asyncio
    async def test_get_quality_metrics_success(
        self,
        mock_quality_metrics: Dict[str, Any],
        mock_outcome_distribution: Dict[str, int]
    ) -> None:
        """Test getting quality metrics."""
        with patch("src.api.routes.dashboard.load_settings") as mock_settings, \
             patch("src.api.routes.dashboard.AnalyticsService") as mock_service_cls:

            mock_settings.return_value = MagicMock()
            mock_service = AsyncMock()
            mock_service.initialize = AsyncMock()
            mock_service.cleanup = AsyncMock()
            mock_service.get_qa_quality_metrics = AsyncMock(
                return_value=mock_quality_metrics
            )
            mock_service.get_outcome_distribution = AsyncMock(
                return_value=mock_outcome_distribution
            )
            mock_service_cls.return_value = mock_service

            async with create_test_client() as client:
                response = await client.get("/api/dashboard/quality")

            assert response.status_code == 200
            data = response.json()
            assert "quality_metrics" in data
            assert "outcome_distribution" in data
            assert data["quality_metrics"]["total_qa_pairs"] == 500
            assert data["quality_metrics"]["good_ratio"] == 85.71
            assert data["outcome_distribution"]["successful"] == 200

    @pytest.mark.asyncio
    async def test_get_quality_metrics_empty(self) -> None:
        """Test getting quality metrics with no data."""
        empty_quality = {
            "total_qa_pairs": 0,
            "rated_count": 0,
            "good_count": 0,
            "bad_count": 0,
            "unrated_count": 0,
            "good_ratio": 0.0,
            "exemplar_count": 0
        }
        empty_outcome = {
            "successful": 0,
            "partial": 0,
            "negative": 0,
            "unset": 0
        }

        with patch("src.api.routes.dashboard.load_settings") as mock_settings, \
             patch("src.api.routes.dashboard.AnalyticsService") as mock_service_cls:

            mock_settings.return_value = MagicMock()
            mock_service = AsyncMock()
            mock_service.initialize = AsyncMock()
            mock_service.cleanup = AsyncMock()
            mock_service.get_qa_quality_metrics = AsyncMock(return_value=empty_quality)
            mock_service.get_outcome_distribution = AsyncMock(return_value=empty_outcome)
            mock_service_cls.return_value = mock_service

            async with create_test_client() as client:
                response = await client.get("/api/dashboard/quality")

            assert response.status_code == 200
            data = response.json()
            assert data["quality_metrics"]["total_qa_pairs"] == 0
            assert data["quality_metrics"]["good_ratio"] == 0.0


class TestDashboardAPIErrorHandling:
    """Tests for error handling in dashboard API."""

    @pytest.mark.asyncio
    async def test_service_initialization_error(self) -> None:
        """Test handling of service initialization errors."""
        with patch("src.api.routes.dashboard.load_settings") as mock_settings, \
             patch("src.api.routes.dashboard.AnalyticsService") as mock_service_cls:

            mock_settings.return_value = MagicMock()
            mock_service = AsyncMock()
            mock_service.initialize = AsyncMock(side_effect=Exception("Connection failed"))
            mock_service.cleanup = AsyncMock()
            mock_service_cls.return_value = mock_service

            async with create_test_client() as client:
                response = await client.get("/api/dashboard/summary")

            assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_aggregation_timeout_error(self) -> None:
        """Test handling of aggregation timeout errors."""
        with patch("src.api.routes.dashboard.load_settings") as mock_settings, \
             patch("src.api.routes.dashboard.AnalyticsService") as mock_service_cls:

            mock_settings.return_value = MagicMock()
            mock_service = AsyncMock()
            mock_service.initialize = AsyncMock()
            mock_service.cleanup = AsyncMock()
            mock_service.get_dashboard_summary = AsyncMock(
                side_effect=Exception("Aggregation timeout")
            )
            mock_service_cls.return_value = mock_service

            async with create_test_client() as client:
                response = await client.get("/api/dashboard/summary")

            assert response.status_code == 500


# =============================================================================
# Run tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
