"""
Senior session creation E2E tests.

Creates a session scoped to the project from test_02 and stores the session_id
in e2e_state for use by Q&A stage tests.
"""

import logging

import httpx
import pytest

from tests.e2e.conftest import assert_status

logger = logging.getLogger(__name__)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_a_create_senior_session_full(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """Create a full senior session scoped to the E2E project."""
    project_id = e2e_state.get("project_id")
    assert project_id, "e2e_state['project_id'] must be set by test_02"

    payload = {
        "name": "E2E Senior Session — Round 1",
        "user_role": "senior",
        "project_id": project_id,
        "company_info": "Leyton Poland Sp. z o.o., R&D and IP Box tax consultancy",
        "region": "Mazowieckie",
    }
    response = await api_client.post("/api/sessions", json=payload)
    await assert_status(response, 201, "POST /api/sessions (full senior session)")
    data = response.json()

    assert data["user_role"] == "senior", (
        f"Expected user_role='senior', got '{data['user_role']}'"
    )
    assert data["status"] == "active", (
        f"Expected status='active', got '{data['status']}'"
    )

    session_id = data.get("id") or data.get("_id")
    assert session_id, (
        f"Session response must include an id. Got fields: {list(data.keys())}"
    )
    e2e_state["session_id"] = session_id
    logger.info("Created senior session id=%s for project_id=%s", session_id, project_id)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_b_create_senior_session_minimal(
    api_client: httpx.AsyncClient,
) -> None:
    """Create a minimal senior session with only required fields."""
    payload = {"name": "Minimal Senior", "user_role": "senior"}
    response = await api_client.post("/api/sessions", json=payload)
    await assert_status(response, 201, "POST /api/sessions (minimal senior session)")
    data = response.json()
    assert data["user_role"] == "senior", (
        f"Expected user_role='senior', got '{data['user_role']}'"
    )
    session_id = data.get("id") or data.get("_id")
    assert session_id, "Minimal senior session must have an id"
    logger.info("Created minimal senior session id=%s", session_id)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_c_get_created_session(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """Retrieve the created session by ID and verify its fields."""
    session_id = e2e_state.get("session_id")
    assert session_id, "e2e_state['session_id'] must be set by test_a"

    response = await api_client.get(f"/api/sessions/{session_id}")
    await assert_status(response, 200, f"GET /api/sessions/{session_id}")
    data = response.json()

    assert data["user_role"] == "senior", (
        f"Expected user_role='senior', got '{data['user_role']}'"
    )
    assert data["status"] == "active", (
        f"Expected status='active', got '{data['status']}'"
    )
    # Session response has 'session_name' field (from SessionResponse model)
    assert "session_name" in data, (
        f"SessionResponse must include 'session_name' field. Got: {list(data.keys())}"
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_d_list_sessions_includes_new(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """List sessions and verify the new session appears."""
    session_id = e2e_state.get("session_id")
    assert session_id, "e2e_state['session_id'] must be set by test_a"

    response = await api_client.get("/api/sessions")
    await assert_status(response, 200, "GET /api/sessions")
    sessions = response.json()
    assert isinstance(sessions, list), (
        f"Expected list from GET /api/sessions, got {type(sessions)}"
    )

    ids = [str(s.get("id") or s.get("_id")) for s in sessions]
    assert session_id in ids, (
        f"Session id={session_id} not found in sessions list. Found ids: {ids[:10]}"
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_fail1_create_session_invalid_role(
    api_client: httpx.AsyncClient,
) -> None:
    """Creating a session with an invalid user_role must return 422."""
    response = await api_client.post(
        "/api/sessions", json={"name": "Bad Role Session", "user_role": "manager"}
    )
    assert response.status_code == 422, (
        f"Expected HTTP 422 for invalid user_role='manager', got {response.status_code}: "
        f"{response.text[:300]}"
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_fail2_create_session_missing_user_role(
    api_client: httpx.AsyncClient,
) -> None:
    """Creating a session without user_role must return 422."""
    response = await api_client.post(
        "/api/sessions", json={"name": "No Role Session"}
    )
    assert response.status_code == 422, (
        f"Expected HTTP 422 for missing user_role, got {response.status_code}: "
        f"{response.text[:300]}"
    )
