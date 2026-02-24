"""
Stage rollback E2E tests.

Tests the rollback capability of the project stage machine.
A dedicated project is created in test_a_setup_project_for_rollback and
stored in e2e_state["rollback_project_id"]. All subsequent tests in this
file operate on that project.

Rollback API contract:
  PUT /api/projects/{id}/stage
      body: {"to_stage": "<stage_key>", "event": "<any>", "mode": "rollback"}

Stage options API:
  GET /api/projects/{id}/stage-options
      returns: {"next_actions": [...], "rollback_targets": ["await_response", ...]}
      rollback_targets: unique visited stages in reverse order, excluding current.

Stage history is stored in project.stage_history as a list of dicts:
  {"from": str|None, "to": str, "event": str, "at": str, "note": str|None, "by": str|None}
  A rollback entry has event starting with "rollback:".
"""

import logging

import httpx
import pytest

from tests.e2e.conftest import assert_status

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

# Transitions used to advance the rollback test project to inquiry_check
# Each tuple is (event, expected_to_stage)
ROLLBACK_SETUP_PATH: list[tuple[str, str]] = [
    ("next", "submit_first_instance"),
    ("next", "await_response"),
    ("next", "inquiry_check"),
]


async def _advance_stage(
    client: httpx.AsyncClient,
    project_id: str,
    event: str,
    expected_stage: str,
) -> dict:
    """
    Advance the project stage by one transition and assert the resulting stage.

    Resolves the correct to_stage from stage-options before calling PUT, so
    the test is not hard-coded to a specific to_stage value.

    Args:
        client: The async HTTP client.
        project_id: MongoDB ObjectId string of the project to advance.
        event: Transition event name (e.g. "next", "no", "negative").
        expected_stage: The stage key expected after this transition.

    Returns:
        Updated project dict returned by the API.
    """
    options_resp = await client.get(f"/api/projects/{project_id}/stage-options")
    assert options_resp.status_code == 200, (
        f"GET stage-options for project {project_id} failed: "
        f"{options_resp.status_code} {options_resp.text[:300]}"
    )
    options = options_resp.json()
    next_actions = options.get("next_actions", [])

    matching = next((a for a in next_actions if a["event"] == event), None)
    assert matching is not None, (
        f"Event '{event}' not found in next_actions: {next_actions}. "
        f"Project id={project_id}, full options: {options}"
    )

    to_stage = matching["to"]
    response = await client.put(
        f"/api/projects/{project_id}/stage",
        json={"event": event, "to_stage": to_stage},
    )
    assert response.status_code in (200, 201), (
        f"Stage advance event='{event}' to_stage='{to_stage}' failed: "
        f"{response.status_code} {response.text[:300]}"
    )
    data = response.json()
    actual_stage = data.get("stage", {}).get("key")
    assert actual_stage == expected_stage, (
        f"After event='{event}': expected stage='{expected_stage}', "
        f"got '{actual_stage}'. Project id={project_id}"
    )
    logger.info(
        "Project %s: event='%s' -> stage='%s'", project_id, event, actual_stage
    )
    return data


async def _rollback_stage(
    client: httpx.AsyncClient,
    project_id: str,
    to_stage: str,
) -> dict:
    """
    Perform a rollback to a given stage key via the rollback mode.

    Args:
        client: The async HTTP client.
        project_id: MongoDB ObjectId string of the project to roll back.
        to_stage: The target stage key to roll back to.

    Returns:
        Updated project dict returned by the API.
    """
    response = await client.put(
        f"/api/projects/{project_id}/stage",
        json={"to_stage": to_stage, "event": "rollback", "mode": "rollback"},
    )
    return response


# ---------------------------------------------------------------------------
# Test functions
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_a_setup_project_for_rollback(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    Create a dedicated rollback test project and advance it to inquiry_check.

    Creates a fresh project (independent of the main e2e_state project) and
    advances it through three forward transitions:
      prep_docs -> submit_first_instance -> await_response -> inquiry_check

    The project id is stored in e2e_state["rollback_project_id"] for all
    subsequent tests in this file.
    """
    # Create a fresh project dedicated to rollback testing
    create_resp = await api_client.post(
        "/api/projects",
        json={"name": "E2E Rollback Test Project"},
    )
    await assert_status(create_resp, 201, "POST /api/projects (rollback project)")
    data = create_resp.json()
    project_id = data.get("id") or data.get("_id")
    assert project_id, (
        f"Created rollback project must have an id. Got keys: {list(data.keys())}"
    )

    # Verify initial stage
    initial_stage = data.get("stage", {}).get("key")
    assert initial_stage == "prep_docs", (
        f"New project must start at 'prep_docs', got '{initial_stage}'"
    )
    e2e_state["rollback_project_id"] = project_id
    logger.info("Created rollback test project id=%s at stage='prep_docs'", project_id)

    # Advance through 3 transitions to reach inquiry_check
    for event, expected_stage in ROLLBACK_SETUP_PATH:
        await _advance_stage(api_client, project_id, event, expected_stage)

    # Final verification
    final_resp = await api_client.get(f"/api/projects/{project_id}")
    await assert_status(final_resp, 200, f"GET /api/projects/{project_id} after setup")
    final_stage = final_resp.json().get("stage", {}).get("key")
    assert final_stage == "inquiry_check", (
        f"Expected project at 'inquiry_check' after setup, got '{final_stage}'"
    )
    logger.info(
        "Rollback project %s is ready at stage='inquiry_check'", project_id
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_b_verify_rollback_targets_available(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    Verify that stage-options returns meaningful rollback_targets.

    At inquiry_check (after 3 forward transitions from prep_docs), the
    rollback_targets should include all previously visited stages in reverse
    chronological order: ["await_response", "submit_first_instance", "prep_docs"].
    """
    project_id = e2e_state.get("rollback_project_id")
    assert project_id, (
        "e2e_state['rollback_project_id'] must be set by test_a_setup_project_for_rollback"
    )

    options_resp = await api_client.get(f"/api/projects/{project_id}/stage-options")
    await assert_status(options_resp, 200, f"GET /api/projects/{project_id}/stage-options")
    options = options_resp.json()

    rollback_targets = options.get("rollback_targets", [])
    logger.info("Rollback targets at inquiry_check: %s", rollback_targets)

    assert isinstance(rollback_targets, list), (
        f"rollback_targets must be a list. Got: {type(rollback_targets)}"
    )
    assert len(rollback_targets) > 0, (
        "rollback_targets must not be empty after 3 forward transitions. "
        f"Full options: {options}"
    )
    assert "await_response" in rollback_targets, (
        f"'await_response' (most recent previous stage) must be in rollback_targets. "
        f"Got: {rollback_targets}"
    )
    assert "prep_docs" in rollback_targets, (
        f"'prep_docs' (original stage) must be in rollback_targets. "
        f"Got: {rollback_targets}"
    )

    # The most recent previous stage (rollback_targets[0]) should be await_response
    assert rollback_targets[0] == "await_response", (
        f"rollback_targets[0] must be the most recent previous stage 'await_response'. "
        f"Got '{rollback_targets[0]}'. Full list: {rollback_targets}"
    )
    logger.info(
        "rollback_targets verified: %d targets, most recent='%s', oldest='%s'",
        len(rollback_targets),
        rollback_targets[0],
        rollback_targets[-1],
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_c_rollback_one_stage(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    Rollback from inquiry_check to await_response (the most recent previous stage).

    Uses mode="rollback" with to_stage=rollback_targets[0]. Verifies:
    - PUT /api/projects/{id}/stage returns 200 with stage.key == "await_response"
    - GET /api/projects/{id} confirms the stage is persisted
    - stage_history has a new entry with event containing "rollback" and to="await_response"
    """
    project_id = e2e_state.get("rollback_project_id")
    assert project_id, (
        "e2e_state['rollback_project_id'] must be set by test_a_setup_project_for_rollback"
    )

    # Get current rollback targets
    options_resp = await api_client.get(f"/api/projects/{project_id}/stage-options")
    await assert_status(options_resp, 200, "GET stage-options before rollback")
    rollback_targets = options_resp.json().get("rollback_targets", [])
    assert len(rollback_targets) > 0, (
        f"Need at least one rollback_target. Got: {rollback_targets}"
    )

    target_stage = rollback_targets[0]  # most recent = "await_response"
    logger.info(
        "Rolling back project %s from 'inquiry_check' to '%s'",
        project_id,
        target_stage,
    )

    # Perform the rollback
    rollback_resp = await _rollback_stage(api_client, project_id, target_stage)
    await assert_status(rollback_resp, 200, f"PUT /api/projects/{project_id}/stage (rollback)")
    rollback_data = rollback_resp.json()

    # Assert response stage key
    response_stage = rollback_data.get("stage", {}).get("key")
    assert response_stage == target_stage, (
        f"Rollback response must have stage.key='{target_stage}', got '{response_stage}'"
    )
    logger.info("Rollback PUT response: stage.key='%s'", response_stage)

    # Confirm persistence via GET
    get_resp = await api_client.get(f"/api/projects/{project_id}")
    await assert_status(get_resp, 200, f"GET /api/projects/{project_id} after rollback")
    get_data = get_resp.json()
    persisted_stage = get_data.get("stage", {}).get("key")
    assert persisted_stage == target_stage, (
        f"After rollback, GET must return stage.key='{target_stage}', "
        f"got '{persisted_stage}'"
    )
    logger.info("GET confirmed persisted stage='%s'", persisted_stage)

    # Verify stage_history has a rollback entry
    stage_history = get_data.get("stage_history", [])
    assert len(stage_history) > 0, "stage_history must not be empty"

    last_entry = stage_history[-1]
    last_event = last_entry.get("event", "")
    last_to = last_entry.get("to", "")
    assert "rollback" in last_event.lower(), (
        f"Last stage_history entry must have event containing 'rollback'. "
        f"Got event='{last_event}'. Full entry: {last_entry}"
    )
    assert last_to == target_stage, (
        f"Last stage_history entry must have to='{target_stage}'. "
        f"Got to='{last_to}'. Full entry: {last_entry}"
    )
    logger.info(
        "stage_history rollback entry verified: event='%s', to='%s'",
        last_event,
        last_to,
    )

    # Store the rolled-back stage for next tests
    e2e_state["rollback_current_stage"] = target_stage


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_d_rollback_history_integrity(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    Verify the integrity of stage_history after one rollback.

    Expected history (5 entries minimum after setup + 1 rollback):
      1. {"from": None, "to": "prep_docs", "event": "create"}
      2. {"from": "prep_docs", "to": "submit_first_instance", "event": "next"}
      3. {"from": "submit_first_instance", "to": "await_response", "event": "next"}
      4. {"from": "await_response", "to": "inquiry_check", "event": "next"}
      5. {"from": "inquiry_check", "to": "await_response", "event": "rollback:..."}

    Verifies:
    - At least 5 history entries exist
    - First entry: to="prep_docs", from=None or "prep_docs"
    - History shows a forward progression before the rollback
    - Last entry is the rollback (event contains "rollback")
    """
    project_id = e2e_state.get("rollback_project_id")
    assert project_id, (
        "e2e_state['rollback_project_id'] must be set by test_a_setup_project_for_rollback"
    )

    get_resp = await api_client.get(f"/api/projects/{project_id}")
    await assert_status(get_resp, 200, f"GET /api/projects/{project_id}")
    data = get_resp.json()
    stage_history = data.get("stage_history", [])

    logger.info(
        "stage_history has %d entries: %s",
        len(stage_history),
        [
            {"event": h.get("event"), "from": h.get("from"), "to": h.get("to")}
            for h in stage_history
        ],
    )

    # At minimum: 1 create + 3 advances + 1 rollback = 5 entries
    assert len(stage_history) >= 5, (
        f"Expected at least 5 stage_history entries (1 create + 3 advances + 1 rollback). "
        f"Got {len(stage_history)}: {stage_history}"
    )

    # First entry: project creation -> prep_docs
    first_entry = stage_history[0]
    assert first_entry.get("to") == "prep_docs", (
        f"First history entry must be the initial 'prep_docs' stage. "
        f"Got to='{first_entry.get('to')}'. Entry: {first_entry}"
    )
    # The "from" field on creation is None
    assert first_entry.get("from") is None, (
        f"First history entry 'from' must be None (creation event). "
        f"Got from='{first_entry.get('from')}'. Entry: {first_entry}"
    )
    logger.info("First history entry verified: to='prep_docs', from=None")

    # Last entry must be the rollback
    last_entry = stage_history[-1]
    assert "rollback" in last_entry.get("event", "").lower(), (
        f"Last history entry must be a rollback. "
        f"Got event='{last_entry.get('event')}'. Entry: {last_entry}"
    )
    logger.info(
        "Last history entry verified as rollback: event='%s', to='%s'",
        last_entry.get("event"),
        last_entry.get("to"),
    )

    # Verify forward progress in intermediate entries
    forward_stages = [h.get("to") for h in stage_history[1:-1]]
    assert "submit_first_instance" in forward_stages, (
        f"History must show advancement through 'submit_first_instance'. "
        f"Intermediate stages: {forward_stages}"
    )
    assert "await_response" in forward_stages, (
        f"History must show advancement through 'await_response'. "
        f"Intermediate stages: {forward_stages}"
    )
    assert "inquiry_check" in forward_stages, (
        f"History must show advancement through 'inquiry_check'. "
        f"Intermediate stages: {forward_stages}"
    )
    logger.info(
        "Forward progression verified in stage_history: %s", forward_stages
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e_rollback_multiple_stages(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    Rollback from await_response all the way back to prep_docs (multi-stage rollback).

    The project is currently at await_response (after rollback in test_c).
    The oldest rollback_target should be prep_docs. After this rollback,
    the project should be back at prep_docs and able to advance forward again.
    """
    project_id = e2e_state.get("rollback_project_id")
    assert project_id, (
        "e2e_state['rollback_project_id'] must be set by test_a_setup_project_for_rollback"
    )

    # Verify current stage before this rollback
    options_resp = await api_client.get(f"/api/projects/{project_id}/stage-options")
    await assert_status(options_resp, 200, "GET stage-options before multi-stage rollback")
    options = options_resp.json()
    rollback_targets = options.get("rollback_targets", [])
    logger.info(
        "Current stage-options rollback_targets: %s", rollback_targets
    )

    assert len(rollback_targets) > 0, (
        f"Must have rollback_targets available. Got: {rollback_targets}. "
        f"Full options: {options}"
    )

    # Roll back to the oldest (furthest back) available target
    oldest_target = rollback_targets[-1]
    logger.info(
        "Rolling back project %s to oldest target='%s'", project_id, oldest_target
    )

    rollback_resp = await _rollback_stage(api_client, project_id, oldest_target)
    await assert_status(
        rollback_resp, 200, f"PUT /api/projects/{project_id}/stage (multi-stage rollback)"
    )
    response_stage = rollback_resp.json().get("stage", {}).get("key")
    assert response_stage == oldest_target, (
        f"Multi-stage rollback must land at '{oldest_target}', got '{response_stage}'"
    )
    logger.info(
        "Multi-stage rollback successful: project %s is now at stage='%s'",
        project_id,
        response_stage,
    )

    # Verify that forward transitions are available (stage machine is not locked)
    verify_options_resp = await api_client.get(
        f"/api/projects/{project_id}/stage-options"
    )
    await assert_status(verify_options_resp, 200, "GET stage-options after multi-stage rollback")
    verify_options = verify_options_resp.json()
    next_actions = verify_options.get("next_actions", [])
    assert len(next_actions) > 0, (
        f"After rollback to '{oldest_target}', next_actions must not be empty "
        f"(stage machine must not be locked). Got: {next_actions}. "
        f"Full options: {verify_options}"
    )
    logger.info(
        "Stage machine not locked after rollback: %d forward action(s) available",
        len(next_actions),
    )

    # Store the stage for next test
    e2e_state["post_rollback_stage"] = oldest_target


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_f_advance_after_rollback(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    Verify the stage machine can be advanced normally after a rollback.

    The project was rolled back to an early stage in test_e. This test fires the
    'next' event to confirm the machine is fully functional post-rollback.
    It is NOT locked and transitions are valid.
    """
    project_id = e2e_state.get("rollback_project_id")
    assert project_id, (
        "e2e_state['rollback_project_id'] must be set by test_a_setup_project_for_rollback"
    )

    # Resolve the 'next' action from stage-options
    options_resp = await api_client.get(f"/api/projects/{project_id}/stage-options")
    await assert_status(options_resp, 200, "GET stage-options before post-rollback advance")
    options = options_resp.json()
    next_actions = options.get("next_actions", [])
    assert len(next_actions) > 0, (
        f"Expected available next_actions after rollback. Got: {next_actions}. "
        f"Full options: {options}"
    )

    # Prefer the 'next' event; fall back to the first available
    matching = next((a for a in next_actions if a["event"] == "next"), None)
    if matching is None:
        matching = next_actions[0]

    event = matching["event"]
    to_stage = matching["to"]
    logger.info(
        "Advancing project %s post-rollback: event='%s', to_stage='%s'",
        project_id,
        event,
        to_stage,
    )

    advance_resp = await api_client.put(
        f"/api/projects/{project_id}/stage",
        json={"event": event, "to_stage": to_stage},
    )
    await assert_status(
        advance_resp, 200, f"PUT /api/projects/{project_id}/stage (post-rollback advance)"
    )
    result_stage = advance_resp.json().get("stage", {}).get("key")
    assert result_stage == to_stage, (
        f"Post-rollback advance must move to '{to_stage}', got '{result_stage}'"
    )
    logger.info(
        "Post-rollback advance succeeded: project %s is now at stage='%s'",
        project_id,
        result_stage,
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_fail1_rollback_to_invalid_stage(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    Rollback to a nonexistent stage key must return 400 or 422.

    The stage machine's set_stage raises ValueError for unknown stage keys.
    The route handler converts ValueError to a 400 ValidationError.
    """
    project_id = e2e_state.get("rollback_project_id")
    assert project_id, (
        "e2e_state['rollback_project_id'] must be set by test_a_setup_project_for_rollback"
    )

    response = await api_client.put(
        f"/api/projects/{project_id}/stage",
        json={
            "to_stage": "nonexistent_stage_xyz",
            "event": "rollback",
            "mode": "rollback",
        },
    )
    assert response.status_code in (400, 422), (
        f"Rollback to invalid stage 'nonexistent_stage_xyz' must return 400 or 422. "
        f"Got {response.status_code}: {response.text[:300]}"
    )
    logger.info(
        "Invalid rollback target correctly rejected with HTTP %d", response.status_code
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_fail2_rollback_nonexistent_project(
    api_client: httpx.AsyncClient,
) -> None:
    """
    Rollback on a nonexistent project id must return 404.

    Uses a syntactically valid but non-existent MongoDB ObjectId.
    """
    fake_id = "000000000000000000000000"

    response = await api_client.put(
        f"/api/projects/{fake_id}/stage",
        json={
            "to_stage": "prep_docs",
            "event": "rollback",
            "mode": "rollback",
        },
    )
    assert response.status_code == 404, (
        f"Rollback on nonexistent project must return 404. "
        f"Got {response.status_code}: {response.text[:300]}"
    )
    logger.info(
        "Nonexistent project rollback correctly rejected with HTTP 404"
    )
