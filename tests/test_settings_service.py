"""Unit tests for SettingsService."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from bson import ObjectId

from src.services.settings_service import SettingsService, SETTINGS_FIELDS


@pytest.fixture
def mock_settings():
    """Create a mock Settings object with all required attributes."""
    settings = MagicMock()
    settings.mongodb_uri = "mongodb://localhost:27017"
    settings.mongodb_database = "test_db"
    settings.mongodb_collection_app_settings = "app_settings"
    settings.mongodb_collection_qa_pairs = "qa_pairs"
    settings.llm_model = "test-model"
    settings.llm_base_url = "http://test"
    settings.embedding_model = "test-embedding"
    settings.default_match_count = 10
    settings.max_match_count = 50
    settings.enable_question_decomposition = True
    settings.enable_iterative_refinement = True
    settings.show_full_citations = False
    return settings


@pytest.fixture
def service(mock_settings):
    """Create a SettingsService with mocked DB layer."""
    svc = SettingsService(mock_settings)
    # Mark as already initialized so initialize() is a no-op
    svc.mongo_client = MagicMock()
    svc.db = MagicMock()
    return svc


def _make_collection_mock():
    """Create an AsyncMock that behaves like a Motor collection."""
    coll = MagicMock()
    coll.find_one = AsyncMock(return_value=None)
    coll.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))
    coll.update_one = AsyncMock()
    coll.replace_one = AsyncMock()
    coll.count_documents = AsyncMock(return_value=0)
    return coll


@pytest.mark.asyncio
@patch("src.services.settings_service.SettingsService._seed_from_env", new_callable=AsyncMock)
async def test_get_current_seeds_on_first_call(mock_seed, service):
    """When no global_config exists, _seed_from_env should be called."""
    seeded_doc = {
        "_id": ObjectId(),
        "type": "global_config",
        "version": 1,
        "main_system_prompt": "prompt",
    }
    mock_seed.return_value = seeded_doc

    coll = _make_collection_mock()
    coll.find_one = AsyncMock(return_value=None)
    service.db.__getitem__ = MagicMock(return_value=coll)

    result = await service.get_current()

    mock_seed.assert_awaited_once()
    assert result["version"] == 1
    # _id should be stringified
    assert isinstance(result["_id"], str)


@pytest.mark.asyncio
async def test_get_current_returns_existing(service):
    """When global_config exists, it should be returned directly."""
    existing_doc = {
        "_id": ObjectId(),
        "type": "global_config",
        "version": 3,
        "main_system_prompt": "existing prompt",
        "default_match_count": 15,
    }

    coll = _make_collection_mock()
    coll.find_one = AsyncMock(return_value=existing_doc)
    service.db.__getitem__ = MagicMock(return_value=coll)

    result = await service.get_current()

    assert result["version"] == 3
    assert result["main_system_prompt"] == "existing prompt"
    assert isinstance(result["_id"], str)


@pytest.mark.asyncio
async def test_update_creates_new_version(service):
    """Updating settings should archive old version and increment version number."""
    old_id = ObjectId()
    current_doc = {
        "_id": old_id,
        "type": "global_config",
        "version": 2,
        "default_match_count": 10,
        "llm_model": "old-model",
    }
    updated_doc = {
        "_id": old_id,
        "type": "global_config",
        "version": 3,
        "default_match_count": 20,
        "llm_model": "old-model",
    }

    coll = _make_collection_mock()
    # First find_one returns current, second returns updated
    coll.find_one = AsyncMock(side_effect=[current_doc, updated_doc])
    service.db.__getitem__ = MagicMock(return_value=coll)

    result = await service.update({"default_match_count": 20})

    # Should have inserted a version archive doc
    coll.insert_one.assert_awaited_once()
    version_doc = coll.insert_one.call_args[0][0]
    assert version_doc["type"] == "version"
    assert version_doc["version"] == 2
    assert "default_match_count" in version_doc["changed_fields"]

    # Should have called update_one on the global_config
    coll.update_one.assert_awaited_once()
    update_call = coll.update_one.call_args
    assert update_call[0][0] == {"type": "global_config"}
    set_fields = update_call[0][1]["$set"]
    assert set_fields["version"] == 3
    assert set_fields["default_match_count"] == 20

    assert result["version"] == 3


@pytest.mark.asyncio
async def test_update_no_changes_returns_current(service):
    """If no fields actually change, the current config should be returned as-is."""
    old_id = ObjectId()
    current_doc = {
        "_id": old_id,
        "type": "global_config",
        "version": 2,
        "default_match_count": 10,
    }

    coll = _make_collection_mock()
    coll.find_one = AsyncMock(return_value=current_doc)
    service.db.__getitem__ = MagicMock(return_value=coll)

    result = await service.update({"default_match_count": 10})

    # No insert/update should happen
    coll.insert_one.assert_not_awaited()
    coll.update_one.assert_not_awaited()
    assert result["version"] == 2


@pytest.mark.asyncio
async def test_get_history_returns_versions(service):
    """get_history should return version docs sorted by version desc."""
    version_docs = [
        {
            "_id": ObjectId(),
            "type": "version",
            "version": 3,
            "changed_fields": ["llm_model"],
            "summary": "Updated llm_model",
            "created_at": datetime(2026, 2, 23),
        },
        {
            "_id": ObjectId(),
            "type": "version",
            "version": 2,
            "changed_fields": ["default_match_count"],
            "summary": "Updated default_match_count",
            "created_at": datetime(2026, 2, 22),
        },
    ]

    # Build a mock async cursor
    async def _async_iter(docs):
        for d in docs:
            yield d

    cursor_mock = MagicMock()
    cursor_mock.sort = MagicMock(return_value=cursor_mock)
    cursor_mock.limit = MagicMock(return_value=cursor_mock)
    cursor_mock.__aiter__ = lambda self: _async_iter(version_docs).__aiter__()

    coll = MagicMock()
    coll.find = MagicMock(return_value=cursor_mock)
    service.db.__getitem__ = MagicMock(return_value=coll)

    result = await service.get_history(limit=20)

    assert len(result) == 2
    assert result[0]["version"] == 3
    assert result[1]["version"] == 2
    assert result[0]["changed_fields"] == ["llm_model"]
    coll.find.assert_called_once_with({"type": "version"})


@pytest.mark.asyncio
async def test_restore_version_calls_update(service):
    """restore() should find the version doc and call update() with its snapshot."""
    version_doc = {
        "_id": ObjectId(),
        "type": "version",
        "version": 2,
        "snapshot": {"default_match_count": 15, "llm_model": "old-model"},
        "created_at": datetime(2026, 2, 22),
    }

    coll = _make_collection_mock()
    coll.find_one = AsyncMock(return_value=version_doc)
    service.db.__getitem__ = MagicMock(return_value=coll)

    with patch.object(service, "update", new_callable=AsyncMock) as mock_update:
        mock_update.return_value = {"version": 4, "_id": "abc"}
        result = await service.restore(version=2)

    mock_update.assert_awaited_once_with(version_doc["snapshot"])
    assert result["version"] == 4


@pytest.mark.asyncio
async def test_restore_version_not_found_raises(service):
    """restore() should raise ValueError if version not found."""
    coll = _make_collection_mock()
    coll.find_one = AsyncMock(return_value=None)
    service.db.__getitem__ = MagicMock(return_value=coll)

    with pytest.raises(ValueError, match="Version 99 not found"):
        await service.restore(version=99)


@pytest.mark.asyncio
async def test_seed_from_env_uses_prompt_constants(service):
    """_seed_from_env should use MAIN_SYSTEM_PROMPT and other constants from src.prompts."""
    coll = _make_collection_mock()
    coll.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))
    service.db.__getitem__ = MagicMock(return_value=coll)

    # The prompts are lazily imported inside _seed_from_env, so patch src.prompts
    with patch("src.prompts.MAIN_SYSTEM_PROMPT", "test-main-prompt"), \
         patch("src.prompts.FOLLOW_UP_CONTEXT_PROMPT", "test-followup"), \
         patch("src.prompts.QA_HISTORY_PROMPT", "test-qa-hist"):
        result = await service._seed_from_env()

    assert result["type"] == "global_config"
    assert result["version"] == 1
    assert result["main_system_prompt"] == "test-main-prompt"
    assert result["follow_up_context_prompt"] == "test-followup"
    assert result["qa_history_prompt"] == "test-qa-hist"

    # Should have inserted the config doc + a version doc = 2 inserts
    assert coll.insert_one.await_count == 2
    # The second insert should be the version doc
    version_call = coll.insert_one.call_args_list[1][0][0]
    assert version_call["type"] == "version"
    assert version_call["version"] == 1
    assert version_call["summary"] == "Initial seed from environment"
