"""
Dashboard analytics E2E tests.

The dashboard endpoints aggregate MongoDB data and expose read-only
statistics to the frontend.  Every endpoint must:

- Return HTTP 200 regardless of whether there is data in the database.
- Return a valid JSON object with the documented top-level keys.
- Produce sensible numeric values (counts >= 0, ratios in [0, 1]).

Tests are purely read-only — no inserts, updates, or deletes are made.
By the time this file runs, earlier test files (02–08) will have created
at least one project, session, and Q&A pair, so summary counts > 0 can be
asserted where appropriate.

Run order: a–k (happy path), fail1–fail3 (validation error path).
"""

import logging

import httpx
import pytest

from tests.e2e.conftest import assert_status

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Happy-path tests — one per endpoint
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_a_dashboard_summary(api_client: httpx.AsyncClient) -> None:
    """Verify the summary endpoint returns counts and a generated_at timestamp.

    By the time this test runs, at least one project has been created by the
    project creation tests (test_02).  Therefore project_count must be >= 1.
    All numeric counters must be non-negative integers and good_ratio (if
    present) must lie in [0.0, 1.0].
    """
    response = await api_client.get("/api/dashboard/summary")
    await assert_status(response, 200, "GET /api/dashboard/summary")

    data = response.json()

    for required_key in ("project_count", "session_count", "qa_pair_count"):
        assert required_key in data, (
            f"Summary response must include '{required_key}'. "
            f"Keys found: {list(data.keys())}"
        )
        value = data[required_key]
        assert isinstance(value, int) and value >= 0, (
            f"'{required_key}' must be a non-negative integer, got {value!r}"
        )

    # At minimum one project must exist (created in test_02)
    assert data["project_count"] > 0, (
        f"project_count must be > 0 after project creation tests. "
        f"Got project_count={data['project_count']}"
    )

    # generated_at must be present as a timestamp string
    assert "generated_at" in data, (
        f"Summary response must include 'generated_at'. Keys: {list(data.keys())}"
    )
    assert data["generated_at"], (
        "'generated_at' must not be empty or null"
    )

    logger.info(
        "Dashboard summary — projects=%d, sessions=%d, qa_pairs=%d, generated_at=%s",
        data["project_count"],
        data["session_count"],
        data["qa_pair_count"],
        data["generated_at"],
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_b_distribution_by_region(api_client: httpx.AsyncClient) -> None:
    """Verify the region distribution endpoint returns dicts for projects and sessions.

    Even with zero data, the endpoint must return the 'projects' and
    'sessions' keys mapping to a dict (possibly empty).  With data created
    by earlier tests, at least one of the dicts must be non-empty.
    """
    response = await api_client.get("/api/dashboard/distribution/region")
    await assert_status(response, 200, "GET /api/dashboard/distribution/region")

    data = response.json()
    assert "projects" in data, (
        f"Region distribution must include 'projects' key. Keys: {list(data.keys())}"
    )
    assert isinstance(data["projects"], dict), (
        f"'projects' must be a dict, got {type(data['projects'])}"
    )
    logger.info(
        "Region distribution — %d project regions, %d session regions",
        len(data.get("projects", {})),
        len(data.get("sessions", {})),
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_c_distribution_by_industry(api_client: httpx.AsyncClient) -> None:
    """Verify the industry distribution endpoint returns an 'industries' dict.

    The dict maps industry codes to counts.  With at least one project
    created in the 'it' industry (test_02), the 'industries' dict must
    not be empty.
    """
    response = await api_client.get("/api/dashboard/distribution/industry")
    await assert_status(response, 200, "GET /api/dashboard/distribution/industry")

    data = response.json()
    assert "industries" in data, (
        f"Industry distribution must include 'industries' key. Keys: {list(data.keys())}"
    )
    assert isinstance(data["industries"], dict), (
        f"'industries' must be a dict, got {type(data['industries'])}"
    )
    logger.info(
        "Industry distribution — %d industries tracked", len(data["industries"])
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_d_distribution_by_tax_office(api_client: httpx.AsyncClient) -> None:
    """Verify the tax-office distribution endpoint returns a list of office objects.

    Each item in 'tax_offices' must include at minimum a count field.  An
    empty list is acceptable if no projects have a tax_office_id assigned.
    """
    response = await api_client.get(
        "/api/dashboard/distribution/tax-office", params={"limit": 5}
    )
    await assert_status(
        response, 200, "GET /api/dashboard/distribution/tax-office?limit=5"
    )

    data = response.json()
    assert "tax_offices" in data, (
        f"Tax-office distribution must include 'tax_offices' key. Keys: {list(data.keys())}"
    )
    assert isinstance(data["tax_offices"], list), (
        f"'tax_offices' must be a list, got {type(data['tax_offices'])}"
    )
    logger.info(
        "Tax-office distribution — %d offices with projects", len(data["tax_offices"])
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e_trends_default(api_client: httpx.AsyncClient) -> None:
    """Verify the trends endpoint with default parameters (30 days, daily granularity).

    The response must echo back the requested period_days and granularity,
    and include 'projects', 'sessions', and 'qa_pairs' time-series arrays.
    Each time-series is allowed to be empty if no data falls in the window.
    """
    response = await api_client.get(
        "/api/dashboard/trends", params={"days": 30, "granularity": "day"}
    )
    await assert_status(response, 200, "GET /api/dashboard/trends?days=30&granularity=day")

    data = response.json()
    assert data.get("period_days") == 30, (
        f"Expected period_days=30, got {data.get('period_days')!r}"
    )
    assert data.get("granularity") == "day", (
        f"Expected granularity='day', got {data.get('granularity')!r}"
    )

    for series in ("projects", "sessions", "qa_pairs"):
        assert series in data, (
            f"Trends response must include '{series}' series. Keys: {list(data.keys())}"
        )
        assert isinstance(data[series], list), (
            f"'{series}' must be a list, got {type(data[series])}"
        )

    logger.info(
        "Trends (30d/day) — %d project data-points, %d session data-points",
        len(data.get("projects", [])),
        len(data.get("sessions", [])),
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_f_trends_weekly(api_client: httpx.AsyncClient) -> None:
    """Verify the trends endpoint accepts a 7-day window with weekly granularity.

    This exercises a different parameter combination from test_e and confirms
    the granularity and period_days are properly reflected in the response.
    """
    response = await api_client.get(
        "/api/dashboard/trends", params={"days": 7, "granularity": "week"}
    )
    await assert_status(response, 200, "GET /api/dashboard/trends?days=7&granularity=week")

    data = response.json()
    assert data.get("period_days") == 7, (
        f"Expected period_days=7, got {data.get('period_days')!r}"
    )
    assert data.get("granularity") == "week", (
        f"Expected granularity='week', got {data.get('granularity')!r}"
    )
    logger.info("Trends (7d/week) — period_days=%d, granularity=%s", 7, "week")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_g_quality_metrics(api_client: httpx.AsyncClient) -> None:
    """Verify the quality endpoint returns well-structured quality_metrics.

    The quality_metrics object must include at minimum 'total' and
    'good_ratio'.  The good_ratio must be a float in [0.0, 1.0] — the
    endpoint must clamp or default correctly even when zero Q&A pairs
    have been rated.
    """
    response = await api_client.get("/api/dashboard/quality")
    await assert_status(response, 200, "GET /api/dashboard/quality")

    data = response.json()
    assert "quality_metrics" in data, (
        f"Quality response must include 'quality_metrics'. Keys: {list(data.keys())}"
    )

    qm = data["quality_metrics"]
    assert isinstance(qm, dict), (
        f"'quality_metrics' must be a dict, got {type(qm)}"
    )
    # The API returns 'total_qa_pairs' (not 'total') as the count field
    assert "total_qa_pairs" in qm, (
        f"quality_metrics must include 'total_qa_pairs'. Keys: {list(qm.keys())}"
    )
    assert "good_ratio" in qm, (
        f"quality_metrics must include 'good_ratio'. Keys: {list(qm.keys())}"
    )

    good_ratio = qm.get("good_ratio", 0)
    assert isinstance(good_ratio, (int, float)), (
        f"'good_ratio' must be numeric, got {type(good_ratio)}"
    )
    assert 0.0 <= float(good_ratio) <= 1.0, (
        f"'good_ratio' must be in [0, 1], got {good_ratio}"
    )
    logger.info(
        "Quality metrics — total_qa_pairs=%s, good_ratio=%.3f",
        qm.get("total_qa_pairs"),
        float(good_ratio),
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_h_stage_funnel(api_client: httpx.AsyncClient) -> None:
    """Verify the stage funnel endpoint returns funnel items and a total project count.

    The funnel represents how many projects are at each workflow stage.
    Both 'funnel' (list) and 'total_projects' (int >= 0) must be present.
    """
    response = await api_client.get("/api/dashboard/stage-funnel")
    await assert_status(response, 200, "GET /api/dashboard/stage-funnel")

    data = response.json()
    assert "funnel" in data, (
        f"Stage-funnel response must include 'funnel'. Keys: {list(data.keys())}"
    )
    assert isinstance(data["funnel"], list), (
        f"'funnel' must be a list, got {type(data['funnel'])}"
    )
    assert "total_projects" in data, (
        f"Stage-funnel response must include 'total_projects'. Keys: {list(data.keys())}"
    )
    total = data["total_projects"]
    assert isinstance(total, int) and total >= 0, (
        f"'total_projects' must be a non-negative integer, got {total!r}"
    )
    logger.info(
        "Stage funnel — %d funnel items, total_projects=%d",
        len(data["funnel"]),
        total,
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_i_quality_trend(api_client: httpx.AsyncClient) -> None:
    """Verify the quality trend endpoint returns a list of time-bucketed data points.

    Each data point in 'trend_data' represents one time bucket.  The list
    may be empty if no rated Q&A pairs exist in the window.
    """
    response = await api_client.get(
        "/api/dashboard/quality-trend", params={"days": 30, "granularity": "day"}
    )
    await assert_status(
        response, 200, "GET /api/dashboard/quality-trend?days=30&granularity=day"
    )

    data = response.json()
    assert "trend_data" in data, (
        f"Quality-trend response must include 'trend_data'. Keys: {list(data.keys())}"
    )
    assert isinstance(data["trend_data"], list), (
        f"'trend_data' must be a list, got {type(data['trend_data'])}"
    )
    logger.info(
        "Quality trend (30d/day) — %d data points", len(data["trend_data"])
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_j_kb_health(api_client: httpx.AsyncClient) -> None:
    """Verify the knowledge-base health endpoint returns document and chunk counts.

    At least one document must have been uploaded by test_01 (preflight).
    Counts must be non-negative integers and embedding_coverage_pct must
    be in [0.0, 100.0].
    """
    response = await api_client.get("/api/dashboard/kb-health")
    await assert_status(response, 200, "GET /api/dashboard/kb-health")

    data = response.json()

    for required_key in ("document_count", "chunk_count", "embedding_coverage_pct"):
        assert required_key in data, (
            f"KB health response must include '{required_key}'. "
            f"Keys found: {list(data.keys())}"
        )

    doc_count = data["document_count"]
    chunk_count = data["chunk_count"]
    coverage_pct = data["embedding_coverage_pct"]

    assert isinstance(doc_count, int) and doc_count >= 0, (
        f"'document_count' must be a non-negative integer, got {doc_count!r}"
    )
    assert isinstance(chunk_count, int) and chunk_count >= 0, (
        f"'chunk_count' must be a non-negative integer, got {chunk_count!r}"
    )
    assert isinstance(coverage_pct, (int, float)), (
        f"'embedding_coverage_pct' must be numeric, got {type(coverage_pct)}"
    )
    assert 0.0 <= float(coverage_pct) <= 100.0, (
        f"'embedding_coverage_pct' must be in [0, 100], got {coverage_pct}"
    )

    logger.info(
        "KB health — documents=%d, chunks=%d, embedding_coverage=%.1f%%",
        doc_count,
        chunk_count,
        float(coverage_pct),
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_k_system_metrics(api_client: httpx.AsyncClient) -> None:
    """Verify the system metrics endpoint returns at least one performance metric.

    The exact set of metrics may evolve; the test requires at minimum one of
    'query_count' or 'uptime_hours' to be present, confirming the endpoint
    is live and returning structured data rather than an empty body.
    """
    response = await api_client.get("/api/dashboard/system-metrics")
    await assert_status(response, 200, "GET /api/dashboard/system-metrics")

    data = response.json()
    assert isinstance(data, dict) and len(data) > 0, (
        "System metrics response must be a non-empty JSON object"
    )
    assert "query_count" in data or "uptime_hours" in data, (
        f"System metrics must include at least 'query_count' or 'uptime_hours'. "
        f"Keys found: {list(data.keys())}"
    )
    logger.info("System metrics — keys: %s", list(data.keys()))


# ---------------------------------------------------------------------------
# Error-path tests — validation rejection
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_fail1_trends_invalid_granularity(
    api_client: httpx.AsyncClient,
) -> None:
    """An unrecognised granularity value must be rejected with 422 Unprocessable Entity.

    The granularity query parameter is declared as Literal["day", "week",
    "month"].  Passing any other value violates the enum constraint and
    FastAPI must return 422 with a validation error detail.
    """
    response = await api_client.get(
        "/api/dashboard/trends",
        params={"days": 30, "granularity": "invalid_value"},
    )
    assert response.status_code == 422, (
        f"Invalid granularity must return HTTP 422. "
        f"Got {response.status_code}: {response.text[:300]}"
    )
    data = response.json()
    assert "detail" in data, (
        f"422 response must include 'detail'. Keys: {list(data.keys())}"
    )
    logger.info(
        "Invalid granularity correctly rejected with 422. Detail: %s",
        str(data.get("detail", ""))[:200],
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_fail2_trends_days_out_of_range(
    api_client: httpx.AsyncClient,
) -> None:
    """A days value exceeding the maximum (365) must be rejected with 422.

    The trends endpoint declares `days: int = Query(ge=1, le=365)`.
    Passing days=999 violates the upper bound and must produce a FastAPI
    validation error (HTTP 422), not a 500 or a silent truncation.
    """
    response = await api_client.get(
        "/api/dashboard/trends",
        params={"days": 999, "granularity": "day"},
    )
    assert response.status_code == 422, (
        f"days=999 exceeds maximum (365) and must return HTTP 422. "
        f"Got {response.status_code}: {response.text[:300]}"
    )
    data = response.json()
    assert "detail" in data, (
        f"422 response must include 'detail'. Keys: {list(data.keys())}"
    )
    logger.info(
        "days=999 correctly rejected with 422. Detail: %s",
        str(data.get("detail", ""))[:200],
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_fail3_tax_office_distribution_invalid_limit(
    api_client: httpx.AsyncClient,
) -> None:
    """A limit of 0 for tax-office distribution must be rejected with 422.

    The endpoint declares `limit: int = Query(ge=1, le=100)`.  Passing
    limit=0 violates the lower bound and must produce a FastAPI validation
    error (HTTP 422) — not a 500 or an empty result set.
    """
    response = await api_client.get(
        "/api/dashboard/distribution/tax-office", params={"limit": 0}
    )
    assert response.status_code == 422, (
        f"limit=0 violates ge=1 constraint and must return HTTP 422. "
        f"Got {response.status_code}: {response.text[:300]}"
    )
    data = response.json()
    assert "detail" in data, (
        f"422 response must include 'detail'. Keys: {list(data.keys())}"
    )
    logger.info(
        "limit=0 for tax-office distribution correctly rejected with 422. Detail: %s",
        str(data.get("detail", ""))[:200],
    )
