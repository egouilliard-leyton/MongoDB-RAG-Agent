"""
Project stage machine E2E tests — full path to NSA decision.

Tests the complete 14-stage Polish tax appeal process (project_stages.py).
Uses SEPARATE projects from the session workflow project (tests 02-07).

Fast path to NSA (10 transitions, all "negative" choices):
  prep_docs          --(next)-->      submit_first_instance
  submit_first       --(next)-->      await_response
  await_response     --(next)-->      inquiry_check
  inquiry_check      --(no)-->        first_instance_outcome
  first_instance     --(negative)--> appeal_second_instance
  appeal_second      --(yes)-->       second_instance_decision
  second_instance    --(negative)--> complaint_wsa
  complaint_wsa      --(yes)-->       wsa_decision
  wsa_decision       --(negative)--> complaint_nsa
  complaint_nsa      --(yes)-->       nsa_decision   <- NSA REACHED

Three projects are created:
  nsa_project_id           -> fast path to nsa_decision -> negative_final -> end_no_appeal
  nsa_success_project_id   -> fast path to nsa_decision -> successful -> return_reconsideration
  positive_first_project_id -> prep_docs->submit->await->inquiry->first_instance->positive->end_refund
"""

import logging

import httpx
import pytest

from tests.e2e.conftest import assert_status

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

# Fast path: sequence of (event, expected_to_stage) for reaching nsa_decision
NSA_FAST_PATH: list[tuple[str, str]] = [
    ("next", "submit_first_instance"),
    ("next", "await_response"),
    ("next", "inquiry_check"),
    ("no", "first_instance_outcome"),
    ("negative", "appeal_second_instance"),
    ("yes", "second_instance_decision"),
    ("negative", "complaint_wsa"),
    ("yes", "wsa_decision"),
    ("negative", "complaint_nsa"),
    ("yes", "nsa_decision"),
]


async def advance_stage(
    client: httpx.AsyncClient, project_id: str, event: str
) -> dict:
    """
    Advance project stage machine by firing an event.

    Looks up the valid to_stage from stage-options so the PUT request
    includes both required fields (event + to_stage).

    Args:
        client: The async HTTP client.
        project_id: MongoDB ObjectId string for the project.
        event: Transition event name (e.g. 'next', 'negative', 'yes', 'no').

    Returns:
        Updated project dict from the API response.
    """
    # First get stage options to find the to_stage for this event
    options_resp = await client.get(f"/api/projects/{project_id}/stage-options")
    assert options_resp.status_code == 200, (
        f"GET stage-options for project {project_id} failed: "
        f"{options_resp.status_code} {options_resp.text[:300]}"
    )
    options = options_resp.json()
    next_actions = options.get("next_actions", [])

    matching = next((a for a in next_actions if a["event"] == event), None)
    assert matching is not None, (
        f"Stage advance event='{event}' not found in next_actions: {next_actions}. "
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
    return response.json()


async def get_current_stage(client: httpx.AsyncClient, project_id: str) -> str:
    """
    Return the current stage key for a project.

    Args:
        client: The async HTTP client.
        project_id: MongoDB ObjectId string for the project.

    Returns:
        Current stage key string (e.g. 'prep_docs', 'nsa_decision').
    """
    resp = await client.get(f"/api/projects/{project_id}")
    assert resp.status_code == 200, (
        f"GET /api/projects/{project_id} failed: {resp.status_code} {resp.text[:300]}"
    )
    data = resp.json()
    return data["stage"]["key"]


async def _fast_path_to_nsa(
    client: httpx.AsyncClient, project_id: str
) -> None:
    """
    Execute all 10 transitions in the fast path to nsa_decision.

    Args:
        client: The async HTTP client.
        project_id: MongoDB ObjectId string for the project to advance.
    """
    for event, expected_stage in NSA_FAST_PATH:
        result = await advance_stage(client, project_id, event)
        actual_stage = result.get("stage", {}).get("key")
        assert actual_stage == expected_stage, (
            f"After event='{event}': expected stage='{expected_stage}', "
            f"got '{actual_stage}'. Project id={project_id}"
        )
        logger.info(
            "Project %s: event='%s' -> stage='%s'", project_id, event, actual_stage
        )


# ---------------------------------------------------------------------------
# Test functions
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_a_create_nsa_test_projects(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    Create 3 dedicated projects for stage machine testing.

    Each project starts at 'prep_docs' (the initial project stage).
    """
    projects_to_create = [
        ("nsa_project_id", "E2E NSA Test — Negative Final Path"),
        ("nsa_success_project_id", "E2E NSA Test — Successful Path"),
        ("positive_first_project_id", "E2E NSA Test — Positive First Instance"),
    ]

    for state_key, project_name in projects_to_create:
        response = await api_client.post(
            "/api/projects", json={"name": project_name}
        )
        await assert_status(response, 201, f"POST /api/projects ({state_key})")
        data = response.json()
        project_id = data.get("id") or data.get("_id")
        assert project_id, f"Created project must have an id. Got: {list(data.keys())}"

        # Verify initial stage is prep_docs
        stage_key = data.get("stage", {}).get("key")
        assert stage_key == "prep_docs", (
            f"New project '{project_name}' must start at 'prep_docs', "
            f"got '{stage_key}'"
        )

        e2e_state[state_key] = project_id
        logger.info("Created project %s id=%s, initial stage=%s", state_key, project_id, stage_key)

    logger.info(
        "Three NSA test projects created: nsa=%s, nsa_success=%s, positive_first=%s",
        e2e_state["nsa_project_id"],
        e2e_state["nsa_success_project_id"],
        e2e_state["positive_first_project_id"],
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_b_stage_prep_docs_to_submit(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """Transition 1: prep_docs --(next)--> submit_first_instance."""
    project_id = e2e_state.get("nsa_project_id")
    assert project_id, "e2e_state['nsa_project_id'] must be set by test_a"

    result = await advance_stage(api_client, project_id, "next")
    current = result.get("stage", {}).get("key")
    assert current == "submit_first_instance", (
        f"Expected 'submit_first_instance', got '{current}'"
    )
    logger.info("NSA project: prep_docs -> submit_first_instance OK")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_c_stage_submit_to_await(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """Transition 2: submit_first_instance --(next)--> await_response."""
    project_id = e2e_state.get("nsa_project_id")
    assert project_id, "e2e_state['nsa_project_id'] must be set by test_a"

    result = await advance_stage(api_client, project_id, "next")
    current = result.get("stage", {}).get("key")
    assert current == "await_response", (
        f"Expected 'await_response', got '{current}'"
    )
    logger.info("NSA project: submit_first_instance -> await_response OK")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_d_stage_await_to_inquiry(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """Transition 3: await_response --(next)--> inquiry_check."""
    project_id = e2e_state.get("nsa_project_id")
    assert project_id, "e2e_state['nsa_project_id'] must be set by test_a"

    result = await advance_stage(api_client, project_id, "next")
    current = result.get("stage", {}).get("key")
    assert current == "inquiry_check", (
        f"Expected 'inquiry_check', got '{current}'"
    )
    logger.info("NSA project: await_response -> inquiry_check OK")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e_stage_inquiry_no_to_first_instance(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """Transition 4: inquiry_check --(no)--> first_instance_outcome."""
    project_id = e2e_state.get("nsa_project_id")
    assert project_id, "e2e_state['nsa_project_id'] must be set by test_a"

    result = await advance_stage(api_client, project_id, "no")
    current = result.get("stage", {}).get("key")
    assert current == "first_instance_outcome", (
        f"Expected 'first_instance_outcome', got '{current}'"
    )
    logger.info("NSA project: inquiry_check --(no)--> first_instance_outcome OK")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_f_stage_first_instance_negative(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """Transition 5: first_instance_outcome --(negative)--> appeal_second_instance."""
    project_id = e2e_state.get("nsa_project_id")
    assert project_id, "e2e_state['nsa_project_id'] must be set by test_a"

    result = await advance_stage(api_client, project_id, "negative")
    current = result.get("stage", {}).get("key")
    assert current == "appeal_second_instance", (
        f"Expected 'appeal_second_instance', got '{current}'"
    )
    logger.info("NSA project: first_instance_outcome --(negative)--> appeal_second_instance OK")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_g_stage_appeal_second_yes(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """Transition 6: appeal_second_instance --(yes)--> second_instance_decision."""
    project_id = e2e_state.get("nsa_project_id")
    assert project_id, "e2e_state['nsa_project_id'] must be set by test_a"

    result = await advance_stage(api_client, project_id, "yes")
    current = result.get("stage", {}).get("key")
    assert current == "second_instance_decision", (
        f"Expected 'second_instance_decision', got '{current}'"
    )
    logger.info("NSA project: appeal_second_instance --(yes)--> second_instance_decision OK")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_h_stage_second_instance_negative(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """Transition 7: second_instance_decision --(negative)--> complaint_wsa."""
    project_id = e2e_state.get("nsa_project_id")
    assert project_id, "e2e_state['nsa_project_id'] must be set by test_a"

    result = await advance_stage(api_client, project_id, "negative")
    current = result.get("stage", {}).get("key")
    assert current == "complaint_wsa", (
        f"Expected 'complaint_wsa', got '{current}'"
    )
    logger.info("NSA project: second_instance_decision --(negative)--> complaint_wsa OK")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_i_stage_complaint_wsa_yes(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """Transition 8: complaint_wsa --(yes)--> wsa_decision."""
    project_id = e2e_state.get("nsa_project_id")
    assert project_id, "e2e_state['nsa_project_id'] must be set by test_a"

    result = await advance_stage(api_client, project_id, "yes")
    current = result.get("stage", {}).get("key")
    assert current == "wsa_decision", (
        f"Expected 'wsa_decision', got '{current}'"
    )
    logger.info("NSA project: complaint_wsa --(yes)--> wsa_decision OK")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_j_stage_wsa_negative(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """Transition 9: wsa_decision --(negative)--> complaint_nsa."""
    project_id = e2e_state.get("nsa_project_id")
    assert project_id, "e2e_state['nsa_project_id'] must be set by test_a"

    result = await advance_stage(api_client, project_id, "negative")
    current = result.get("stage", {}).get("key")
    assert current == "complaint_nsa", (
        f"Expected 'complaint_nsa', got '{current}'"
    )
    logger.info("NSA project: wsa_decision --(negative)--> complaint_nsa OK")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_k_stage_complaint_nsa_yes_reach_nsa(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    Transition 10: complaint_nsa --(yes)--> nsa_decision.

    NSA stage reached! Verify that the available events are
    'negative_final' and 'successful'.
    """
    project_id = e2e_state.get("nsa_project_id")
    assert project_id, "e2e_state['nsa_project_id'] must be set by test_a"

    result = await advance_stage(api_client, project_id, "yes")
    current = result.get("stage", {}).get("key")
    assert current == "nsa_decision", (
        f"Expected 'nsa_decision' after 10 transitions, got '{current}'"
    )
    logger.info("*** NSA stage reached! project_id=%s ***", project_id)
    print(f"NSA stage reached for project {project_id}")

    # Verify stage-options at nsa_decision has exactly the expected events
    options_resp = await api_client.get(f"/api/projects/{project_id}/stage-options")
    await assert_status(options_resp, 200, "GET stage-options at nsa_decision")
    options = options_resp.json()
    next_actions = options.get("next_actions", [])
    available_events = {a["event"] for a in next_actions}

    assert "negative_final" in available_events, (
        f"nsa_decision must have 'negative_final' transition. "
        f"Available events: {available_events}"
    )
    assert "successful" in available_events, (
        f"nsa_decision must have 'successful' transition. "
        f"Available events: {available_events}"
    )
    logger.info("NSA decision stage options verified: events=%s", available_events)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_l_nsa_decision_negative_final(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    OUTCOME 1: NSA rejects the case.

    nsa_decision --(negative_final)--> end_no_appeal (TERMINAL)
    Verify terminal state has no outgoing transitions.
    """
    project_id = e2e_state.get("nsa_project_id")
    assert project_id, "e2e_state['nsa_project_id'] must be set by test_a"

    result = await advance_stage(api_client, project_id, "negative_final")
    current = result.get("stage", {}).get("key")
    assert current == "end_no_appeal", (
        f"Expected 'end_no_appeal' after negative_final, got '{current}'"
    )
    logger.info("NSA project: nsa_decision --(negative_final)--> end_no_appeal OK")

    # Verify terminal: stage-options should have empty next_actions
    options_resp = await api_client.get(f"/api/projects/{project_id}/stage-options")
    await assert_status(options_resp, 200, "GET stage-options at end_no_appeal")
    options = options_resp.json()
    next_actions = options.get("next_actions", [])
    assert len(next_actions) == 0, (
        f"Terminal stage 'end_no_appeal' must have no outgoing transitions. "
        f"Got: {next_actions}"
    )
    logger.info("Confirmed: end_no_appeal is terminal (0 transitions)")
    print("OUTCOME 1: NSA rejected -> end_no_appeal (terminal) VERIFIED")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_m_nsa_decision_successful(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    OUTCOME 2: NSA grants the case.

    Advance nsa_success_project through the full 10-step fast path,
    then fire 'successful' -> return_reconsideration.
    """
    project_id = e2e_state.get("nsa_success_project_id")
    assert project_id, "e2e_state['nsa_success_project_id'] must be set by test_a"

    # Execute all 10 fast-path transitions
    await _fast_path_to_nsa(api_client, project_id)

    # Verify NSA reached
    current = await get_current_stage(api_client, project_id)
    assert current == "nsa_decision", (
        f"Expected 'nsa_decision' after fast path, got '{current}'"
    )

    # Fire 'successful' -> return_reconsideration
    result = await advance_stage(api_client, project_id, "successful")
    final_stage = result.get("stage", {}).get("key")
    assert final_stage == "return_reconsideration", (
        f"Expected 'return_reconsideration' after successful NSA, got '{final_stage}'"
    )
    logger.info(
        "NSA success project: nsa_decision --(successful)--> return_reconsideration OK"
    )
    print("OUTCOME 2: NSA granted -> return_reconsideration VERIFIED")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_n_positive_first_instance(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    OUTCOME 3: Early win — first instance grants the case.

    Path: prep_docs -> submit_first_instance -> await_response ->
          inquiry_check -> first_instance_outcome -> end_refund (TERMINAL)
    """
    project_id = e2e_state.get("positive_first_project_id")
    assert project_id, "e2e_state['positive_first_project_id'] must be set by test_a"

    # Advance through early path to first_instance_outcome
    early_path: list[tuple[str, str]] = [
        ("next", "submit_first_instance"),
        ("next", "await_response"),
        ("next", "inquiry_check"),
        ("no", "first_instance_outcome"),
        ("positive", "end_refund"),
    ]

    for event, expected_stage in early_path:
        result = await advance_stage(api_client, project_id, event)
        actual_stage = result.get("stage", {}).get("key")
        assert actual_stage == expected_stage, (
            f"After event='{event}': expected stage='{expected_stage}', "
            f"got '{actual_stage}'. Project id={project_id}"
        )
        logger.info(
            "Positive first instance project: event='%s' -> stage='%s'",
            event,
            actual_stage,
        )

    # Verify terminal: end_refund has no outgoing transitions
    options_resp = await api_client.get(f"/api/projects/{project_id}/stage-options")
    await assert_status(options_resp, 200, "GET stage-options at end_refund")
    options = options_resp.json()
    next_actions = options.get("next_actions", [])
    assert len(next_actions) == 0, (
        f"Terminal stage 'end_refund' must have no outgoing transitions. "
        f"Got: {next_actions}"
    )
    logger.info("Confirmed: end_refund is terminal (0 transitions)")
    print("OUTCOME 3: Positive first instance -> end_refund (terminal) VERIFIED")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_fail1_invalid_event_from_stage(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    Firing an invalid event from return_reconsideration must return 400 or 422.

    The nsa_success_project is at 'return_reconsideration' after test_m.
    The only valid event from return_reconsideration is 'next'.
    Firing 'jump_to_nsa' must be rejected.
    """
    project_id = e2e_state.get("nsa_success_project_id")
    assert project_id, "e2e_state['nsa_success_project_id'] must be set by test_a"

    # Verify we're at return_reconsideration
    current = await get_current_stage(api_client, project_id)
    assert current == "return_reconsideration", (
        f"Expected 'return_reconsideration' for nsa_success_project, "
        f"got '{current}'. (test_m may not have run yet)"
    )

    # Fire an invalid event — 'jump_to_nsa' does not exist in the transition table
    response = await api_client.put(
        f"/api/projects/{project_id}/stage",
        json={"event": "jump_to_nsa", "to_stage": "nsa_decision"},
    )
    assert response.status_code in (400, 422), (
        f"Invalid event 'jump_to_nsa' from 'return_reconsideration' must return 400/422. "
        f"Got {response.status_code}: {response.text[:300]}"
    )
    logger.info(
        "Invalid event from return_reconsideration correctly rejected with %d",
        response.status_code,
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_fail2_advance_terminal_stage(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    Advancing a terminal stage (end_no_appeal) must return 400 or 422.

    The nsa_project ended at 'end_no_appeal' (terminal) in test_l.
    Firing 'next' must be rejected because terminal stages have no transitions.
    """
    project_id = e2e_state.get("nsa_project_id")
    assert project_id, "e2e_state['nsa_project_id'] must be set by test_a"

    # Verify we're at end_no_appeal (terminal)
    current = await get_current_stage(api_client, project_id)
    assert current == "end_no_appeal", (
        f"Expected nsa_project at 'end_no_appeal', got '{current}'. "
        "(test_l may not have run yet)"
    )

    # Attempt to fire 'next' from terminal stage
    response = await api_client.put(
        f"/api/projects/{project_id}/stage",
        json={"event": "next", "to_stage": "submit_first_instance"},
    )
    assert response.status_code in (400, 422), (
        f"Advancing terminal stage 'end_no_appeal' must return 400/422. "
        f"Got {response.status_code}: {response.text[:300]}"
    )
    logger.info(
        "Terminal stage 'end_no_appeal' correctly rejects 'next' event with %d",
        response.status_code,
    )
    print("VERIFIED: terminal stage cannot be advanced further")
