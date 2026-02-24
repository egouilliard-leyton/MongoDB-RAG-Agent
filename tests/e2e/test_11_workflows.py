"""
Workflow template management E2E tests.

Covers the full CRUD lifecycle for workflow templates:
  seed-default (idempotent) -> list -> get -> create -> duplicate ->
  update -> list (verify counts) -> delete (custom + duplicate) ->
  not-found error cases.

Tests run in alphabetical order enforced by the letter prefix.
State shared between tests via the session-scoped e2e_state fixture:
  e2e_state["default_workflow_id"]   — id of the seeded default workflow
  e2e_state["workflow_count_before"] — list length before custom creation
  e2e_state["custom_workflow_id"]    — id of the workflow created in test_d
  e2e_state["duplicate_workflow_id"] — id of the workflow duplicated in test_e
"""

import logging

import httpx
import pytest

from tests.e2e.conftest import assert_status

logger = logging.getLogger(__name__)

# Sentinel ObjectId that is guaranteed not to exist in any test database.
_NONEXISTENT_ID = "000000000000000000000000"


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_a_seed_default_workflow_idempotent(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    POST /api/workflows/seed-default is idempotent.

    Calling it twice must return 200 both times with the same workflow name,
    demonstrating that the operation does not create duplicate records.
    """
    # First call — seeds the workflow if it doesn't exist yet.
    response_1 = await api_client.post("/api/workflows/seed-default")
    await assert_status(response_1, 200, "POST /api/workflows/seed-default (1st call)")
    data_1 = response_1.json()

    workflow_id = data_1.get("id") or data_1.get("_id")
    assert workflow_id, (
        f"seed-default response must include an id field. Got keys: {list(data_1.keys())}"
    )
    assert data_1.get("name"), (
        f"seed-default response must include a non-empty 'name'. Got: {data_1}"
    )

    logger.info("Seeded default workflow: name='%s' id=%s", data_1["name"], workflow_id)

    # Second call — must be fully idempotent: same name, HTTP 200.
    response_2 = await api_client.post("/api/workflows/seed-default")
    await assert_status(response_2, 200, "POST /api/workflows/seed-default (2nd call — idempotency)")
    data_2 = response_2.json()

    assert data_2.get("name") == data_1["name"], (
        f"Idempotent seed must return the same workflow name both times. "
        f"1st='{data_1['name']}', 2nd='{data_2.get('name')}'"
    )

    e2e_state["default_workflow_id"] = workflow_id
    logger.info("Idempotency confirmed: seed-default returned same name on 2nd call")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_b_list_workflows_contains_default(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    GET /api/workflows returns a list containing at least the seeded default.

    Captures the current count so later tests can assert new entries appeared.
    """
    default_workflow_id = e2e_state.get("default_workflow_id")
    assert default_workflow_id, (
        "e2e_state['default_workflow_id'] must be set by test_a_seed_default_workflow_idempotent"
    )

    response = await api_client.get("/api/workflows")
    await assert_status(response, 200, "GET /api/workflows")
    workflows = response.json()

    assert isinstance(workflows, list), (
        f"GET /api/workflows must return a JSON array. Got type: {type(workflows)}"
    )
    assert len(workflows) >= 1, (
        "Workflow list must contain at least the seeded default workflow"
    )

    # Confirm the default workflow appears in the list.
    ids_in_list = [str(w.get("id") or w.get("_id")) for w in workflows]
    assert default_workflow_id in ids_in_list, (
        f"Default workflow id={default_workflow_id} not found in list. "
        f"Found ids: {ids_in_list}"
    )

    e2e_state["workflow_count_before"] = len(workflows)
    logger.info(
        "Workflow list has %d entries; default id=%s confirmed present",
        len(workflows),
        default_workflow_id,
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_c_get_default_workflow(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    GET /api/workflows/{id} returns the full workflow with its stages list.

    Verifies that the detail endpoint responds correctly for the default workflow
    and that the response includes a non-empty stages collection.
    """
    default_workflow_id = e2e_state.get("default_workflow_id")
    assert default_workflow_id, (
        "e2e_state['default_workflow_id'] must be set by test_a_seed_default_workflow_idempotent"
    )

    response = await api_client.get(f"/api/workflows/{default_workflow_id}")
    await assert_status(response, 200, f"GET /api/workflows/{default_workflow_id}")
    data = response.json()

    returned_id = data.get("id") or data.get("_id")
    assert returned_id, (
        f"Workflow detail must include an id field. Got keys: {list(data.keys())}"
    )
    assert data.get("name"), (
        f"Workflow detail must include a non-empty 'name'. Got: {data}"
    )

    stages = data.get("stages")
    assert isinstance(stages, list), (
        f"Workflow detail must include a 'stages' list. Got type: {type(stages)}"
    )
    assert len(stages) > 0, (
        f"Default workflow must have at least one stage. Got: {stages}"
    )

    logger.info(
        "Default workflow '%s' has %d stage(s)", data["name"], len(stages)
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_d_create_custom_workflow(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    POST /api/workflows creates a new workflow template and returns 201.

    Uses a minimal valid body: name, description, and an empty stages list.
    Stores the resulting id for use by later update, duplicate, and delete tests.
    """
    payload = {
        "name": "E2E Test Workflow",
        "description": "Created by E2E tests — safe to delete",
        "stages": [],
    }
    response = await api_client.post("/api/workflows", json=payload)
    await assert_status(response, 201, "POST /api/workflows (create custom)")
    data = response.json()

    custom_workflow_id = data.get("id") or data.get("_id")
    assert custom_workflow_id, (
        f"Created workflow must include an id field. Got keys: {list(data.keys())}"
    )
    assert data.get("name") == payload["name"], (
        f"Expected name='{payload['name']}', got '{data.get('name')}'"
    )

    e2e_state["custom_workflow_id"] = custom_workflow_id
    logger.info("Created custom workflow id=%s", custom_workflow_id)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e_duplicate_workflow(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    POST /api/workflows/{id}/duplicate creates a copy with a new name and returns 201.

    Duplicates the default workflow (which has stages) so the copy is non-trivial.
    Stores the duplicate id for the delete test.
    """
    default_workflow_id = e2e_state.get("default_workflow_id")
    assert default_workflow_id, (
        "e2e_state['default_workflow_id'] must be set by test_a_seed_default_workflow_idempotent"
    )

    # WorkflowDuplicateRequest uses field name "name" (not "new_name").
    payload = {"name": "E2E Duplicate Workflow"}
    response = await api_client.post(
        f"/api/workflows/{default_workflow_id}/duplicate", json=payload
    )
    await assert_status(
        response, 201, f"POST /api/workflows/{default_workflow_id}/duplicate"
    )
    data = response.json()

    duplicate_workflow_id = data.get("id") or data.get("_id")
    assert duplicate_workflow_id, (
        f"Duplicated workflow must include an id field. Got keys: {list(data.keys())}"
    )
    assert data.get("name") == "E2E Duplicate Workflow", (
        f"Duplicated workflow name must match the requested name. "
        f"Expected 'E2E Duplicate Workflow', got '{data.get('name')}'"
    )
    # A duplicate of the default workflow must not itself be the default.
    assert data.get("is_default") is False, (
        f"A duplicated workflow must have is_default=False. Got: {data.get('is_default')}"
    )

    e2e_state["duplicate_workflow_id"] = duplicate_workflow_id
    logger.info(
        "Duplicated workflow from id=%s -> new id=%s, name='%s'",
        default_workflow_id,
        duplicate_workflow_id,
        data.get("name"),
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_f_update_workflow(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    PUT /api/workflows/{id} performs a full replacement update.

    Renames the custom workflow and verifies the new name is persisted.
    """
    custom_workflow_id = e2e_state.get("custom_workflow_id")
    assert custom_workflow_id, (
        "e2e_state['custom_workflow_id'] must be set by test_d_create_custom_workflow"
    )

    updated_payload = {
        "name": "E2E Updated Workflow",
        "description": "Updated by E2E test_f",
        "stages": [],
    }
    response = await api_client.put(
        f"/api/workflows/{custom_workflow_id}", json=updated_payload
    )
    await assert_status(response, 200, f"PUT /api/workflows/{custom_workflow_id}")
    data = response.json()

    assert data.get("name") == "E2E Updated Workflow", (
        f"Expected updated name='E2E Updated Workflow', got '{data.get('name')}'"
    )
    logger.info(
        "Updated workflow id=%s to name='%s'", custom_workflow_id, data.get("name")
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_g_list_after_create_shows_new_workflows(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    GET /api/workflows list grows by at least 2 after creating the custom and duplicate workflows.

    Compares current count against the snapshot taken in test_b.
    """
    workflow_count_before = e2e_state.get("workflow_count_before")
    assert workflow_count_before is not None, (
        "e2e_state['workflow_count_before'] must be set by test_b_list_workflows_contains_default"
    )

    response = await api_client.get("/api/workflows")
    await assert_status(response, 200, "GET /api/workflows (after create + duplicate)")
    workflows = response.json()

    assert isinstance(workflows, list), (
        f"GET /api/workflows must return a JSON array. Got type: {type(workflows)}"
    )
    current_count = len(workflows)
    assert current_count >= workflow_count_before + 2, (
        f"Expected at least {workflow_count_before + 2} workflows after creating custom "
        f"and duplicate, but found {current_count}"
    )
    logger.info(
        "Workflow list grew from %d to %d (delta=%d, expected >=2)",
        workflow_count_before,
        current_count,
        current_count - workflow_count_before,
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_h_delete_custom_workflow(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    DELETE /api/workflows/{id} removes the custom workflow and returns 204.

    Follows up with a GET to confirm the record is truly gone (404).
    """
    custom_workflow_id = e2e_state.get("custom_workflow_id")
    assert custom_workflow_id, (
        "e2e_state['custom_workflow_id'] must be set by test_d_create_custom_workflow"
    )

    # Delete the custom workflow.
    delete_response = await api_client.delete(f"/api/workflows/{custom_workflow_id}")
    await assert_status(
        delete_response, 204, f"DELETE /api/workflows/{custom_workflow_id}"
    )

    # Verify deletion: subsequent GET must return 404.
    get_response = await api_client.get(f"/api/workflows/{custom_workflow_id}")
    await assert_status(
        get_response, 404,
        f"GET /api/workflows/{custom_workflow_id} after deletion must return 404"
    )
    logger.info("Custom workflow id=%s deleted and confirmed absent", custom_workflow_id)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_i_delete_duplicate_workflow(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    DELETE /api/workflows/{id} removes the duplicated workflow and returns 204.

    Cleans up the duplicate created in test_e to leave the database tidy.
    """
    duplicate_workflow_id = e2e_state.get("duplicate_workflow_id")
    assert duplicate_workflow_id, (
        "e2e_state['duplicate_workflow_id'] must be set by test_e_duplicate_workflow"
    )

    delete_response = await api_client.delete(
        f"/api/workflows/{duplicate_workflow_id}"
    )
    await assert_status(
        delete_response, 204, f"DELETE /api/workflows/{duplicate_workflow_id}"
    )
    logger.info(
        "Duplicate workflow id=%s deleted successfully", duplicate_workflow_id
    )


# ---------------------------------------------------------------------------
# Error / failure tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_fail1_get_nonexistent_workflow(
    api_client: httpx.AsyncClient,
) -> None:
    """
    GET /api/workflows/{id} with a valid-format but nonexistent ObjectId must return 404.

    Uses a zero-padded ObjectId that cannot exist in any real database.
    """
    response = await api_client.get(f"/api/workflows/{_NONEXISTENT_ID}")
    await assert_status(
        response, 404,
        f"GET /api/workflows/{_NONEXISTENT_ID} must return 404 for nonexistent workflow"
    )
    logger.info(
        "GET nonexistent workflow correctly returned 404: %s",
        response.text[:200],
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_fail2_delete_nonexistent_workflow(
    api_client: httpx.AsyncClient,
) -> None:
    """
    DELETE /api/workflows/{id} with a nonexistent ObjectId must return 404.

    Verifies the API does not silently succeed on missing resources.
    """
    response = await api_client.delete(f"/api/workflows/{_NONEXISTENT_ID}")
    await assert_status(
        response, 404,
        f"DELETE /api/workflows/{_NONEXISTENT_ID} must return 404 for nonexistent workflow"
    )
    logger.info(
        "DELETE nonexistent workflow correctly returned 404: %s",
        response.text[:200],
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_fail3_duplicate_nonexistent_workflow(
    api_client: httpx.AsyncClient,
) -> None:
    """
    POST /api/workflows/{id}/duplicate with a nonexistent ObjectId must return 404.

    The service must not create a copy when the source template does not exist.
    """
    payload = {"name": "Should Fail — Source Nonexistent"}
    response = await api_client.post(
        f"/api/workflows/{_NONEXISTENT_ID}/duplicate", json=payload
    )
    await assert_status(
        response, 404,
        f"POST /api/workflows/{_NONEXISTENT_ID}/duplicate must return 404"
    )
    logger.info(
        "Duplicate of nonexistent workflow correctly returned 404: %s",
        response.text[:200],
    )
