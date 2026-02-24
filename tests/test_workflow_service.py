"""Unit tests for WorkflowService."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from bson import ObjectId
from fastapi import HTTPException

from src.services.workflow_service import (
    WorkflowService,
    DEFAULT_STAGES,
    DEFAULT_TEMPLATE_NAME,
    DEFAULT_TEMPLATE_DESCRIPTION,
)


@pytest.fixture
def mock_settings():
    """Create a mock Settings object."""
    settings = MagicMock()
    settings.mongodb_uri = "mongodb://localhost:27017"
    settings.mongodb_database = "test_db"
    settings.mongodb_collection_workflow_templates = "workflow_templates"
    settings.mongodb_collection_projects = "projects"
    return settings


@pytest.fixture
def service(mock_settings):
    """Create a WorkflowService with mocked DB layer."""
    svc = WorkflowService(mock_settings)
    svc.mongo_client = MagicMock()
    svc.db = MagicMock()
    return svc


def _make_collection_mock():
    """Create a mock collection with common async methods."""
    coll = MagicMock()
    coll.find_one = AsyncMock(return_value=None)
    coll.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))
    coll.update_one = AsyncMock()
    coll.update_many = AsyncMock()
    coll.delete_one = AsyncMock()
    coll.count_documents = AsyncMock(return_value=0)
    return coll


@pytest.mark.asyncio
async def test_seed_default_creates_template(service):
    """seed_default should insert a default template when none exists."""
    template_coll = _make_collection_mock()
    template_coll.find_one = AsyncMock(return_value=None)
    new_id = ObjectId()
    template_coll.insert_one = AsyncMock(return_value=MagicMock(inserted_id=new_id))

    service.db.__getitem__ = MagicMock(return_value=template_coll)

    result = await service.seed_default()

    template_coll.insert_one.assert_awaited_once()
    inserted_doc = template_coll.insert_one.call_args[0][0]
    assert inserted_doc["name"] == DEFAULT_TEMPLATE_NAME
    assert inserted_doc["description"] == DEFAULT_TEMPLATE_DESCRIPTION
    assert inserted_doc["is_default"] is True
    assert len(inserted_doc["stages"]) == len(DEFAULT_STAGES)
    assert len(inserted_doc["stages"]) >= 2

    # Result should have string id (from _doc_to_api)
    assert "id" in result
    assert result["is_default"] is True


@pytest.mark.asyncio
async def test_seed_default_idempotent(service):
    """seed_default should return existing default without inserting."""
    existing_id = ObjectId()
    existing_doc = {
        "_id": existing_id,
        "name": DEFAULT_TEMPLATE_NAME,
        "description": DEFAULT_TEMPLATE_DESCRIPTION,
        "is_default": True,
        "stages": DEFAULT_STAGES,
        "created_at": datetime(2026, 1, 1),
        "updated_at": datetime(2026, 1, 1),
    }

    template_coll = _make_collection_mock()
    template_coll.find_one = AsyncMock(return_value=existing_doc)
    service.db.__getitem__ = MagicMock(return_value=template_coll)

    result = await service.seed_default()

    template_coll.insert_one.assert_not_awaited()
    assert result["name"] == DEFAULT_TEMPLATE_NAME
    assert result["id"] == str(existing_id)


@pytest.mark.asyncio
async def test_list_templates_returns_list_items(service):
    """list_templates should return docs with stage_count field."""
    docs = [
        {
            "_id": ObjectId(),
            "name": "Template A",
            "description": "Desc A",
            "is_default": True,
            "stages": [{"id": "s1"}, {"id": "s2"}, {"id": "s3"}],
            "created_at": datetime(2026, 2, 20),
            "updated_at": datetime(2026, 2, 20),
        },
        {
            "_id": ObjectId(),
            "name": "Template B",
            "description": "Desc B",
            "is_default": False,
            "stages": [{"id": "s1"}],
            "created_at": datetime(2026, 2, 21),
            "updated_at": datetime(2026, 2, 21),
        },
    ]

    async def _async_iter(items):
        for item in items:
            yield item

    cursor_mock = MagicMock()
    cursor_mock.sort = MagicMock(return_value=cursor_mock)
    cursor_mock.__aiter__ = lambda self: _async_iter(docs).__aiter__()

    coll = MagicMock()
    coll.find = MagicMock(return_value=cursor_mock)
    service.db.__getitem__ = MagicMock(return_value=coll)

    result = await service.list_templates()

    assert len(result) == 2
    assert result[0]["stage_count"] == 3
    assert result[1]["stage_count"] == 1
    assert "id" in result[0]
    assert "_id" not in result[0]


@pytest.mark.asyncio
async def test_get_template_not_found_raises_404(service):
    """get() should raise HTTPException 404 when template not found."""
    template_coll = _make_collection_mock()
    template_coll.find_one = AsyncMock(return_value=None)
    service.db.__getitem__ = MagicMock(return_value=template_coll)

    valid_id = str(ObjectId())

    with pytest.raises(HTTPException) as exc_info:
        await service.get(valid_id)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_template_invalid_id_raises_404(service):
    """get() should raise HTTPException 404 when ID is not a valid ObjectId."""
    with pytest.raises(HTTPException) as exc_info:
        await service.get("not-a-valid-id")

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_default_raises_409(service):
    """Deleting the default template should raise HTTPException 409."""
    template_id = ObjectId()
    default_doc = {
        "_id": template_id,
        "name": "Default",
        "is_default": True,
        "stages": [],
    }

    template_coll = _make_collection_mock()
    template_coll.find_one = AsyncMock(return_value=default_doc)
    service.db.__getitem__ = MagicMock(return_value=template_coll)

    with pytest.raises(HTTPException) as exc_info:
        await service.delete(str(template_id))

    assert exc_info.value.status_code == 409
    assert "default" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_delete_referenced_by_projects_raises_409(service):
    """Deleting a template referenced by projects should raise 409."""
    template_id = ObjectId()
    non_default_doc = {
        "_id": template_id,
        "name": "Custom",
        "is_default": False,
        "stages": [],
    }

    template_coll = _make_collection_mock()
    template_coll.find_one = AsyncMock(return_value=non_default_doc)

    projects_coll = _make_collection_mock()
    projects_coll.count_documents = AsyncMock(return_value=3)

    def _get_collection(name):
        if name == "projects":
            return projects_coll
        return template_coll

    service.db.__getitem__ = MagicMock(side_effect=_get_collection)

    with pytest.raises(HTTPException) as exc_info:
        await service.delete(str(template_id))

    assert exc_info.value.status_code == 409
    assert "3 project(s)" in exc_info.value.detail


@pytest.mark.asyncio
async def test_duplicate_creates_new_template(service):
    """duplicate() should create a new template that is not default."""
    source_id = ObjectId()
    source_doc = {
        "_id": source_id,
        "name": "Original Template",
        "description": "Original desc",
        "is_default": True,
        "stages": [
            {"id": "intake", "label": "Intake", "order": 0},
            {"id": "review", "label": "Review", "order": 1},
        ],
        "created_at": datetime(2026, 1, 1),
        "updated_at": datetime(2026, 1, 1),
    }

    new_id = ObjectId()
    template_coll = _make_collection_mock()
    template_coll.find_one = AsyncMock(return_value=source_doc)
    template_coll.insert_one = AsyncMock(return_value=MagicMock(inserted_id=new_id))
    service.db.__getitem__ = MagicMock(return_value=template_coll)

    result = await service.duplicate(str(source_id))

    template_coll.insert_one.assert_awaited_once()
    inserted = template_coll.insert_one.call_args[0][0]
    assert inserted["is_default"] is False
    assert inserted["name"] == "Copy of Original Template"
    assert len(inserted["stages"]) == 2

    assert result["id"] == str(new_id)
    assert result["is_default"] is False


@pytest.mark.asyncio
async def test_duplicate_with_custom_name(service):
    """duplicate() should use the provided name."""
    source_id = ObjectId()
    source_doc = {
        "_id": source_id,
        "name": "Original",
        "description": "",
        "is_default": False,
        "stages": [],
        "created_at": datetime(2026, 1, 1),
        "updated_at": datetime(2026, 1, 1),
    }

    template_coll = _make_collection_mock()
    template_coll.find_one = AsyncMock(return_value=source_doc)
    template_coll.insert_one = AsyncMock(
        return_value=MagicMock(inserted_id=ObjectId())
    )
    service.db.__getitem__ = MagicMock(return_value=template_coll)

    result = await service.duplicate(str(source_id), new_name="My Custom Copy")

    inserted = template_coll.insert_one.call_args[0][0]
    assert inserted["name"] == "My Custom Copy"


@pytest.mark.asyncio
async def test_get_resolved_stage_config_applies_inheritance(service):
    """Resolved config should prefer stage override over global defaults."""
    workflow_id = str(ObjectId())
    template_doc = {
        "_id": ObjectId(workflow_id),
        "name": "Test",
        "stages": [
            {
                "id": "analysis",
                "label": "Analysis",
                "order": 1,
                "config": {
                    "system_prompt_append": "Focus on legal analysis.",
                    "search_params": {
                        "match_count": 15,
                        "rrf_k": None,
                        "qa_history_match_count": None,
                    },
                    "metadata_fields": [],
                    "auto_advance": False,
                },
                "transitions": [],
            }
        ],
        "created_at": datetime(2026, 1, 1),
        "updated_at": datetime(2026, 1, 1),
    }

    template_coll = _make_collection_mock()
    template_coll.find_one = AsyncMock(return_value=template_doc)
    service.db.__getitem__ = MagicMock(return_value=template_coll)

    global_settings = {
        "main_system_prompt": "You are a helpful assistant.",
        "default_match_count": 10,
        "rrf_k_constant": 60,
        "qa_history_match_count": 3,
        "stage_defaults": {
            "system_prompt_append": None,
            "search_params": {
                "match_count": None,
                "rrf_k": None,
                "qa_history_match_count": None,
            },
        },
    }

    result = await service.get_resolved_stage_config(
        workflow_id, "analysis", global_settings
    )

    # Stage override: match_count=15 should win over global default_match_count=10
    assert result["match_count"] == 15
    # No stage/default override for rrf_k, should fall back to global
    assert result["rrf_k"] == 60
    # No stage/default override for qa_history, should fall back to global
    assert result["qa_history_match_count"] == 3
    # Prompt should be main + stage append
    assert "You are a helpful assistant." in result["final_system_prompt"]
    assert "Focus on legal analysis." in result["final_system_prompt"]


@pytest.mark.asyncio
async def test_get_resolved_stage_config_falls_back_to_global(service):
    """When stage has no overrides, resolved config should use global values."""
    workflow_id = str(ObjectId())
    template_doc = {
        "_id": ObjectId(workflow_id),
        "name": "Test",
        "stages": [
            {
                "id": "intake",
                "label": "Intake",
                "order": 0,
                "config": {
                    "system_prompt_append": None,
                    "search_params": {
                        "match_count": None,
                        "rrf_k": None,
                        "qa_history_match_count": None,
                    },
                    "metadata_fields": [],
                    "auto_advance": False,
                },
                "transitions": [],
            }
        ],
        "created_at": datetime(2026, 1, 1),
        "updated_at": datetime(2026, 1, 1),
    }

    template_coll = _make_collection_mock()
    template_coll.find_one = AsyncMock(return_value=template_doc)
    service.db.__getitem__ = MagicMock(return_value=template_coll)

    global_settings = {
        "main_system_prompt": "Base prompt.",
        "default_match_count": 10,
        "rrf_k_constant": 60,
        "qa_history_match_count": 3,
        "stage_defaults": {
            "system_prompt_append": None,
            "search_params": {
                "match_count": None,
                "rrf_k": None,
                "qa_history_match_count": None,
            },
        },
    }

    result = await service.get_resolved_stage_config(
        workflow_id, "intake", global_settings
    )

    assert result["match_count"] == 10
    assert result["rrf_k"] == 60
    assert result["qa_history_match_count"] == 3
    assert result["final_system_prompt"] == "Base prompt."
