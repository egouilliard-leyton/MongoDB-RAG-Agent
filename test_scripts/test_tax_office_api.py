"""Integration tests for tax office API endpoints.

Tests the tax office routes defined in src/api/routes/tax_offices.py.
Uses httpx.AsyncClient with ASGITransport for async testing.
"""

import pytest
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from src.api.routes.tax_offices import router
from src.api.models import TaxOffice
from src.api.middleware import error_handler_middleware


# Create test app with just the tax offices router
test_app = FastAPI()
test_app.middleware("http")(error_handler_middleware)
test_app.include_router(router)


def create_test_client() -> AsyncClient:
    """Create an AsyncClient with ASGITransport for testing."""
    transport = ASGITransport(app=test_app)
    return AsyncClient(transport=transport, base_url="http://test")


class TestTaxOfficeAPIListEndpoint:
    """Tests for GET /api/tax-offices endpoint."""

    @pytest.fixture
    def mock_tax_offices(self) -> List[Dict[str, Any]]:
        """Create mock tax office data."""
        return [
            {
                "_id": "507f1f77bcf86cd799439011",
                "kodjednostki": 101,
                "nazwa_urzedu": "Urząd Skarbowy Warszawa-Centrum",
                "typ": "US",
                "wojewodztwo": "mazowieckie",
                "miasto": "Warszawa",
                "ulica": "ul. Marszałkowska",
                "nr_budynku": "1",
                "kod_pocztowy": "00-001",
                "telefon": "123456789",
                "email": "warszawa-centrum@us.gov.pl",
                "adres_bip": "https://bip.us-waw-centrum.gov.pl"
            },
            {
                "_id": "507f1f77bcf86cd799439012",
                "kodjednostki": 201,
                "nazwa_urzedu": "Urząd Skarbowy Kraków-Podgórze",
                "typ": "US",
                "wojewodztwo": "małopolskie",
                "miasto": "Kraków",
                "ulica": "ul. Wielicka",
                "nr_budynku": "10",
                "kod_pocztowy": "30-001",
                "telefon": "987654321",
                "email": "krakow-podgorze@us.gov.pl",
                "adres_bip": "https://bip.us-krk-podgorze.gov.pl"
            },
        ]

    @pytest.mark.asyncio
    async def test_list_tax_offices_success(
        self, mock_tax_offices: List[Dict[str, Any]]
    ) -> None:
        """Test listing tax offices with default pagination."""
        with patch("src.api.routes.tax_offices.load_settings") as mock_settings, \
             patch("src.api.routes.tax_offices.TaxOfficeStorageService") as mock_service_cls:

            mock_settings.return_value = MagicMock()
            mock_service = AsyncMock()
            mock_service.initialize = AsyncMock()
            mock_service.cleanup = AsyncMock()
            mock_service.list_tax_offices = AsyncMock(return_value=mock_tax_offices)
            mock_service_cls.return_value = mock_service

            async with create_test_client() as client:
                response = await client.get("/api/tax-offices")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["kodjednostki"] == 101
            assert data[1]["kodjednostki"] == 201
            mock_service.list_tax_offices.assert_called_once_with(limit=100, skip=0)

    @pytest.mark.asyncio
    async def test_list_tax_offices_with_pagination(
        self, mock_tax_offices: List[Dict[str, Any]]
    ) -> None:
        """Test listing tax offices with custom pagination."""
        with patch("src.api.routes.tax_offices.load_settings") as mock_settings, \
             patch("src.api.routes.tax_offices.TaxOfficeStorageService") as mock_service_cls:

            mock_settings.return_value = MagicMock()
            mock_service = AsyncMock()
            mock_service.initialize = AsyncMock()
            mock_service.cleanup = AsyncMock()
            mock_service.list_tax_offices = AsyncMock(return_value=[mock_tax_offices[0]])
            mock_service_cls.return_value = mock_service

            async with create_test_client() as client:
                response = await client.get("/api/tax-offices?limit=50&skip=10")

            assert response.status_code == 200
            mock_service.list_tax_offices.assert_called_once_with(limit=50, skip=10)

    @pytest.mark.asyncio
    async def test_list_tax_offices_limit_validation(self) -> None:
        """Test that limit is validated (max 600)."""
        async with create_test_client() as client:
            response = await client.get("/api/tax-offices?limit=1000")

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_list_tax_offices_empty_result(self) -> None:
        """Test listing tax offices with no results."""
        with patch("src.api.routes.tax_offices.load_settings") as mock_settings, \
             patch("src.api.routes.tax_offices.TaxOfficeStorageService") as mock_service_cls:

            mock_settings.return_value = MagicMock()
            mock_service = AsyncMock()
            mock_service.initialize = AsyncMock()
            mock_service.cleanup = AsyncMock()
            mock_service.list_tax_offices = AsyncMock(return_value=[])
            mock_service_cls.return_value = mock_service

            async with create_test_client() as client:
                response = await client.get("/api/tax-offices")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 0


class TestTaxOfficeAPISearchEndpoint:
    """Tests for GET /api/tax-offices/search endpoint."""

    @pytest.fixture
    def mock_search_results(self) -> List[Dict[str, Any]]:
        """Create mock search results."""
        return [
            {
                "_id": "507f1f77bcf86cd799439011",
                "kodjednostki": 101,
                "nazwa_urzedu": "Urząd Skarbowy Warszawa-Centrum",
                "typ": "US",
                "wojewodztwo": "mazowieckie",
                "miasto": "Warszawa",
                "ulica": "ul. Marszałkowska",
                "nr_budynku": "1",
                "kod_pocztowy": "00-001",
                "telefon": "123456789",
                "email": "warszawa-centrum@us.gov.pl",
                "adres_bip": "https://bip.us-waw-centrum.gov.pl"
            },
        ]

    @pytest.mark.asyncio
    async def test_search_tax_offices_by_name(
        self, mock_search_results: List[Dict[str, Any]]
    ) -> None:
        """Test searching tax offices by name."""
        with patch("src.api.routes.tax_offices.load_settings") as mock_settings, \
             patch("src.api.routes.tax_offices.TaxOfficeStorageService") as mock_service_cls:

            mock_settings.return_value = MagicMock()
            mock_service = AsyncMock()
            mock_service.initialize = AsyncMock()
            mock_service.cleanup = AsyncMock()
            mock_service.search_tax_offices = AsyncMock(return_value=mock_search_results)
            mock_service_cls.return_value = mock_service

            async with create_test_client() as client:
                response = await client.get("/api/tax-offices/search?q=Warszawa")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert "Warszawa" in data[0]["nazwa_urzedu"]
            mock_service.search_tax_offices.assert_called_once_with(query="Warszawa", limit=20)

    @pytest.mark.asyncio
    async def test_search_tax_offices_by_city(
        self, mock_search_results: List[Dict[str, Any]]
    ) -> None:
        """Test searching tax offices by city."""
        with patch("src.api.routes.tax_offices.load_settings") as mock_settings, \
             patch("src.api.routes.tax_offices.TaxOfficeStorageService") as mock_service_cls:

            mock_settings.return_value = MagicMock()
            mock_service = AsyncMock()
            mock_service.initialize = AsyncMock()
            mock_service.cleanup = AsyncMock()
            mock_service.search_tax_offices = AsyncMock(return_value=mock_search_results)
            mock_service_cls.return_value = mock_service

            async with create_test_client() as client:
                response = await client.get("/api/tax-offices/search?q=Warszawa&limit=10")

            assert response.status_code == 200
            mock_service.search_tax_offices.assert_called_once_with(query="Warszawa", limit=10)

    @pytest.mark.asyncio
    async def test_search_tax_offices_by_kodjednostki(
        self, mock_search_results: List[Dict[str, Any]]
    ) -> None:
        """Test searching tax offices by numeric ID."""
        with patch("src.api.routes.tax_offices.load_settings") as mock_settings, \
             patch("src.api.routes.tax_offices.TaxOfficeStorageService") as mock_service_cls:

            mock_settings.return_value = MagicMock()
            mock_service = AsyncMock()
            mock_service.initialize = AsyncMock()
            mock_service.cleanup = AsyncMock()
            mock_service.search_tax_offices = AsyncMock(return_value=mock_search_results)
            mock_service_cls.return_value = mock_service

            async with create_test_client() as client:
                response = await client.get("/api/tax-offices/search?q=101")

            assert response.status_code == 200
            mock_service.search_tax_offices.assert_called_once_with(query="101", limit=20)

    @pytest.mark.asyncio
    async def test_search_tax_offices_empty_query(self) -> None:
        """Test search with empty query returns validation error."""
        async with create_test_client() as client:
            response = await client.get("/api/tax-offices/search?q=")

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_search_tax_offices_missing_query(self) -> None:
        """Test search without query parameter returns validation error."""
        async with create_test_client() as client:
            response = await client.get("/api/tax-offices/search")

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_search_tax_offices_no_results(self) -> None:
        """Test search with no matching results."""
        with patch("src.api.routes.tax_offices.load_settings") as mock_settings, \
             patch("src.api.routes.tax_offices.TaxOfficeStorageService") as mock_service_cls:

            mock_settings.return_value = MagicMock()
            mock_service = AsyncMock()
            mock_service.initialize = AsyncMock()
            mock_service.cleanup = AsyncMock()
            mock_service.search_tax_offices = AsyncMock(return_value=[])
            mock_service_cls.return_value = mock_service

            async with create_test_client() as client:
                response = await client.get("/api/tax-offices/search?q=nonexistent")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 0


class TestTaxOfficeAPIGetByIdEndpoint:
    """Tests for GET /api/tax-offices/{kodjednostki} endpoint."""

    @pytest.fixture
    def mock_tax_office(self) -> Dict[str, Any]:
        """Create mock tax office data."""
        return {
            "_id": "507f1f77bcf86cd799439011",
            "kodjednostki": 12345,
            "nazwa_urzedu": "Urząd Skarbowy Test",
            "typ": "US",
            "wojewodztwo": "mazowieckie",
            "miasto": "Test City",
            "ulica": "ul. Testowa",
            "nr_budynku": "1",
            "kod_pocztowy": "00-001",
            "telefon": "123456789",
            "email": "test@us.gov.pl",
            "adres_bip": "https://bip.test.gov.pl"
        }

    @pytest.mark.asyncio
    async def test_get_tax_office_by_id_found(
        self, mock_tax_office: Dict[str, Any]
    ) -> None:
        """Test getting tax office by kodjednostki when found."""
        with patch("src.api.routes.tax_offices.load_settings") as mock_settings, \
             patch("src.api.routes.tax_offices.TaxOfficeStorageService") as mock_service_cls:

            mock_settings.return_value = MagicMock()
            mock_service = AsyncMock()
            mock_service.initialize = AsyncMock()
            mock_service.cleanup = AsyncMock()
            mock_service.get_tax_office_by_id = AsyncMock(return_value=mock_tax_office)
            mock_service_cls.return_value = mock_service

            async with create_test_client() as client:
                response = await client.get("/api/tax-offices/12345")

            assert response.status_code == 200
            data = response.json()
            assert data["kodjednostki"] == 12345
            assert data["nazwa_urzedu"] == "Urząd Skarbowy Test"
            mock_service.get_tax_office_by_id.assert_called_once_with(12345)

    @pytest.mark.asyncio
    async def test_get_tax_office_by_id_not_found(self) -> None:
        """Test getting tax office by kodjednostki when not found."""
        with patch("src.api.routes.tax_offices.load_settings") as mock_settings, \
             patch("src.api.routes.tax_offices.TaxOfficeStorageService") as mock_service_cls:

            mock_settings.return_value = MagicMock()
            mock_service = AsyncMock()
            mock_service.initialize = AsyncMock()
            mock_service.cleanup = AsyncMock()
            mock_service.get_tax_office_by_id = AsyncMock(return_value=None)
            mock_service_cls.return_value = mock_service

            async with create_test_client() as client:
                response = await client.get("/api/tax-offices/99999")

            assert response.status_code == 404
            data = response.json()
            assert "not found" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_get_tax_office_invalid_id(self) -> None:
        """Test getting tax office with invalid (negative) kodjednostki."""
        with patch("src.api.routes.tax_offices.load_settings") as mock_settings, \
             patch("src.api.routes.tax_offices.TaxOfficeStorageService") as mock_service_cls:

            mock_settings.return_value = MagicMock()
            mock_service = AsyncMock()
            mock_service.initialize = AsyncMock()
            mock_service.cleanup = AsyncMock()
            mock_service_cls.return_value = mock_service

            async with create_test_client() as client:
                response = await client.get("/api/tax-offices/-1")

            assert response.status_code == 400  # Validation error
            data = response.json()
            assert "positive" in data["message"].lower()


class TestTaxOfficeAPIRegionsEndpoint:
    """Tests for GET /api/tax-offices/regions endpoint."""

    @pytest.fixture
    def mock_grouped_offices(self) -> Dict[str, List[Dict[str, Any]]]:
        """Create mock grouped tax offices."""
        return {
            "mazowieckie": [
                {
                    "_id": "507f1f77bcf86cd799439011",
                    "kodjednostki": 101,
                    "nazwa_urzedu": "Urząd Skarbowy Warszawa",
                    "typ": "US",
                    "wojewodztwo": "mazowieckie",
                    "miasto": "Warszawa",
                    "ulica": "ul. Test",
                    "nr_budynku": "1",
                    "kod_pocztowy": "00-001",
                    "telefon": "123456789",
                    "email": "test@us.gov.pl",
                    "adres_bip": "https://bip.test.gov.pl"
                }
            ],
            "małopolskie": [
                {
                    "_id": "507f1f77bcf86cd799439012",
                    "kodjednostki": 201,
                    "nazwa_urzedu": "Urząd Skarbowy Kraków",
                    "typ": "US",
                    "wojewodztwo": "małopolskie",
                    "miasto": "Kraków",
                    "ulica": "ul. Test",
                    "nr_budynku": "1",
                    "kod_pocztowy": "30-001",
                    "telefon": "987654321",
                    "email": "krakow@us.gov.pl",
                    "adres_bip": "https://bip.krakow.gov.pl"
                }
            ]
        }

    @pytest.mark.asyncio
    async def test_list_tax_offices_by_region(
        self, mock_grouped_offices: Dict[str, List[Dict[str, Any]]]
    ) -> None:
        """Test listing tax offices grouped by region."""
        with patch("src.api.routes.tax_offices.load_settings") as mock_settings, \
             patch("src.api.routes.tax_offices.TaxOfficeStorageService") as mock_service_cls:

            mock_settings.return_value = MagicMock()
            mock_service = AsyncMock()
            mock_service.initialize = AsyncMock()
            mock_service.cleanup = AsyncMock()
            mock_service.get_tax_offices_grouped_by_region = AsyncMock(
                return_value=mock_grouped_offices
            )
            mock_service_cls.return_value = mock_service

            async with create_test_client() as client:
                response = await client.get("/api/tax-offices/regions")

            assert response.status_code == 200
            data = response.json()
            assert "mazowieckie" in data
            assert "małopolskie" in data
            assert len(data["mazowieckie"]) == 1
            assert len(data["małopolskie"]) == 1


class TestTaxOfficeAPICountEndpoint:
    """Tests for GET /api/tax-offices/count endpoint."""

    @pytest.mark.asyncio
    async def test_count_tax_offices(self) -> None:
        """Test counting all tax offices."""
        with patch("src.api.routes.tax_offices.load_settings") as mock_settings, \
             patch("src.api.routes.tax_offices.TaxOfficeStorageService") as mock_service_cls:

            mock_settings.return_value = MagicMock()
            mock_service = AsyncMock()
            mock_service.initialize = AsyncMock()
            mock_service.cleanup = AsyncMock()
            mock_service.count_tax_offices = AsyncMock(return_value=590)
            mock_service_cls.return_value = mock_service

            async with create_test_client() as client:
                response = await client.get("/api/tax-offices/count")

            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 590

    @pytest.mark.asyncio
    async def test_count_tax_offices_empty(self) -> None:
        """Test counting when no tax offices exist."""
        with patch("src.api.routes.tax_offices.load_settings") as mock_settings, \
             patch("src.api.routes.tax_offices.TaxOfficeStorageService") as mock_service_cls:

            mock_settings.return_value = MagicMock()
            mock_service = AsyncMock()
            mock_service.initialize = AsyncMock()
            mock_service.cleanup = AsyncMock()
            mock_service.count_tax_offices = AsyncMock(return_value=0)
            mock_service_cls.return_value = mock_service

            async with create_test_client() as client:
                response = await client.get("/api/tax-offices/count")

            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 0


class TestTaxOfficeAPIErrorHandling:
    """Tests for error handling in tax office API."""

    @pytest.mark.asyncio
    async def test_service_initialization_error(self) -> None:
        """Test handling of service initialization errors."""
        with patch("src.api.routes.tax_offices.load_settings") as mock_settings, \
             patch("src.api.routes.tax_offices.TaxOfficeStorageService") as mock_service_cls:

            mock_settings.return_value = MagicMock()
            mock_service = AsyncMock()
            mock_service.initialize = AsyncMock(side_effect=Exception("Connection failed"))
            mock_service.cleanup = AsyncMock()
            mock_service_cls.return_value = mock_service

            async with create_test_client() as client:
                response = await client.get("/api/tax-offices")

            assert response.status_code == 500


# =============================================================================
# Run tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
