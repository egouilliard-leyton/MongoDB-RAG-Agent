"""Unit tests for TaxOfficeStorageService."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any, Dict, List

from bson import ObjectId

from src.services.tax_office_storage import TaxOfficeStorageService


class TestTaxOfficeStorageServiceInit:
    """Tests for TaxOfficeStorageService initialization."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock settings."""
        settings = MagicMock()
        settings.mongodb_uri = "mongodb://localhost:27017"
        settings.mongodb_database = "test_db"
        settings.mongodb_collection_tax_offices = "tax_offices"
        return settings

    def test_init_sets_settings(self, mock_settings: MagicMock) -> None:
        """Test that init properly sets settings."""
        service = TaxOfficeStorageService(mock_settings)
        assert service.settings == mock_settings
        assert service.mongo_client is None
        assert service.db is None

    def test_collection_name_property(self, mock_settings: MagicMock) -> None:
        """Test that collection_name property returns correct value."""
        service = TaxOfficeStorageService(mock_settings)
        assert service.collection_name == "tax_offices"


class TestTaxOfficeStorageServiceToApiConversion:
    """Tests for MongoDB document to API format conversion."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock settings."""
        settings = MagicMock()
        settings.mongodb_uri = "mongodb://localhost:27017"
        settings.mongodb_database = "test_db"
        settings.mongodb_collection_tax_offices = "tax_offices"
        return settings

    def test_tax_office_to_api_converts_object_id(
        self, mock_settings: MagicMock
    ) -> None:
        """Test that _tax_office_to_api converts ObjectId to string."""
        service = TaxOfficeStorageService(mock_settings)
        doc_id = ObjectId()
        doc: Dict[str, Any] = {
            "_id": doc_id,
            "kodjednostki": 12345,
            "nazwa_urzedu": "Test Office",
            "miasto": "Warszawa"
        }

        result = service._tax_office_to_api(doc)

        assert result["_id"] == str(doc_id)
        assert result["kodjednostki"] == 12345
        assert result["nazwa_urzedu"] == "Test Office"
        assert result["miasto"] == "Warszawa"

    def test_tax_office_to_api_preserves_other_fields(
        self, mock_settings: MagicMock
    ) -> None:
        """Test that other fields are preserved during conversion."""
        service = TaxOfficeStorageService(mock_settings)
        doc: Dict[str, Any] = {
            "_id": ObjectId(),
            "kodjednostki": 99999,
            "nazwa_urzedu": "Urząd Skarbowy Kraków",
            "typ": "US",
            "wojewodztwo": "małopolskie",
            "miasto": "Kraków",
            "ulica": "ul. Testowa",
            "nr_budynku": "10",
            "kod_pocztowy": "30-001",
            "telefon": "123456789",
            "email": "test@us.gov.pl",
            "adres_bip": "https://bip.test.gov.pl"
        }

        result = service._tax_office_to_api(doc)

        assert result["typ"] == "US"
        assert result["wojewodztwo"] == "małopolskie"
        assert result["ulica"] == "ul. Testowa"
        assert result["email"] == "test@us.gov.pl"


class TestTaxOfficeStorageServiceCRUD:
    """Tests for CRUD operations."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock settings."""
        settings = MagicMock()
        settings.mongodb_uri = "mongodb://localhost:27017"
        settings.mongodb_database = "test_db"
        settings.mongodb_collection_tax_offices = "tax_offices"
        return settings

    @pytest.fixture
    def mock_collection(self) -> AsyncMock:
        """Create mock MongoDB collection."""
        return AsyncMock()

    @pytest.fixture
    def service_with_mocks(
        self, mock_settings: MagicMock, mock_collection: AsyncMock
    ) -> tuple[TaxOfficeStorageService, AsyncMock]:
        """Create service with mocked dependencies."""
        service = TaxOfficeStorageService(mock_settings)
        service.mongo_client = MagicMock()
        service.db = MagicMock()
        service.db.__getitem__ = MagicMock(return_value=mock_collection)
        return service, mock_collection

    @pytest.mark.asyncio
    async def test_create_tax_office(
        self, service_with_mocks: tuple[TaxOfficeStorageService, AsyncMock]
    ) -> None:
        """Test creating a new tax office."""
        service, mock_collection = service_with_mocks
        inserted_id = ObjectId()
        mock_collection.insert_one = AsyncMock(
            return_value=MagicMock(inserted_id=inserted_id)
        )

        result = await service.create_tax_office(
            kodjednostki=12345,
            nazwa_urzedu="Test Tax Office",
            typ="US",
            wojewodztwo="mazowieckie",
            miasto="Warszawa",
            ulica="ul. Testowa",
            nr_budynku="1",
            kod_pocztowy="00-001",
            telefon="123456789",
            email="test@us.gov.pl",
            adres_bip="https://bip.test.gov.pl"
        )

        assert result == str(inserted_id)
        mock_collection.insert_one.assert_called_once()
        call_args = mock_collection.insert_one.call_args[0][0]
        assert call_args["kodjednostki"] == 12345
        assert call_args["nazwa_urzedu"] == "Test Tax Office"
        assert call_args["wojewodztwo"] == "mazowieckie"

    @pytest.mark.asyncio
    async def test_get_tax_office_by_id_found(
        self, service_with_mocks: tuple[TaxOfficeStorageService, AsyncMock]
    ) -> None:
        """Test getting tax office by ID when found."""
        service, mock_collection = service_with_mocks
        doc_id = ObjectId()
        mock_doc: Dict[str, Any] = {
            "_id": doc_id,
            "kodjednostki": 12345,
            "nazwa_urzedu": "Test Office",
            "miasto": "Warszawa"
        }
        mock_collection.find_one = AsyncMock(return_value=mock_doc)

        result = await service.get_tax_office_by_id(12345)

        assert result is not None
        assert result["_id"] == str(doc_id)
        assert result["kodjednostki"] == 12345
        mock_collection.find_one.assert_called_once_with({"kodjednostki": 12345})

    @pytest.mark.asyncio
    async def test_get_tax_office_by_id_not_found(
        self, service_with_mocks: tuple[TaxOfficeStorageService, AsyncMock]
    ) -> None:
        """Test getting tax office by ID when not found."""
        service, mock_collection = service_with_mocks
        mock_collection.find_one = AsyncMock(return_value=None)

        result = await service.get_tax_office_by_id(99999)

        assert result is None
        mock_collection.find_one.assert_called_once_with({"kodjednostki": 99999})

    @pytest.mark.asyncio
    async def test_count_tax_offices(
        self, service_with_mocks: tuple[TaxOfficeStorageService, AsyncMock]
    ) -> None:
        """Test counting tax offices."""
        service, mock_collection = service_with_mocks
        mock_collection.count_documents = AsyncMock(return_value=590)

        count = await service.count_tax_offices()

        assert count == 590
        mock_collection.count_documents.assert_called_once_with({})


class TestTaxOfficeStorageServiceListing:
    """Tests for listing operations."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock settings."""
        settings = MagicMock()
        settings.mongodb_uri = "mongodb://localhost:27017"
        settings.mongodb_database = "test_db"
        settings.mongodb_collection_tax_offices = "tax_offices"
        return settings

    @pytest.fixture
    def mock_collection(self) -> AsyncMock:
        """Create mock MongoDB collection."""
        return AsyncMock()

    @pytest.fixture
    def service_with_mocks(
        self, mock_settings: MagicMock, mock_collection: AsyncMock
    ) -> tuple[TaxOfficeStorageService, AsyncMock]:
        """Create service with mocked dependencies."""
        service = TaxOfficeStorageService(mock_settings)
        service.mongo_client = MagicMock()
        service.db = MagicMock()
        service.db.__getitem__ = MagicMock(return_value=mock_collection)
        return service, mock_collection

    @pytest.mark.asyncio
    async def test_list_tax_offices(
        self, service_with_mocks: tuple[TaxOfficeStorageService, AsyncMock]
    ) -> None:
        """Test listing tax offices with pagination."""
        service, mock_collection = service_with_mocks
        mock_offices: List[Dict[str, Any]] = [
            {"_id": ObjectId(), "kodjednostki": 1, "nazwa_urzedu": "Office 1"},
            {"_id": ObjectId(), "kodjednostki": 2, "nazwa_urzedu": "Office 2"},
        ]

        # Create async iterator mock
        async def async_generator():
            for office in mock_offices:
                yield office

        mock_cursor = MagicMock()
        mock_cursor.sort = MagicMock(return_value=mock_cursor)
        mock_cursor.skip = MagicMock(return_value=mock_cursor)
        mock_cursor.limit = MagicMock(return_value=mock_cursor)
        mock_cursor.__aiter__ = lambda self: async_generator()
        mock_collection.find = MagicMock(return_value=mock_cursor)

        results = await service.list_tax_offices(limit=10, skip=0)

        assert len(results) == 2
        assert results[0]["kodjednostki"] == 1
        assert results[1]["kodjednostki"] == 2
        mock_collection.find.assert_called_once_with()
        mock_cursor.sort.assert_called_once_with("nazwa_urzedu", 1)
        mock_cursor.skip.assert_called_once_with(0)
        mock_cursor.limit.assert_called_once_with(10)


class TestTaxOfficeStorageServiceSearch:
    """Tests for search operations."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock settings."""
        settings = MagicMock()
        settings.mongodb_uri = "mongodb://localhost:27017"
        settings.mongodb_database = "test_db"
        settings.mongodb_collection_tax_offices = "tax_offices"
        return settings

    @pytest.fixture
    def mock_collection(self) -> AsyncMock:
        """Create mock MongoDB collection."""
        return AsyncMock()

    @pytest.fixture
    def service_with_mocks(
        self, mock_settings: MagicMock, mock_collection: AsyncMock
    ) -> tuple[TaxOfficeStorageService, AsyncMock]:
        """Create service with mocked dependencies."""
        service = TaxOfficeStorageService(mock_settings)
        service.mongo_client = MagicMock()
        service.db = MagicMock()
        service.db.__getitem__ = MagicMock(return_value=mock_collection)
        return service, mock_collection

    @pytest.mark.asyncio
    async def test_search_tax_offices_by_name(
        self, service_with_mocks: tuple[TaxOfficeStorageService, AsyncMock]
    ) -> None:
        """Test searching tax offices by name."""
        service, mock_collection = service_with_mocks
        mock_offices: List[Dict[str, Any]] = [
            {"_id": ObjectId(), "kodjednostki": 1, "nazwa_urzedu": "Urząd Skarbowy Warszawa"},
        ]

        async def async_generator():
            for office in mock_offices:
                yield office

        mock_cursor = MagicMock()
        mock_cursor.sort = MagicMock(return_value=mock_cursor)
        mock_cursor.limit = MagicMock(return_value=mock_cursor)
        mock_cursor.__aiter__ = lambda self: async_generator()
        mock_collection.find = MagicMock(return_value=mock_cursor)

        results = await service.search_tax_offices("Warszawa", limit=20)

        assert len(results) == 1
        assert "Warszawa" in results[0]["nazwa_urzedu"]

        # Verify search filter was constructed correctly
        call_args = mock_collection.find.call_args[0][0]
        assert "$or" in call_args
        assert len(call_args["$or"]) == 2  # nazwa_urzedu and miasto regex

    @pytest.mark.asyncio
    async def test_search_tax_offices_by_numeric_id(
        self, service_with_mocks: tuple[TaxOfficeStorageService, AsyncMock]
    ) -> None:
        """Test searching tax offices by numeric kodjednostki."""
        service, mock_collection = service_with_mocks
        mock_offices: List[Dict[str, Any]] = [
            {"_id": ObjectId(), "kodjednostki": 12345, "nazwa_urzedu": "Test Office"},
        ]

        async def async_generator():
            for office in mock_offices:
                yield office

        mock_cursor = MagicMock()
        mock_cursor.sort = MagicMock(return_value=mock_cursor)
        mock_cursor.limit = MagicMock(return_value=mock_cursor)
        mock_cursor.__aiter__ = lambda self: async_generator()
        mock_collection.find = MagicMock(return_value=mock_cursor)

        results = await service.search_tax_offices("12345", limit=20)

        # Verify numeric search was included
        call_args = mock_collection.find.call_args[0][0]
        assert "$or" in call_args
        # Should have 3 conditions when query is numeric
        assert len(call_args["$or"]) == 3

    @pytest.mark.asyncio
    async def test_get_tax_offices_by_region(
        self, service_with_mocks: tuple[TaxOfficeStorageService, AsyncMock]
    ) -> None:
        """Test getting tax offices by region."""
        service, mock_collection = service_with_mocks
        mock_offices: List[Dict[str, Any]] = [
            {"_id": ObjectId(), "kodjednostki": 1, "nazwa_urzedu": "Office 1", "wojewodztwo": "mazowieckie"},
            {"_id": ObjectId(), "kodjednostki": 2, "nazwa_urzedu": "Office 2", "wojewodztwo": "mazowieckie"},
        ]

        async def async_generator():
            for office in mock_offices:
                yield office

        mock_cursor = MagicMock()
        mock_cursor.sort = MagicMock(return_value=mock_cursor)
        mock_cursor.__aiter__ = lambda self: async_generator()
        mock_collection.find = MagicMock(return_value=mock_cursor)

        results = await service.get_tax_offices_by_region("mazowieckie")

        assert len(results) == 2
        mock_collection.find.assert_called_once_with({"wojewodztwo": "mazowieckie"})


class TestTaxOfficeStorageServiceGrouped:
    """Tests for grouped operations."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock settings."""
        settings = MagicMock()
        settings.mongodb_uri = "mongodb://localhost:27017"
        settings.mongodb_database = "test_db"
        settings.mongodb_collection_tax_offices = "tax_offices"
        return settings

    @pytest.fixture
    def mock_collection(self) -> AsyncMock:
        """Create mock MongoDB collection."""
        return AsyncMock()

    @pytest.fixture
    def service_with_mocks(
        self, mock_settings: MagicMock, mock_collection: AsyncMock
    ) -> tuple[TaxOfficeStorageService, AsyncMock]:
        """Create service with mocked dependencies."""
        service = TaxOfficeStorageService(mock_settings)
        service.mongo_client = MagicMock()
        service.db = MagicMock()
        service.db.__getitem__ = MagicMock(return_value=mock_collection)
        return service, mock_collection

    @pytest.mark.asyncio
    async def test_get_tax_offices_grouped_by_region(
        self, service_with_mocks: tuple[TaxOfficeStorageService, AsyncMock]
    ) -> None:
        """Test getting tax offices grouped by region."""
        service, mock_collection = service_with_mocks

        # Mock aggregation result
        mock_groups: List[Dict[str, Any]] = [
            {
                "_id": "mazowieckie",
                "tax_offices": [
                    {"_id": ObjectId(), "kodjednostki": 1, "nazwa_urzedu": "Office 1"},
                    {"_id": ObjectId(), "kodjednostki": 2, "nazwa_urzedu": "Office 2"},
                ]
            },
            {
                "_id": "małopolskie",
                "tax_offices": [
                    {"_id": ObjectId(), "kodjednostki": 3, "nazwa_urzedu": "Office 3"},
                ]
            }
        ]

        async def async_generator():
            for group in mock_groups:
                yield group

        mock_cursor = AsyncMock()
        mock_cursor.__aiter__ = lambda self: async_generator()
        mock_collection.aggregate = AsyncMock(return_value=mock_cursor)

        result = await service.get_tax_offices_grouped_by_region()

        assert len(result) == 2
        assert "mazowieckie" in result
        assert "małopolskie" in result
        assert len(result["mazowieckie"]) == 2
        assert len(result["małopolskie"]) == 1


# =============================================================================
# Run tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
