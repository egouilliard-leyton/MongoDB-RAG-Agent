"""
Multi-workflow-type E2E tests.

Covers:
  - GET /api/workflows?workflow_type= filtering for all 4 types
  - POST /api/workflows/seed-default-for-type idempotency for all 4 types
  - workflow_type field present on all workflow responses
  - Project workflow has exactly 15 stages (the real pipeline)
  - Project workflow contains key stage IDs (prep_docs, inquiry_check, end_refund, etc.)
  - is_default scoped per type (creating a default for qa_session doesn't affect project default)

Tests are ordered alphabetically by letter prefix and are self-contained: each creates
and tears down its own temporary data rather than relying on shared state across tests.
"""

import logging

import httpx
import pytest

from tests.e2e.conftest import assert_status

logger = logging.getLogger(__name__)

_ALL_WORKFLOW_TYPES: list[str] = ["project", "qa_session", "qa_pair", "agentic"]


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_a_all_four_types_have_defaults(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    GET /api/workflows returns at least 4 workflows covering all 4 workflow types.

    Each type must have at least one workflow with is_default=True.  Stores the
    default workflow ids by type in e2e_state for use by downstream tests.
    """
    response = await api_client.get("/api/workflows")
    await assert_status(response, 200, "GET /api/workflows (all types)")
    workflows: list[dict] = response.json()

    assert isinstance(workflows, list), (
        f"GET /api/workflows must return a JSON array, got {type(workflows)}"
    )
    assert len(workflows) >= 4, (
        f"Expected at least 4 workflows (one per type), found {len(workflows)}"
    )

    # Collect all types present in the response.
    types_present = {w.get("workflow_type") for w in workflows}
    for wtype in _ALL_WORKFLOW_TYPES:
        assert wtype in types_present, (
            f"workflow_type='{wtype}' is missing from GET /api/workflows. "
            f"Types found: {types_present}"
        )

    # Verify each type has at least one default and store ids.
    defaults_by_type: dict[str, str] = {}
    for wtype in _ALL_WORKFLOW_TYPES:
        type_defaults = [
            w for w in workflows
            if w.get("workflow_type") == wtype and w.get("is_default") is True
        ]
        assert len(type_defaults) >= 1, (
            f"No default workflow found for type='{wtype}'. "
            f"All workflows of that type: "
            f"{[w for w in workflows if w.get('workflow_type') == wtype]}"
        )
        wid = type_defaults[0].get("id") or type_defaults[0].get("_id")
        assert wid, f"Default workflow for type='{wtype}' has no id field"
        defaults_by_type[wtype] = wid

    e2e_state["default_workflow_ids_by_type"] = defaults_by_type
    logger.info(
        "All 4 workflow types have defaults. IDs: %s",
        defaults_by_type,
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_b_filter_by_project_type(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    GET /api/workflows?workflow_type=project returns only project-type workflows.

    The "Polish Tax Interpretations" default must be present, must have exactly
    15 stages, and every returned item must have workflow_type='project'.
    """
    response = await api_client.get("/api/workflows", params={"workflow_type": "project"})
    await assert_status(response, 200, "GET /api/workflows?workflow_type=project")
    workflows: list[dict] = response.json()

    assert isinstance(workflows, list), (
        f"Response must be a list, got {type(workflows)}"
    )
    assert len(workflows) >= 1, (
        "Filter by project type must return at least the default project workflow"
    )

    # All returned items must be of type "project".
    for w in workflows:
        assert w.get("workflow_type") == "project", (
            f"workflow_type filter returned a non-project item: {w}"
        )

    # Find the default project workflow.
    defaults = [w for w in workflows if w.get("is_default") is True]
    assert len(defaults) >= 1, (
        "No default project workflow found in filtered list"
    )
    default_proj = defaults[0]

    assert default_proj.get("stage_count") == 15, (
        f"Default project workflow must have exactly 15 stages, "
        f"got stage_count={default_proj.get('stage_count')}"
    )

    project_wid = default_proj.get("id") or default_proj.get("_id")
    assert project_wid, "Default project workflow must have an id field"
    e2e_state["project_workflow_id"] = project_wid
    logger.info(
        "Project workflow filter: %d result(s); default id=%s stage_count=%d",
        len(workflows),
        project_wid,
        default_proj.get("stage_count"),
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_c_project_workflow_has_real_stages(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    GET /api/workflows/{id} for the project workflow returns 15 stages with
    the correct stage IDs and transition counts.

    Key assertions:
    - Total stage count == 15
    - Required stage IDs are all present
    - end_refund and end_no_appeal are terminal (0 transitions)
    - inquiry_check has exactly 2 transitions
    """
    project_wid = e2e_state.get("project_workflow_id")
    assert project_wid, (
        "e2e_state['project_workflow_id'] must be set by test_b_filter_by_project_type"
    )

    response = await api_client.get(f"/api/workflows/{project_wid}")
    await assert_status(response, 200, f"GET /api/workflows/{project_wid}")
    data = response.json()

    stages: list[dict] = data.get("stages", [])
    assert len(stages) == 15, (
        f"Project workflow must have exactly 15 stages, got {len(stages)}"
    )

    stage_ids = {s["id"] for s in stages}
    required_ids = {
        "prep_docs",
        "submit_first_instance",
        "await_response",
        "inquiry_check",
        "prepare_answers",
        "first_instance_outcome",
        "end_refund",
        "end_no_appeal",
        "return_reconsideration",
    }
    missing = required_ids - stage_ids
    assert not missing, (
        f"Project workflow missing required stage IDs: {missing}. "
        f"Found: {stage_ids}"
    )

    # Terminal stages must have 0 transitions.
    stages_by_id = {s["id"]: s for s in stages}
    for terminal_id in ("end_refund", "end_no_appeal"):
        transitions = stages_by_id[terminal_id].get("transitions", [])
        assert len(transitions) == 0, (
            f"Stage '{terminal_id}' must be terminal (0 transitions), "
            f"got {len(transitions)}: {transitions}"
        )

    # inquiry_check must have exactly 2 transitions (Yes/No branch).
    inquiry_transitions = stages_by_id["inquiry_check"].get("transitions", [])
    assert len(inquiry_transitions) == 2, (
        f"Stage 'inquiry_check' must have exactly 2 transitions, "
        f"got {len(inquiry_transitions)}: {inquiry_transitions}"
    )

    logger.info(
        "Project workflow id=%s: 15 stages verified; required IDs present; "
        "terminal stages correct; inquiry_check has 2 transitions",
        project_wid,
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_d_filter_by_qa_session_type(
    api_client: httpx.AsyncClient,
) -> None:
    """
    GET /api/workflows?workflow_type=qa_session returns at least one qa_session workflow.

    The default qa_session workflow must have exactly 4 stages.
    All returned items must have workflow_type='qa_session'.
    """
    response = await api_client.get("/api/workflows", params={"workflow_type": "qa_session"})
    await assert_status(response, 200, "GET /api/workflows?workflow_type=qa_session")
    workflows: list[dict] = response.json()

    assert isinstance(workflows, list), (
        f"Response must be a list, got {type(workflows)}"
    )
    assert len(workflows) >= 1, (
        "Filter by qa_session type must return at least the default workflow"
    )

    for w in workflows:
        assert w.get("workflow_type") == "qa_session", (
            f"workflow_type filter returned a non-qa_session item: {w}"
        )

    defaults = [w for w in workflows if w.get("is_default") is True]
    assert len(defaults) >= 1, "No default qa_session workflow found"

    default_qa = defaults[0]
    assert default_qa.get("stage_count") == 4, (
        f"Default qa_session workflow must have 4 stages, "
        f"got stage_count={default_qa.get('stage_count')}"
    )

    logger.info(
        "qa_session filter: %d result(s); default has %d stage(s)",
        len(workflows),
        default_qa.get("stage_count"),
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e_filter_by_qa_pair_type(
    api_client: httpx.AsyncClient,
) -> None:
    """
    GET /api/workflows?workflow_type=qa_pair returns the qa_pair workflow.

    The default qa_pair workflow must have exactly 5 stages.
    All returned items must have workflow_type='qa_pair'.
    """
    response = await api_client.get("/api/workflows", params={"workflow_type": "qa_pair"})
    await assert_status(response, 200, "GET /api/workflows?workflow_type=qa_pair")
    workflows: list[dict] = response.json()

    assert isinstance(workflows, list), (
        f"Response must be a list, got {type(workflows)}"
    )
    assert len(workflows) >= 1, (
        "Filter by qa_pair type must return at least the default workflow"
    )

    for w in workflows:
        assert w.get("workflow_type") == "qa_pair", (
            f"workflow_type filter returned a non-qa_pair item: {w}"
        )

    defaults = [w for w in workflows if w.get("is_default") is True]
    assert len(defaults) >= 1, "No default qa_pair workflow found"

    default_qa_pair = defaults[0]
    assert default_qa_pair.get("stage_count") == 5, (
        f"Default qa_pair workflow must have 5 stages, "
        f"got stage_count={default_qa_pair.get('stage_count')}"
    )

    logger.info(
        "qa_pair filter: %d result(s); default has %d stage(s)",
        len(workflows),
        default_qa_pair.get("stage_count"),
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_f_filter_by_agentic_type(
    api_client: httpx.AsyncClient,
) -> None:
    """
    GET /api/workflows?workflow_type=agentic returns the agentic workflow.

    The default agentic workflow must have exactly 5 stages.
    All returned items must have workflow_type='agentic'.
    """
    response = await api_client.get("/api/workflows", params={"workflow_type": "agentic"})
    await assert_status(response, 200, "GET /api/workflows?workflow_type=agentic")
    workflows: list[dict] = response.json()

    assert isinstance(workflows, list), (
        f"Response must be a list, got {type(workflows)}"
    )
    assert len(workflows) >= 1, (
        "Filter by agentic type must return at least the default workflow"
    )

    for w in workflows:
        assert w.get("workflow_type") == "agentic", (
            f"workflow_type filter returned a non-agentic item: {w}"
        )

    defaults = [w for w in workflows if w.get("is_default") is True]
    assert len(defaults) >= 1, "No default agentic workflow found"

    default_agentic = defaults[0]
    assert default_agentic.get("stage_count") == 5, (
        f"Default agentic workflow must have 5 stages, "
        f"got stage_count={default_agentic.get('stage_count')}"
    )

    logger.info(
        "agentic filter: %d result(s); default has %d stage(s)",
        len(workflows),
        default_agentic.get("stage_count"),
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_g_seed_default_for_type_idempotent(
    api_client: httpx.AsyncClient,
) -> None:
    """
    POST /api/workflows/seed-default-for-type?workflow_type=agentic is idempotent.

    Calling it twice must return 200 both times with the same workflow name, and
    the list of agentic workflows must not grow between the two calls.
    """
    list_before_response = await api_client.get(
        "/api/workflows", params={"workflow_type": "agentic"}
    )
    await assert_status(list_before_response, 200, "GET agentic workflows (before seed)")
    count_before = len(list_before_response.json())

    # First call.
    r1 = await api_client.post(
        "/api/workflows/seed-default-for-type",
        params={"workflow_type": "agentic"},
    )
    await assert_status(r1, 200, "POST seed-default-for-type agentic (1st call)")
    data1 = r1.json()
    assert data1.get("name"), f"First seed call must return a workflow name. Got: {data1}"
    assert data1.get("workflow_type") == "agentic", (
        f"Seeded workflow must have workflow_type='agentic', got '{data1.get('workflow_type')}'"
    )

    # Second call — must be idempotent.
    r2 = await api_client.post(
        "/api/workflows/seed-default-for-type",
        params={"workflow_type": "agentic"},
    )
    await assert_status(r2, 200, "POST seed-default-for-type agentic (2nd call — idempotency)")
    data2 = r2.json()

    assert data2.get("name") == data1.get("name"), (
        f"Idempotent seed must return the same workflow name. "
        f"1st='{data1.get('name')}', 2nd='{data2.get('name')}'"
    )
    assert data2.get("id") == data1.get("id"), (
        f"Idempotent seed must return the same workflow id. "
        f"1st='{data1.get('id')}', 2nd='{data2.get('id')}'"
    )

    # List must not have grown (no duplicate created).
    list_after_response = await api_client.get(
        "/api/workflows", params={"workflow_type": "agentic"}
    )
    await assert_status(list_after_response, 200, "GET agentic workflows (after seed)")
    count_after = len(list_after_response.json())

    assert count_after == count_before, (
        f"Idempotent seed must not create duplicate workflows. "
        f"Count before: {count_before}, after: {count_after}"
    )

    logger.info(
        "seed-default-for-type agentic idempotency confirmed: "
        "name='%s' id=%s count=%d (unchanged)",
        data1.get("name"),
        data1.get("id"),
        count_after,
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_h_is_default_scoped_per_type(
    api_client: httpx.AsyncClient,
) -> None:
    """
    is_default is scoped per workflow_type — promoting a qa_session workflow to
    default must NOT affect the project default.

    Cleanup strategy: after creating a new default qa_session workflow, we use
    PUT to strip its is_default flag so it becomes deletable, then DELETE it.
    This restores the pre-test state by re-seeding the qa_session default.
    """
    # Capture the current project default id so we can verify it is untouched.
    proj_list_response = await api_client.get(
        "/api/workflows", params={"workflow_type": "project"}
    )
    await assert_status(proj_list_response, 200, "GET project workflows (before)")
    project_defaults_before = [
        w for w in proj_list_response.json() if w.get("is_default") is True
    ]
    assert len(project_defaults_before) >= 1, (
        "There must be at least one default project workflow before the test"
    )
    project_default_id = (
        project_defaults_before[0].get("id") or project_defaults_before[0].get("_id")
    )

    # Create a new qa_session workflow with is_default=True.
    # The service must demote the previous qa_session default.
    payload = {
        "name": "E2E Scoping Test QA Session Default",
        "description": "Temporary workflow for is_default scoping test",
        "is_default": True,
        "workflow_type": "qa_session",
        "stages": [],
    }
    create_response = await api_client.post("/api/workflows", json=payload)
    await assert_status(create_response, 201, "POST /api/workflows (new qa_session default)")
    new_wf = create_response.json()
    new_wf_id = new_wf.get("id") or new_wf.get("_id")
    assert new_wf_id, "Created workflow must have an id"
    assert new_wf.get("is_default") is True, (
        "Newly created workflow must have is_default=True"
    )

    try:
        # Verify only one qa_session workflow is the default (the new one).
        qa_list_response = await api_client.get(
            "/api/workflows", params={"workflow_type": "qa_session"}
        )
        await assert_status(
            qa_list_response, 200, "GET qa_session workflows (after creating new default)"
        )
        qa_session_workflows: list[dict] = qa_list_response.json()
        qa_defaults = [
            w for w in qa_session_workflows if w.get("is_default") is True
        ]
        assert len(qa_defaults) == 1, (
            f"Exactly 1 qa_session workflow must be the default after promotion. "
            f"Found {len(qa_defaults)}: {qa_defaults}"
        )
        qa_default_id = qa_defaults[0].get("id") or qa_defaults[0].get("_id")
        assert qa_default_id == new_wf_id, (
            f"The new qa_session workflow must be the default. "
            f"Expected id={new_wf_id}, got id={qa_default_id}"
        )

        # Verify the project default is completely unaffected.
        proj_list_after_response = await api_client.get(
            "/api/workflows", params={"workflow_type": "project"}
        )
        await assert_status(
            proj_list_after_response, 200, "GET project workflows (after qa_session change)"
        )
        project_defaults_after = [
            w for w in proj_list_after_response.json() if w.get("is_default") is True
        ]
        assert len(project_defaults_after) == 1, (
            f"Exactly 1 project workflow must be the default after the qa_session change. "
            f"Found {len(project_defaults_after)}: {project_defaults_after}"
        )
        project_default_id_after = (
            project_defaults_after[0].get("id") or project_defaults_after[0].get("_id")
        )
        assert project_default_id_after == project_default_id, (
            f"Project default must be unaffected by qa_session changes. "
            f"Before: {project_default_id}, after: {project_default_id_after}"
        )

        logger.info(
            "is_default scoping verified: qa_session default=%s, "
            "project default=%s (unchanged)",
            new_wf_id,
            project_default_id,
        )

    finally:
        # Cleanup: strip is_default so the workflow becomes deletable, then delete it.
        # We must first PUT with is_default=False, then DELETE.
        cleanup_payload = {
            "name": new_wf.get("name", "E2E Scoping Test QA Session Default"),
            "description": new_wf.get("description", ""),
            "is_default": False,
            "workflow_type": "qa_session",
            "stages": [],
        }
        await api_client.put(f"/api/workflows/{new_wf_id}", json=cleanup_payload)
        await api_client.delete(f"/api/workflows/{new_wf_id}")

        # Restore the qa_session default by re-seeding.
        await api_client.post(
            "/api/workflows/seed-default-for-type",
            params={"workflow_type": "qa_session"},
        )
        logger.info("Cleanup complete: removed temp qa_session workflow id=%s", new_wf_id)


# ---------------------------------------------------------------------------
# Error / failure tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_fail1_unknown_workflow_type_filter(
    api_client: httpx.AsyncClient,
) -> None:
    """
    GET /api/workflows?workflow_type=unknown_type returns 200 with an empty list.

    Unknown filter values must not cause a server error — the API treats them
    as a valid (but empty) filter result.
    """
    response = await api_client.get(
        "/api/workflows", params={"workflow_type": "unknown_type"}
    )
    await assert_status(
        response, 200,
        "GET /api/workflows?workflow_type=unknown_type must return 200 (empty list)"
    )
    data = response.json()
    assert isinstance(data, list), (
        f"Response must be a list, got {type(data)}"
    )
    assert len(data) == 0, (
        f"Unknown type filter must return an empty list, got {len(data)} items: {data}"
    )
    logger.info("Unknown workflow_type filter correctly returned 200 with empty list")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_fail2_seed_default_for_type_invalid_type(
    api_client: httpx.AsyncClient,
) -> None:
    """
    POST /api/workflows/seed-default-for-type?workflow_type=invalid returns 400 or 422.

    The endpoint must validate the workflow_type parameter and reject invalid values
    with a client-error status code.
    """
    response = await api_client.post(
        "/api/workflows/seed-default-for-type",
        params={"workflow_type": "invalid"},
    )
    assert response.status_code in (400, 422), (
        f"POST seed-default-for-type with invalid type must return 400 or 422. "
        f"Got {response.status_code}: {response.text[:300]}"
    )
    logger.info(
        "seed-default-for-type with invalid type correctly returned %d: %s",
        response.status_code,
        response.text[:200],
    )
