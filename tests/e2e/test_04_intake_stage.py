"""
Intake stage Q&A E2E tests.

Tests:
  - Verify project/workflow intake stage setup
  - Single question processing
  - Batch question processing
  - QA pairs saved for senior user
  - Failure cases (empty list, over-length question)
  - Advance project stage to analysis (runs last via 'z_' prefix)
"""

import logging

import httpx
import pytest

from tests.e2e.conftest import assert_status

logger = logging.getLogger(__name__)


async def _advance_project_stage(
    api_client: httpx.AsyncClient,
    project_id: str,
    event: str,
) -> dict:
    """
    Advance the project stage machine by firing an event.

    Looks up the valid transition from stage-options, then sends
    PUT /api/projects/{project_id}/stage with both 'event' and 'to_stage'.

    Args:
        api_client: The async HTTP client.
        project_id: MongoDB ObjectId string for the project.
        event: The transition event name (e.g. 'next', 'negative').

    Returns:
        The updated project dict from the API response.
    """
    # Get stage options to find the valid to_stage for this event
    options_resp = await api_client.get(f"/api/projects/{project_id}/stage-options")
    assert options_resp.status_code == 200, (
        f"GET stage-options failed: {options_resp.status_code} {options_resp.text[:300]}"
    )
    options = options_resp.json()
    next_actions = options.get("next_actions", [])

    # Find the matching transition for this event
    matching = next((a for a in next_actions if a["event"] == event), None)
    assert matching is not None, (
        f"Event '{event}' not found in next_actions: {next_actions}. "
        f"Full stage options: {options}"
    )

    to_stage = matching["to"]
    response = await api_client.put(
        f"/api/projects/{project_id}/stage",
        json={"event": event, "to_stage": to_stage},
    )
    assert response.status_code in (200, 201), (
        f"PUT /api/projects/{project_id}/stage event='{event}' to_stage='{to_stage}' "
        f"failed: {response.status_code} {response.text[:300]}"
    )
    return response.json()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_a_verify_intake_stage(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    Record workflow stage IDs from the default workflow template.

    NOTE: The project_stages.py machine (14 stages) is SEPARATE from the
    workflow template stages (intake/analysis/review/complete). This test
    records workflow template stage IDs for later use.
    """
    wf_detail = e2e_state.get("default_workflow")
    if not wf_detail:
        # Fetch the default workflow
        wf_resp = await api_client.get("/api/workflows")
        await assert_status(wf_resp, 200, "GET /api/workflows")
        workflows = wf_resp.json()
        default_wf = next((w for w in workflows if w.get("is_default")), None)
        assert default_wf is not None, "No default workflow — check preflight test"
        wf_id = default_wf.get("id") or default_wf.get("_id")
        detail_resp = await api_client.get(f"/api/workflows/{wf_id}")
        await assert_status(detail_resp, 200, f"GET /api/workflows/{wf_id}")
        wf_detail = detail_resp.json()

    stages = wf_detail.get("stages", [])
    assert len(stages) >= 4, (
        f"Default workflow must have at least 4 stages, found {len(stages)}"
    )

    # Store stage IDs by index (intake=0, analysis=1, review=2, complete=3)
    e2e_state["stage_intake_id"] = stages[0]["id"]
    e2e_state["stage_analysis_id"] = stages[1]["id"]
    e2e_state["stage_review_id"] = stages[2]["id"]
    e2e_state["stage_complete_id"] = stages[3]["id"]

    logger.info(
        "Workflow stages: intake=%s, analysis=%s, review=%s, complete=%s",
        e2e_state["stage_intake_id"],
        e2e_state["stage_analysis_id"],
        e2e_state["stage_review_id"],
        e2e_state["stage_complete_id"],
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_b_single_question_ip_box(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """Submit a single question about IP Box and verify the response structure."""
    session_id = e2e_state.get("session_id")
    assert session_id, "e2e_state['session_id'] must be set by test_03"

    payload = {
        "questions": [
            "What are the conditions for applying the IP Box preferential 5% CIT rate in Poland?"
        ],
        "user_role": "senior",
        "include_history": True,
    }
    response = await api_client.post(
        f"/api/sessions/{session_id}/questions", json=payload
    )
    await assert_status(response, 200, "POST single question IP Box")
    data = response.json()

    assert data["questions_processed"] == 1, (
        f"Expected questions_processed=1, got {data['questions_processed']}"
    )
    qa_pairs = data["qa_pairs"]
    assert len(qa_pairs) == 1, (
        f"Expected 1 qa_pair in response, got {len(qa_pairs)}"
    )
    qa = qa_pairs[0]
    assert qa["final_answer"], (
        f"final_answer must not be empty. Got: '{qa.get('final_answer')}'"
    )

    # Senior users: qa_pair_id should be populated (either _id or qa_pair_id field)
    qa_id = qa.get("_id") or qa.get("qa_pair_id")
    assert qa_id, (
        "Senior session must save qa_pair with an ID (_id or qa_pair_id). "
        f"Got fields: {list(qa.keys())}"
    )
    e2e_state["qa_pair_ids"].append(qa_id)
    logger.info("Single question processed; qa_pair_id=%s", qa_id)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_c_batch_three_questions(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """Submit a batch of 3 R&D relief questions and verify all are processed."""
    session_id = e2e_state.get("session_id")
    assert session_id, "e2e_state['session_id'] must be set by test_03"

    payload = {
        "questions": [
            "What R&D activities qualify for the B+R tax relief?",
            "What documentation must a company maintain for R&D cost deductions?",
            "Can software development costs be included in the R&D relief base?",
        ],
        "user_role": "senior",
        "include_history": True,
    }
    response = await api_client.post(
        f"/api/sessions/{session_id}/questions", json=payload
    )
    await assert_status(response, 200, "POST batch 3 questions")
    data = response.json()

    assert data["questions_processed"] == 3, (
        f"Expected questions_processed=3, got {data['questions_processed']}"
    )
    for qa in data["qa_pairs"]:
        assert qa["final_answer"], (
            f"Each qa_pair must have a non-empty final_answer. "
            f"Question: '{qa.get('question', '')[:80]}'"
        )
        qa_id = qa.get("_id") or qa.get("qa_pair_id")
        if qa_id:
            e2e_state["qa_pair_ids"].append(qa_id)

    logger.info(
        "Batch processed 3 questions. Total qa_pair_ids so far: %d",
        len(e2e_state["qa_pair_ids"]),
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_d_verify_qa_pairs_saved_for_senior(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """Verify all Q&A pairs were persisted for the senior session."""
    session_id = e2e_state.get("session_id")
    assert session_id, "e2e_state['session_id'] must be set by test_03"

    response = await api_client.get(f"/api/sessions/{session_id}/qa-pairs")
    await assert_status(response, 200, f"GET /api/sessions/{session_id}/qa-pairs")
    pairs = response.json()

    assert isinstance(pairs, list), (
        f"Expected list from /qa-pairs, got {type(pairs)}"
    )
    assert len(pairs) >= 4, (
        f"Expected at least 4 Q&A pairs (1 single + 3 batch), found {len(pairs)}"
    )

    for pair in pairs:
        pair_id = pair.get("_id") or pair.get("id")
        assert pair_id, f"Each qa_pair must have an _id. Got: {list(pair.keys())}"
        assert pair.get("question"), "Each qa_pair must have a non-empty question"
        assert pair.get("final_answer"), "Each qa_pair must have a non-empty final_answer"

    logger.info("Verified %d Q&A pairs saved for senior session", len(pairs))


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_fail1_empty_questions_list(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """Submitting an empty questions list must return 422 Unprocessable Entity."""
    session_id = e2e_state.get("session_id")
    assert session_id, "e2e_state['session_id'] must be set by test_03"

    response = await api_client.post(
        f"/api/sessions/{session_id}/questions",
        json={"questions": [], "user_role": "senior"},
    )
    assert response.status_code == 422, (
        f"Expected HTTP 422 for empty questions list, got {response.status_code}: "
        f"{response.text[:300]}"
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_fail2_question_over_10000_chars(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """Submitting a question longer than 10000 characters must return 422."""
    session_id = e2e_state.get("session_id")
    assert session_id, "e2e_state['session_id'] must be set by test_03"

    response = await api_client.post(
        f"/api/sessions/{session_id}/questions",
        json={"questions": ["x" * 10001], "user_role": "senior"},
    )
    assert response.status_code == 422, (
        f"Expected HTTP 422 for over-length question, got {response.status_code}: "
        f"{response.text[:300]}"
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_z_advance_intake_to_analysis(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    Advance the project stage machine from its current stage using the 'next' event.

    NOTE: The project stage machine starts at 'prep_docs'. This test fires 'next'
    to advance it. The workflow template stages (intake/analysis) are tracked separately.
    """
    project_id = e2e_state.get("project_id")
    assert project_id, "e2e_state['project_id'] must be set by test_02"

    # Get current stage options
    options_resp = await api_client.get(f"/api/projects/{project_id}/stage-options")
    await assert_status(options_resp, 200, f"GET /api/projects/{project_id}/stage-options")
    options = options_resp.json()
    next_actions = options.get("next_actions", [])

    logger.info("Stage options before advance: %s", next_actions)

    if not next_actions:
        logger.info(
            "No stage transitions available from current stage — "
            "project may already be at a terminal or later stage"
        )
        return

    # Use 'next' event if available, otherwise use the first available event
    event_to_use = "next"
    matching = next((a for a in next_actions if a["event"] == event_to_use), None)
    if matching is None:
        matching = next_actions[0]
        event_to_use = matching["event"]

    to_stage = matching["to"]
    advance_resp = await api_client.put(
        f"/api/projects/{project_id}/stage",
        json={"event": event_to_use, "to_stage": to_stage},
    )
    assert advance_resp.status_code in (200, 201), (
        f"Stage advance event='{event_to_use}' to_stage='{to_stage}' failed: "
        f"{advance_resp.status_code} {advance_resp.text[:300]}"
    )
    updated = advance_resp.json()
    new_stage = updated.get("stage", {}).get("key")
    assert new_stage == to_stage, (
        f"Expected project stage to be '{to_stage}' after advance, got '{new_stage}'"
    )
    logger.info(
        "Advanced project stage: event='%s' -> stage='%s'", event_to_use, new_stage
    )
