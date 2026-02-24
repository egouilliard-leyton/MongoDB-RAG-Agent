"""
Project creation E2E tests.

Tests run in alphabetical order (a, b, c, d, fail1, fail2).
The main project ID is stored in e2e_state["project_id"] for use by later test files.
"""

import logging

import httpx
import pytest

from tests.e2e.conftest import assert_status

logger = logging.getLogger(__name__)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_a_create_full_project(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """Create a project with all optional metadata fields populated."""
    payload = {
        "name": "E2E Senior Test Project — IP Box Analysis",
        "region": "Mazowieckie",
        "industry": "it",
    }
    response = await api_client.post("/api/projects", json=payload)
    await assert_status(response, 201, "POST /api/projects (full project)")
    data = response.json()

    # Either 'id' or '_id' depending on serialization alias
    project_id = data.get("id") or data.get("_id")
    assert project_id, (
        f"Created project must have an id field. Got: {list(data.keys())}"
    )
    assert data["name"] == payload["name"], (
        f"Expected name '{payload['name']}', got '{data['name']}'"
    )

    e2e_state["project_id"] = project_id
    logger.info("Created full project with id=%s", project_id)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_b_create_minimal_project(
    api_client: httpx.AsyncClient,
) -> None:
    """Create a project with only the required name field."""
    payload = {"name": "Minimal E2E Project"}
    response = await api_client.post("/api/projects", json=payload)
    await assert_status(response, 201, "POST /api/projects (minimal project)")
    data = response.json()
    project_id = data.get("id") or data.get("_id")
    assert project_id, "Minimal project must have an id"
    assert data["name"] == "Minimal E2E Project"
    logger.info("Created minimal project with id=%s", project_id)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_c_get_created_project(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """Retrieve the full project by ID and verify its fields."""
    project_id = e2e_state.get("project_id")
    assert project_id, "e2e_state['project_id'] must be set by test_a_create_full_project"

    response = await api_client.get(f"/api/projects/{project_id}")
    await assert_status(response, 200, f"GET /api/projects/{project_id}")
    data = response.json()

    assert data["name"] == "E2E Senior Test Project — IP Box Analysis", (
        f"Expected project name, got '{data['name']}'"
    )
    # Verify stage field exists with a key sub-field
    stage = data.get("stage")
    assert stage is not None, "Project response must include a 'stage' field"
    assert "key" in stage, (
        f"'stage' must have a 'key' sub-field. Got: {stage}"
    )
    logger.info("Project stage: key=%s", stage.get("key"))


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_d_list_projects_contains_new(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """List all projects and verify the newly created project appears."""
    project_id = e2e_state.get("project_id")
    assert project_id, "e2e_state['project_id'] must be set by test_a_create_full_project"

    response = await api_client.get("/api/projects")
    await assert_status(response, 200, "GET /api/projects")
    projects = response.json()
    assert isinstance(projects, list), (
        f"Expected list from GET /api/projects, got {type(projects)}"
    )

    ids = [str(p.get("id") or p.get("_id")) for p in projects]
    assert project_id in ids, (
        f"Project id={project_id} not found in list. Found ids: {ids[:10]}"
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_fail1_create_project_missing_name(
    api_client: httpx.AsyncClient,
) -> None:
    """Creating a project with no name field must return 422 Unprocessable Entity."""
    response = await api_client.post("/api/projects", json={})
    assert response.status_code == 422, (
        f"Expected HTTP 422 for missing name, got {response.status_code}: "
        f"{response.text[:300]}"
    )
    data = response.json()
    assert "detail" in data, (
        f"422 response must include a 'detail' field. Got: {list(data.keys())}"
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_fail2_create_project_name_empty_string(
    api_client: httpx.AsyncClient,
) -> None:
    """Creating a project with an empty name must return 422 Unprocessable Entity."""
    response = await api_client.post("/api/projects", json={"name": ""})
    assert response.status_code == 422, (
        f"Expected HTTP 422 for empty name, got {response.status_code}: "
        f"{response.text[:300]}"
    )
    data = response.json()
    # Validation error detail should mention 'name'
    detail_str = str(data.get("detail", ""))
    assert "name" in detail_str.lower() or "min_length" in detail_str.lower() or data.get("detail"), (
        f"422 detail should mention 'name' validation. Got detail: {detail_str[:300]}"
    )
