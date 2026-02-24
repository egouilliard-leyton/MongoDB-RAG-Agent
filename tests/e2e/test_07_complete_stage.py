"""
Complete stage E2E tests: session outcome, export, follow-up verification.

Tests:
  - Verify project stage advanced
  - Check stage-options at current stage
  - Mark session outcome as successful
  - Export session as markdown
  - Verify follow-up session links back to parent
  - Failure cases (advance past terminal, invalid export format)

NOTE: The project stage machine (project_stages.py) may not be at a "complete"
terminal stage at this point — it depends on how many 'next' transitions were
fired in tests 04/05/06. The workflow Q&A stages (intake->analysis->review->complete)
are separate. This test file focuses on session-level completion and export.
"""

import logging

import httpx
import pytest

from tests.e2e.conftest import assert_status

logger = logging.getLogger(__name__)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_a_verify_complete_stage(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """Verify the project stage and log its current key."""
    project_id = e2e_state.get("project_id")
    assert project_id, "e2e_state['project_id'] must be set by test_02"

    response = await api_client.get(f"/api/projects/{project_id}")
    await assert_status(response, 200, f"GET /api/projects/{project_id}")
    data = response.json()

    stage = data.get("stage", {})
    stage_key = stage.get("key")
    assert stage_key, "Project must have a stage.key"
    logger.info("Project stage at complete test entry: key=%s", stage_key)

    # Verify session exists and is active
    session_id = e2e_state.get("session_id")
    assert session_id, "e2e_state['session_id'] must be set by test_03"
    session_resp = await api_client.get(f"/api/sessions/{session_id}")
    await assert_status(session_resp, 200, f"GET /api/sessions/{session_id}")
    session = session_resp.json()
    assert session["status"] == "active", (
        f"Session should still be active at complete stage, "
        f"got status='{session['status']}'"
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_b_stage_options_check(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """Get stage options and log available transitions at the current project stage."""
    project_id = e2e_state.get("project_id")
    assert project_id, "e2e_state['project_id'] must be set by test_02"

    response = await api_client.get(f"/api/projects/{project_id}/stage-options")
    await assert_status(response, 200, f"GET /api/projects/{project_id}/stage-options")
    options = response.json()

    next_actions = options.get("next_actions", [])
    rollback_targets = options.get("rollback_targets", [])
    logger.info(
        "Stage options: next_actions=%s, rollback_targets=%s",
        next_actions,
        rollback_targets,
    )
    # Log whether transitions exist or if we're at a terminal-ish stage
    print(
        f"Stage options: {len(next_actions)} transitions available, "
        f"{len(rollback_targets)} rollback targets"
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_c_mark_session_outcome_successful(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """Mark the session outcome as 'successful' and verify via GET."""
    session_id = e2e_state.get("session_id")
    assert session_id, "e2e_state['session_id'] must be set by test_03"

    response = await api_client.put(
        f"/api/sessions/{session_id}/outcome",
        json={"outcome": "successful", "determined_by": "user"},
    )
    await assert_status(response, 200, f"PUT /api/sessions/{session_id}/outcome")

    # Verify via GET
    session_resp = await api_client.get(f"/api/sessions/{session_id}")
    await assert_status(session_resp, 200, f"GET /api/sessions/{session_id}")
    session = session_resp.json()
    assert session.get("outcome_status") == "successful", (
        f"Expected outcome_status='successful' after marking, "
        f"got '{session.get('outcome_status')}'"
    )
    logger.info("Session %s outcome marked as 'successful'", session_id)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_d_export_session_markdown(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    Export the session as markdown using a query parameter.

    The export endpoint is:
        POST /api/sessions/{session_id}/export?format=markdown
    The format is a QUERY PARAMETER, not a request body field.
    """
    session_id = e2e_state.get("session_id")
    assert session_id, "e2e_state['session_id'] must be set by test_03"

    response = await api_client.post(
        f"/api/sessions/{session_id}/export",
        params={"format": "markdown"},
    )
    assert response.status_code in (200, 201), (
        f"Markdown export failed: Expected 200/201, got {response.status_code}: "
        f"{response.text[:300]}"
    )

    # Verify non-empty content was returned
    content = response.content
    assert content, "Export must return non-empty content"
    logger.info(
        "Exported session %s as markdown; content length=%d bytes",
        session_id,
        len(content),
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e_follow_up_session_context(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """Verify the follow-up session links back to the parent session."""
    follow_up_id = e2e_state.get("follow_up_session_id")
    assert follow_up_id, (
        "e2e_state['follow_up_session_id'] must be set by test_05 "
        "(test_d_create_follow_up_session)"
    )
    session_id = e2e_state.get("session_id")
    assert session_id, "e2e_state['session_id'] must be set by test_03"

    response = await api_client.get(f"/api/sessions/{follow_up_id}")
    await assert_status(response, 200, f"GET /api/sessions/{follow_up_id}")
    data = response.json()

    meta = data.get("metadata", {})
    parent_session_id = meta.get("parent_session_id")
    assert parent_session_id == session_id, (
        f"Follow-up session must link to parent. "
        f"Expected parent_session_id='{session_id}', "
        f"got '{parent_session_id}'. Metadata: {meta}"
    )
    round_number = meta.get("round_number", 0)
    assert round_number >= 2, (
        f"Follow-up round_number must be >= 2, got {round_number}"
    )
    logger.info(
        "Follow-up session %s links to parent %s, round_number=%d",
        follow_up_id,
        session_id,
        round_number,
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_fail1_try_advancing_past_terminal_stage(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    Attempt to fire an invalid event from a project stage machine terminal state.

    If the project is at a terminal stage (end_no_appeal, end_refund), firing any
    event should return 400/422. If not at terminal yet, this test fires an invalid
    event name to confirm validation.
    """
    project_id = e2e_state.get("project_id")
    assert project_id, "e2e_state['project_id'] must be set by test_02"

    # Get current stage to determine what to test
    proj_resp = await api_client.get(f"/api/projects/{project_id}")
    await assert_status(proj_resp, 200, f"GET /api/projects/{project_id}")
    current_stage = proj_resp.json().get("stage", {}).get("key", "")

    terminal_stages = {"end_no_appeal", "end_refund"}

    if current_stage in terminal_stages:
        # Project is at a terminal stage — any event should fail
        response = await api_client.put(
            f"/api/projects/{project_id}/stage",
            json={"event": "next", "to_stage": "submit_first_instance"},
        )
        assert response.status_code in (400, 422), (
            f"Terminal stage '{current_stage}' should reject 'next' event, "
            f"got {response.status_code}: {response.text[:300]}"
        )
        logger.info(
            "Confirmed: terminal stage '%s' rejects 'next' event with %d",
            current_stage,
            response.status_code,
        )
    else:
        # Not at terminal — try an invalid event name
        response = await api_client.put(
            f"/api/projects/{project_id}/stage",
            json={"event": "invalid_event_xyz", "to_stage": "nsa_decision"},
        )
        assert response.status_code in (400, 422), (
            f"Invalid event from stage '{current_stage}' should return 400/422, "
            f"got {response.status_code}: {response.text[:300]}"
        )
        logger.info(
            "Confirmed: invalid event from stage '%s' returns %d",
            current_stage,
            response.status_code,
        )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_fail2_export_invalid_format(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    Export with an unsupported format must return 400 or 422.

    The export endpoint only supports: markdown, pdf, docx.
    Sending 'xml' should be rejected.
    """
    session_id = e2e_state.get("session_id")
    assert session_id, "e2e_state['session_id'] must be set by test_03"

    response = await api_client.post(
        f"/api/sessions/{session_id}/export",
        params={"format": "xml"},
    )
    assert response.status_code in (400, 422), (
        f"Invalid export format 'xml' should return 400/422, "
        f"got {response.status_code}: {response.text[:300]}"
    )
    logger.info(
        "Invalid export format 'xml' correctly rejected with status %d",
        response.status_code,
    )
