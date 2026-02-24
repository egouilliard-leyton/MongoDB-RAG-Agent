"""
Ingestion job tracking E2E tests.

Tests focus on the /api/ingestion/* endpoints that expose job records created
by the background ingestion pipeline (triggered by /api/documents/upload).
Actual file upload and ingestion are covered by other test files; these tests
assume the ingestion collection may be empty and handle that gracefully.

Tests run in alphabetical order enforced by the letter/fail prefix.
State shared between tests via the session-scoped e2e_state fixture:
  e2e_state["test_job_id"]  — set by test_f when at least one job is found
"""

import logging

import httpx
import pytest

from tests.e2e.conftest import assert_status

logger = logging.getLogger(__name__)

# A valid-format ObjectId guaranteed not to exist in any test database.
_NONEXISTENT_JOB_ID = "000000000000000000000000"

# All valid job status values defined by the IngestionJob Literal type.
_VALID_STATUSES = ("pending", "in_progress", "success", "partial", "failed")

# Terminal states where progress_pct must equal 100.
_TERMINAL_STATUSES = {"success", "partial", "failed"}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _extract_id(job: dict) -> str:
    """
    Extract the string id from an ingestion job dict.

    The serialization alias on IngestionJobResponse uses '_id', but the
    client may receive either '_id' or 'id' depending on FastAPI serialization
    settings.

    Args:
        job: Job dict from the API response.

    Returns:
        The job id as a string.
    """
    return str(job.get("_id") or job.get("id", ""))


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_a_list_ingestion_jobs(api_client: httpx.AsyncClient) -> None:
    """
    GET /api/ingestion/jobs?limit=10 must return 200 with a paginated job list.

    Verifies the basic contract of the list endpoint: the response must be a
    dict with 'jobs' (list) and 'total' (non-negative int).  The test does not
    fail if the list is empty; an empty database is a valid state.
    """
    response = await api_client.get("/api/ingestion/jobs?limit=10")
    await assert_status(response, 200, "GET /api/ingestion/jobs?limit=10")
    data = response.json()

    assert "jobs" in data, (
        f"Response must include a 'jobs' field. Got keys: {list(data.keys())}"
    )
    assert isinstance(data["jobs"], list), (
        f"'jobs' must be a list, got {type(data['jobs'])}"
    )

    assert "total" in data, (
        f"Response must include a 'total' field. Got keys: {list(data.keys())}"
    )
    assert isinstance(data["total"], int) and data["total"] >= 0, (
        f"'total' must be a non-negative int, got {data['total']!r}"
    )

    logger.info(
        "Total ingestion jobs: %d (returned in this page: %d)",
        data["total"],
        len(data["jobs"]),
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_b_list_jobs_with_status_filter(
    api_client: httpx.AsyncClient,
) -> None:
    """
    GET /api/ingestion/jobs?status=success must return only success jobs.

    If the returned list is non-empty each job must have status == 'success'.
    An empty list is acceptable when no successful jobs exist yet.
    """
    response = await api_client.get("/api/ingestion/jobs?status=success&limit=10")
    await assert_status(response, 200, "GET /api/ingestion/jobs?status=success")
    data = response.json()

    jobs = data.get("jobs", [])
    if jobs:
        mismatched = [j for j in jobs if j.get("status") != "success"]
        assert not mismatched, (
            f"All jobs returned with status=success filter must have status='success'. "
            f"Mismatched jobs: {mismatched}"
        )
        logger.info(
            "status=success filter returned %d job(s); all have correct status",
            len(jobs),
        )
    else:
        logger.info("No success jobs found — empty list is acceptable")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_c_list_jobs_with_all_status_filters(
    api_client: httpx.AsyncClient,
) -> None:
    """
    GET /api/ingestion/jobs?status=<value> must return 200 for all valid status values.

    Iterates through every valid status literal and verifies the endpoint
    accepts it (HTTP 200).  If the returned list is non-empty each job's
    status must match the filter value.
    """
    for status in _VALID_STATUSES:
        response = await api_client.get(
            f"/api/ingestion/jobs?status={status}&limit=1"
        )
        await assert_status(
            response, 200, f"GET /api/ingestion/jobs?status={status}"
        )
        data = response.json()
        jobs = data.get("jobs", [])
        if jobs:
            assert jobs[0].get("status") == status, (
                f"First job with status filter '{status}' must have status='{status}'. "
                f"Got: {jobs[0].get('status')}"
            )
        logger.info(
            "status=%s filter: total=%d, returned=%d",
            status,
            data.get("total", 0),
            len(jobs),
        )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_d_ingestion_stats_overall(api_client: httpx.AsyncClient) -> None:
    """
    GET /api/ingestion/stats must return 200 with aggregate statistics.

    The stats are nested under a 'stats' key in the response.  total_jobs
    must be a non-negative int; by_status must be a dict.
    """
    response = await api_client.get("/api/ingestion/stats")
    await assert_status(response, 200, "GET /api/ingestion/stats")
    data = response.json()

    # The route returns IngestionStatsResponse: {stats: {...}, project_id: ...}
    assert "stats" in data, (
        f"Response must include a 'stats' field. Got keys: {list(data.keys())}"
    )
    stats = data["stats"]

    assert "total_jobs" in stats, (
        f"'stats' must include 'total_jobs'. Got keys: {list(stats.keys())}"
    )
    assert isinstance(stats["total_jobs"], int) and stats["total_jobs"] >= 0, (
        f"'total_jobs' must be a non-negative int, got {stats['total_jobs']!r}"
    )

    assert "by_status" in stats, (
        f"'stats' must include 'by_status'. Got keys: {list(stats.keys())}"
    )
    assert isinstance(stats["by_status"], dict), (
        f"'by_status' must be a dict, got {type(stats['by_status'])}"
    )

    logger.info(
        "Overall ingestion stats: total_jobs=%d, by_status=%s",
        stats["total_jobs"],
        stats["by_status"],
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e_ingestion_stats_by_project(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    GET /api/ingestion/stats?project_id={id} must return 200 when a valid project exists.

    Uses the project_id stored by earlier test files.  If no project_id has
    been captured yet, the test is skipped rather than failing.
    """
    project_id = e2e_state.get("project_id")
    if not project_id:
        pytest.skip("No project_id in e2e_state — run project creation tests first")

    response = await api_client.get(
        f"/api/ingestion/stats?project_id={project_id}"
    )
    await assert_status(
        response, 200, f"GET /api/ingestion/stats?project_id={project_id}"
    )
    data = response.json()

    assert "stats" in data, (
        f"Response must include a 'stats' field. Got keys: {list(data.keys())}"
    )
    stats = data["stats"]
    assert "total_jobs" in stats, (
        f"'stats' must include 'total_jobs'. Got: {stats}"
    )
    assert isinstance(stats["total_jobs"], int) and stats["total_jobs"] >= 0, (
        f"'total_jobs' must be a non-negative int, got {stats['total_jobs']!r}"
    )

    logger.info(
        "Project-scoped ingestion stats for project_id=%s: total_jobs=%d",
        project_id,
        stats["total_jobs"],
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_f_get_most_recent_job_if_exists(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    GET /api/ingestion/jobs/{id} must return 200 with full job details for a known job.

    Fetches the most recent ingestion job from the list endpoint.  If no jobs
    exist the test logs an info message and returns early without failing.
    Stores the job id in e2e_state for use by test_g.
    """
    list_response = await api_client.get("/api/ingestion/jobs?limit=1")
    await assert_status(list_response, 200, "GET /api/ingestion/jobs?limit=1 (for test_f)")
    list_data = list_response.json()

    if list_data.get("total", 0) == 0:
        logger.info(
            "No ingestion jobs found in the database — "
            "skipping job detail sub-test (this is not a failure)"
        )
        return

    job_summary = list_data["jobs"][0]
    job_id = _extract_id(job_summary)
    assert job_id, (
        f"First job in list must have an id field. Got: {job_summary}"
    )

    detail_response = await api_client.get(f"/api/ingestion/jobs/{job_id}")
    await assert_status(
        detail_response, 200, f"GET /api/ingestion/jobs/{job_id}"
    )
    data = detail_response.json()

    assert "status" in data, (
        f"Job detail must include 'status'. Got keys: {list(data.keys())}"
    )
    assert data["status"] in _VALID_STATUSES, (
        f"Job status must be one of {_VALID_STATUSES}, got '{data['status']}'"
    )
    assert "filename" in data, (
        f"Job detail must include 'filename'. Got keys: {list(data.keys())}"
    )

    e2e_state["test_job_id"] = job_id
    logger.info(
        "Most recent job id=%s: status=%s, filename='%s'",
        job_id,
        data.get("status"),
        data.get("filename"),
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_g_job_has_required_fields(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    GET /api/ingestion/jobs/{id} must return all required fields with correct types.

    Verifies the full IngestionJobResponse contract for the job captured in
    test_f.  Checks that progress_pct is in range 0–100 and that successfully
    completed jobs have progress_pct == 100.  'partial' and 'failed' jobs may
    have any progress_pct value.  Skipped if no job was found in test_f.
    """
    test_job_id = e2e_state.get("test_job_id")
    if not test_job_id:
        pytest.skip(
            "No test_job_id in e2e_state — test_f found no ingestion jobs"
        )

    response = await api_client.get(f"/api/ingestion/jobs/{test_job_id}")
    await assert_status(
        response, 200, f"GET /api/ingestion/jobs/{test_job_id} (required fields check)"
    )
    data = response.json()

    # Verify id field (serialization alias may be '_id' or 'id').
    job_id_value = data.get("_id") or data.get("id")
    assert job_id_value, (
        f"Job response must include '_id' or 'id'. Got keys: {list(data.keys())}"
    )

    # Required string fields.
    for required_field in ("filename", "status"):
        assert required_field in data, (
            f"Job response must include '{required_field}'. Got keys: {list(data.keys())}"
        )
        assert isinstance(data[required_field], str) and data[required_field], (
            f"'{required_field}' must be a non-empty string, got {data[required_field]!r}"
        )

    # progress_pct must be in [0, 100].
    assert "progress_pct" in data, (
        f"Job response must include 'progress_pct'. Got keys: {list(data.keys())}"
    )
    pct = data["progress_pct"]
    assert isinstance(pct, int) and 0 <= pct <= 100, (
        f"progress_pct must be an int in [0, 100], got {pct!r}"
    )

    # Only 'success' status guarantees 100% progress.
    # 'partial' means the job ended with some errors (not all steps completed),
    # so progress_pct may not be 100.  'failed' jobs may have stopped early.
    if data["status"] == "success":
        assert pct == 100, (
            f"A job with status 'success' must have progress_pct=100, "
            f"got {pct}"
        )

    logger.info(
        "Job %s required fields validated: status=%s, progress_pct=%d",
        test_job_id,
        data.get("status"),
        pct,
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_h_list_jobs_pagination(api_client: httpx.AsyncClient) -> None:
    """
    GET /api/ingestion/jobs with limit=1&skip=0 and limit=1&skip=1 must return
    different jobs when at least 2 jobs exist.

    Verifies that the skip parameter advances the result window correctly.
    If fewer than 2 jobs are in the database the test returns early to avoid
    a false failure on an empty or near-empty environment.
    """
    # Get the total count first.
    stats_response = await api_client.get("/api/ingestion/stats")
    await assert_status(stats_response, 200, "GET /api/ingestion/stats (for pagination check)")
    stats_data = stats_response.json()
    total = stats_data.get("stats", {}).get("total_jobs", 0)

    if total < 2:
        logger.info(
            "Only %d ingestion job(s) found — need at least 2 to test pagination. "
            "Returning early.",
            total,
        )
        return

    first_response = await api_client.get("/api/ingestion/jobs?limit=1&skip=0")
    await assert_status(first_response, 200, "GET /api/ingestion/jobs?limit=1&skip=0")
    first_data = first_response.json()

    second_response = await api_client.get("/api/ingestion/jobs?limit=1&skip=1")
    await assert_status(second_response, 200, "GET /api/ingestion/jobs?limit=1&skip=1")
    second_data = second_response.json()

    first_jobs = first_data.get("jobs", [])
    second_jobs = second_data.get("jobs", [])

    assert first_jobs, "First page (skip=0) must contain at least one job"
    assert second_jobs, "Second page (skip=1) must contain at least one job"

    first_id = _extract_id(first_jobs[0])
    second_id = _extract_id(second_jobs[0])

    assert first_id != second_id, (
        f"Pagination: job at skip=0 and job at skip=1 must be different. "
        f"Both returned id='{first_id}'"
    )
    logger.info(
        "Pagination verified: page-0 id=%s, page-1 id=%s (total=%d)",
        first_id,
        second_id,
        total,
    )


# ---------------------------------------------------------------------------
# Error / failure tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_fail1_get_nonexistent_job(api_client: httpx.AsyncClient) -> None:
    """
    GET /api/ingestion/jobs/{id} with a valid-format but nonexistent ObjectId must
    return HTTP 404 (NotFoundError).
    """
    response = await api_client.get(
        f"/api/ingestion/jobs/{_NONEXISTENT_JOB_ID}"
    )
    await assert_status(
        response, 404,
        f"GET /api/ingestion/jobs/{_NONEXISTENT_JOB_ID} must return 404"
    )
    logger.info(
        "GET nonexistent ingestion job correctly returned 404: %s",
        response.text[:200],
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_fail2_delete_nonexistent_job(api_client: httpx.AsyncClient) -> None:
    """
    DELETE /api/ingestion/jobs/{id} with a valid-format but nonexistent ObjectId must
    return HTTP 404.

    Verifies the API does not silently succeed when deleting a record that
    does not exist.
    """
    response = await api_client.delete(
        f"/api/ingestion/jobs/{_NONEXISTENT_JOB_ID}"
    )
    await assert_status(
        response, 404,
        f"DELETE /api/ingestion/jobs/{_NONEXISTENT_JOB_ID} must return 404"
    )
    logger.info(
        "DELETE nonexistent ingestion job correctly returned 404: %s",
        response.text[:200],
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_fail3_invalid_status_filter(api_client: httpx.AsyncClient) -> None:
    """
    GET /api/ingestion/jobs?status=invalid_status must return HTTP 422.

    The status query parameter is passed to IngestionJobFilter which declares
    it as a Literal type.  Pydantic raises a ValidationError that FastAPI
    converts to 422 Unprocessable Entity when the value is not one of the
    allowed literals.
    """
    response = await api_client.get("/api/ingestion/jobs?status=invalid_status")
    await assert_status(
        response, 422,
        "GET /api/ingestion/jobs?status=invalid_status must return 422"
    )
    logger.info(
        "Invalid status filter correctly returned 422: %s",
        response.text[:200],
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_fail4_jobs_limit_out_of_range(
    api_client: httpx.AsyncClient,
) -> None:
    """
    GET /api/ingestion/jobs with out-of-range limit values must be rejected or clamped.

    The route declares limit as Query(50, ge=1, le=100).
    - limit=0  is below the ge=1 constraint → FastAPI must return 422.
    - limit=10000 is above the le=100 constraint → FastAPI must return 422.

    Both calls must return 422 Unprocessable Entity.
    """
    # Below minimum.
    below_response = await api_client.get("/api/ingestion/jobs?limit=0")
    logger.info(
        "GET /api/ingestion/jobs?limit=0 returned %d: %s",
        below_response.status_code,
        below_response.text[:200],
    )
    assert below_response.status_code == 422, (
        f"limit=0 is below ge=1 — expected 422, got {below_response.status_code}: "
        f"{below_response.text[:300]}"
    )

    # Above maximum.
    above_response = await api_client.get("/api/ingestion/jobs?limit=10000")
    logger.info(
        "GET /api/ingestion/jobs?limit=10000 returned %d: %s",
        above_response.status_code,
        above_response.text[:200],
    )
    assert above_response.status_code == 422, (
        f"limit=10000 is above le=100 — expected 422, got {above_response.status_code}: "
        f"{above_response.text[:300]}"
    )
