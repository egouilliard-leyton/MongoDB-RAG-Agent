"""Unit tests for WorkflowService."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime
from bson import ObjectId
from fastapi import HTTPException

from src.services.workflow_service import (
    WorkflowService,
    DEFAULT_STAGES,
    DEFAULT_TEMPLATE_NAME,
    DEFAULT_TEMPLATE_DESCRIPTION,
    DEFAULT_QA_SESSION_STAGES,
    DEFAULT_QA_PAIR_STAGES,
    DEFAULT_AGENTIC_STAGES,
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


# ---------------------------------------------------------------------------
# New tests: multi-workflow-type backend logic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_seed_default_for_type_creates_all_types(service):
    """seed_default_for_type should insert a new default for each of the 4 types."""
    types = ["project", "qa_session", "qa_pair", "agentic"]
    insert_one_mock = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))

    for workflow_type in types:
        # Each call: find_one returns None (no existing default), insert_one creates it
        template_coll = _make_collection_mock()
        template_coll.find_one = AsyncMock(return_value=None)
        inserted_id = ObjectId()
        template_coll.insert_one = insert_one_mock

        service.db.__getitem__ = MagicMock(return_value=template_coll)
        result = await service.seed_default_for_type(workflow_type)

        assert result["workflow_type"] == workflow_type, (
            f"Expected workflow_type={workflow_type!r}, got {result['workflow_type']!r}"
        )
        assert result["is_default"] is True, (
            f"Expected is_default=True for type {workflow_type!r}"
        )

    # insert_one should have been called exactly once per type (4 times total)
    assert insert_one_mock.await_count == 4, (
        f"Expected insert_one to be called 4 times, got {insert_one_mock.await_count}"
    )


@pytest.mark.asyncio
async def test_seed_default_for_type_is_idempotent(service):
    """seed_default_for_type should return existing default without inserting."""
    existing_id = ObjectId()
    now = datetime.utcnow()
    existing_doc = {
        "_id": existing_id,
        "name": "existing",
        "description": "",
        "is_default": True,
        "workflow_type": "qa_session",
        "stages": [],
        "created_at": now,
        "updated_at": now,
    }

    template_coll = _make_collection_mock()
    template_coll.find_one = AsyncMock(return_value=existing_doc)
    service.db.__getitem__ = MagicMock(return_value=template_coll)

    result = await service.seed_default_for_type("qa_session")

    template_coll.insert_one.assert_not_awaited()
    assert result["name"] == "existing"
    assert result["id"] == str(existing_id)


@pytest.mark.asyncio
async def test_list_by_type_project_includes_legacy_docs(service):
    """list_by_type("project") should pass a query with $or to handle legacy docs."""

    async def _empty_async_iter():
        return
        yield  # make it an async generator

    cursor_mock = MagicMock()
    cursor_mock.sort = MagicMock(return_value=cursor_mock)
    cursor_mock.__aiter__ = lambda self: _empty_async_iter().__aiter__()

    coll = MagicMock()
    coll.find = MagicMock(return_value=cursor_mock)
    service.db.__getitem__ = MagicMock(return_value=coll)

    await service.list_by_type("project")

    coll.find.assert_called_once()
    query_used = coll.find.call_args[0][0]
    assert "$or" in query_used, (
        "Expected '$or' key in query for 'project' type to include legacy docs"
    )
    or_clauses = query_used["$or"]
    # Should include both {"workflow_type": "project"} and {"workflow_type": {"$exists": False}}
    assert {"workflow_type": "project"} in or_clauses
    assert {"workflow_type": {"$exists": False}} in or_clauses


@pytest.mark.asyncio
async def test_list_by_type_excludes_other_types(service):
    """list_by_type("qa_session") should use a simple equality query."""

    async def _empty_async_iter():
        return
        yield

    cursor_mock = MagicMock()
    cursor_mock.sort = MagicMock(return_value=cursor_mock)
    cursor_mock.__aiter__ = lambda self: _empty_async_iter().__aiter__()

    coll = MagicMock()
    coll.find = MagicMock(return_value=cursor_mock)
    service.db.__getitem__ = MagicMock(return_value=coll)

    await service.list_by_type("qa_session")

    coll.find.assert_called_once()
    query_used = coll.find.call_args[0][0]
    assert query_used == {"workflow_type": "qa_session"}, (
        f"Expected simple equality query, got {query_used!r}"
    )


@pytest.mark.asyncio
async def test_is_default_scoped_by_type(service):
    """create() with is_default=True should scope update_many to workflow_type."""
    template_coll = _make_collection_mock()
    new_id = ObjectId()
    template_coll.insert_one = AsyncMock(return_value=MagicMock(inserted_id=new_id))
    service.db.__getitem__ = MagicMock(return_value=template_coll)

    await service.create({
        "name": "test",
        "is_default": True,
        "workflow_type": "qa_session",
        "stages": [],
    })

    template_coll.update_many.assert_awaited_once()
    filter_used = template_coll.update_many.call_args[0][0]
    # The filter must include workflow_type scoping — either directly or via $or
    # For non-"project" types, the filter should be:
    # {"is_default": True, "workflow_type": "qa_session"}
    assert filter_used.get("workflow_type") == "qa_session", (
        f"Expected update_many filter to scope by workflow_type='qa_session', got {filter_used!r}"
    )
    assert filter_used.get("is_default") is True


# ---------------------------------------------------------------------------
# New tests: DEFAULT_STAGES count, integrity, and migration logic
# ---------------------------------------------------------------------------


def test_default_stages_count():
    """DEFAULT_STAGES must have exactly 15 real pipeline stages."""
    from src.services.workflow_service import DEFAULT_STAGES
    assert len(DEFAULT_STAGES) == 15


def test_default_stages_ids_match_fallback():
    """All FALLBACK_STAGES keys must be present in DEFAULT_STAGES."""
    from src.services.project_stages import FALLBACK_STAGES
    from src.services.workflow_service import DEFAULT_STAGES
    default_ids = {s["id"] for s in DEFAULT_STAGES}
    missing = set(FALLBACK_STAGES.keys()) - default_ids
    assert not missing, f"Missing stage IDs: {missing}"


def test_default_stages_transitions_valid():
    """All transitions in DEFAULT_STAGES must reference valid stage IDs."""
    from src.services.workflow_service import DEFAULT_STAGES
    ids = {s["id"] for s in DEFAULT_STAGES}
    for stage in DEFAULT_STAGES:
        for t in stage["transitions"]:
            assert t["to_stage_id"] in ids, (
                f"Broken transition in stage '{stage['id']}': -> '{t['to_stage_id']}'"
            )


def test_default_stages_order_sequential():
    """Stage order values must be sequential starting from 0."""
    from src.services.workflow_service import DEFAULT_STAGES
    orders = sorted(s["order"] for s in DEFAULT_STAGES)
    assert orders == list(range(len(DEFAULT_STAGES)))


@pytest.mark.asyncio
async def test_seed_default_for_type_migrates_outdated_project_template():
    """seed_default_for_type('project') must replace a stale 4-stage placeholder."""
    from unittest.mock import AsyncMock, MagicMock
    from bson import ObjectId
    from datetime import datetime
    from src.services.workflow_service import WorkflowService

    # Build a fake Settings object
    settings = MagicMock()
    settings.mongodb_uri = "mongodb://localhost"
    settings.mongodb_database = "test_db"
    settings.mongodb_collection_workflow_templates = "workflow_templates"
    settings.mongodb_collection_projects = "projects"

    service = WorkflowService(settings)

    # Inject a mock db
    old_id = ObjectId()
    stale_doc = {
        "_id": old_id,
        "name": "Old Template",
        "description": "",
        "is_default": True,
        "workflow_type": "project",
        "stages": [
            {"id": "intake", "label": "Intake"},
            {"id": "analysis", "label": "Analysis"},
            {"id": "review", "label": "Review"},
            {"id": "complete", "label": "Complete"},
        ],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    new_id = ObjectId()
    new_doc = {**stale_doc, "_id": new_id, "stages": [{"id": "prep_docs", "label": "Prepare documents"}]}

    mock_collection = MagicMock()
    mock_collection.find_one = AsyncMock(side_effect=[stale_doc, new_doc])
    mock_collection.delete_one = AsyncMock()
    mock_collection.insert_one = AsyncMock(return_value=MagicMock(inserted_id=new_id))

    service.db = {settings.mongodb_collection_workflow_templates: mock_collection}

    result = await service.seed_default_for_type("project")

    # delete_one must have been called with the stale doc's _id
    mock_collection.delete_one.assert_called_once_with({"_id": old_id})
    # insert_one must have been called (creating fresh template)
    mock_collection.insert_one.assert_called_once()
    # inserted doc must have workflow_type="project"
    inserted = mock_collection.insert_one.call_args[0][0]
    assert inserted["workflow_type"] == "project"
    assert inserted["is_default"] is True
