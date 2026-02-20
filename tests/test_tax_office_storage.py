"""Unit tests for TaxOfficeStorageService."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.tax_office_storage import TaxOfficeStorageService
from src.settings import Settings


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock(spec=Settings)
    settings.mongodb_uri = "mongodb://localhost:27017"
    settings.mongodb_database = "test_db"
    settings.mongodb_collection_tax_offices = "tax_offices"
    return settings


@pytest.fixture
def tax_office_service(mock_settings):
    """Create TaxOfficeStorageService instance with mock settings."""
    return TaxOfficeStorageService(mock_settings)


@pytest.mark.unit
def test_tax_office_service_initialization(tax_office_service, mock_settings):
    """Test TaxOfficeStorageService initializes with correct settings."""
    assert tax_office_service.settings == mock_settings
    assert tax_office_service.mongo_client is None
    assert tax_office_service.db is None


@pytest.mark.unit
def test_collection_name_property(tax_office_service):
    """Test collection_name property returns correct value."""
    assert tax_office_service.collection_name == "tax_offices"


@pytest.mark.unit
def test_tax_office_to_api_conversion(tax_office_service):
    """Test _tax_office_to_api converts ObjectId to string."""
    from bson import ObjectId

    doc = {
        "_id": ObjectId("507f1f77bcf86cd799439011"),
        "kodjednostki": 1001,
        "nazwa_urzedu": "Test Office",
        "wojewodztwo": "mazowieckie"
    }

    result = tax_office_service._tax_office_to_api(doc)

    assert result["_id"] == "507f1f77bcf86cd799439011"
    assert result["kodjednostki"] == 1001
    assert isinstance(result["_id"], str)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_tax_office_duplicate_raises_error(tax_office_service):
    """Test create_tax_office raises ValueError for duplicate kodjednostki."""
    from pymongo.errors import OperationFailure

    with patch.object(tax_office_service, 'initialize', new_callable=AsyncMock):
        with patch.object(tax_office_service, 'db') as mock_db:
            # Mock duplicate key error
            mock_collection = AsyncMock()
            mock_collection.insert_one = AsyncMock(
                side_effect=OperationFailure("duplicate key error")
            )
            mock_db.__getitem__.return_value = mock_collection

            with pytest.raises(ValueError, match="already exists"):
                await tax_office_service.create_tax_office(
                    kodjednostki=1001,
                    nazwa_urzedu="Test Office",
                    typ="US",
                    wojewodztwo="mazowieckie",
                    miasto="Warszawa",
                    ulica="Test",
                    nr_budynku="1",
                    kod_pocztowy="00-000",
                    telefon="123456789",
                    email="test@test.pl",
                    adres_bip="http://test.com"
                )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_search_tax_offices_handles_numeric_query(tax_office_service):
    """Test search_tax_offices handles numeric kodjednostki query."""
    with patch.object(tax_office_service, 'initialize', new_callable=AsyncMock):
        # Mock db to be not None to pass assertion
        tax_office_service.db = MagicMock()

        mock_collection = MagicMock()

        # Create an async iterator that returns empty list
        async def async_iter():
            for item in []:
                yield item

        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: async_iter()

        # Chain the mocks properly
        mock_find = MagicMock()
        mock_sort = MagicMock()
        mock_limit = MagicMock()

        mock_find.return_value = mock_sort
        mock_sort.sort.return_value = mock_limit
        mock_limit.limit.return_value = mock_cursor

        mock_collection.find = mock_find
        tax_office_service.db.__getitem__.return_value = mock_collection

        results = await tax_office_service.search_tax_offices("1001", limit=20)

        # Verify that search_filter includes kodjednostki filter
        call_args = mock_find.call_args[0][0]
        assert "$or" in call_args
        assert any("kodjednostki" in filter_item for filter_item in call_args["$or"])
        assert results == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_tax_office_by_id_returns_none_when_not_found(tax_office_service):
    """Test get_tax_office_by_id returns None when office not found."""
    with patch.object(tax_office_service, 'initialize', new_callable=AsyncMock):
        with patch.object(tax_office_service, 'db') as mock_db:
            mock_collection = AsyncMock()
            mock_collection.find_one = AsyncMock(return_value=None)
            mock_db.__getitem__.return_value = mock_collection

            result = await tax_office_service.get_tax_office_by_id(9999)

            assert result is None
