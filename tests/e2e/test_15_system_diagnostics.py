"""
System diagnostics E2E tests.

Covers the root health endpoint, the /api/system/* health and index endpoints,
the /api/system/verify-document/{id} endpoint, and the /api/admin/background-tasks/*
admin endpoints.

Tests run in alphabetical order enforced by the letter/fail prefix.
No test fails simply because the database is empty — only genuine API contract
violations (wrong status code, missing required fields, wrong field types) cause
test failures.
"""

import logging

import httpx
import pytest

from tests.e2e.conftest import assert_status

logger = logging.getLogger(__name__)

# A valid-format ObjectId that is guaranteed not to exist in any real database.
_NONEXISTENT_DOC_ID = "000000000000000000000001"

# Collection names that must always be present in the health response.
_EXPECTED_COLLECTIONS = [
    "documents",
    "chunks",
    "qa_sessions",
    "qa_pairs",
]


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_a_root_health_endpoint(api_client: httpx.AsyncClient) -> None:
    """
    GET /health (root, not /api/system/health) must return 200 with status 'ok'.

    The root endpoint is a lightweight liveness probe that does not perform
    any database queries.  It must always return HTTP 200 when the Python
    process is running and the status field must equal 'ok'.
    """
    response = await api_client.get("/health")
    await assert_status(response, 200, "GET /health")
    data = response.json()

    assert "status" in data, (
        f"Root /health must include a 'status' field. Got keys: {list(data.keys())}"
    )
    assert data["status"] in ("ok", "healthy"), (
        f"Root /health status must be 'ok' or 'healthy', got '{data['status']}'"
    )
    logger.info("Root /health returned status='%s'", data.get("status"))


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_b_system_health_check(api_client: httpx.AsyncClient) -> None:
    """
    GET /api/system/health must always return HTTP 200 with a valid status string.

    The endpoint is designed to be always-available so callers can inspect the
    health payload even when the system is degraded.  The database must be
    connected (the backend is running), and latency_ms must be a non-negative
    number.
    """
    response = await api_client.get("/api/system/health")
    await assert_status(response, 200, "GET /api/system/health")
    data = response.json()

    assert "status" in data, (
        f"/api/system/health must include a 'status' field. Got keys: {list(data.keys())}"
    )
    assert data["status"] in ("healthy", "degraded", "unhealthy"), (
        f"status must be one of healthy/degraded/unhealthy, got '{data['status']}'"
    )

    assert "database" in data, (
        f"/api/system/health must include a 'database' field. Got keys: {list(data.keys())}"
    )
    db_info = data["database"]
    assert "connected" in db_info, (
        f"'database' must contain a 'connected' field. Got: {db_info}"
    )
    assert db_info["connected"] is True, (
        "Database must be connected when the backend is running. "
        f"Got connected={db_info.get('connected')}. Error: {db_info.get('error')}"
    )

    assert "latency_ms" in db_info, (
        f"'database' must contain a 'latency_ms' field. Got: {db_info}"
    )
    latency_ms = db_info["latency_ms"]
    assert isinstance(latency_ms, (int, float)), (
        f"latency_ms must be numeric, got {type(latency_ms)}: {latency_ms}"
    )
    assert latency_ms >= 0, (
        f"latency_ms must be non-negative, got {latency_ms}"
    )

    assert "collections" in data, (
        f"/api/system/health must include a 'collections' field. Got keys: {list(data.keys())}"
    )

    logger.info(
        "System health: status=%s, db_latency=%.1fms",
        data["status"],
        latency_ms,
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_c_system_health_collections_present(
    api_client: httpx.AsyncClient,
) -> None:
    """
    GET /api/system/health must return a collections dict containing core collection names.

    This is a soft test: we log a warning if an expected collection is missing
    rather than failing, because collection names are configurable.  If a
    collection IS present its document_count must be a non-negative integer.
    """
    response = await api_client.get("/api/system/health")
    await assert_status(response, 200, "GET /api/system/health (collections check)")
    data = response.json()

    collections = data.get("collections", {})
    assert isinstance(collections, dict), (
        f"'collections' field must be a dict, got {type(collections)}"
    )

    for expected_name in _EXPECTED_COLLECTIONS:
        # Soft check: the configured collection name may differ from the canonical name.
        matched = [k for k in collections if expected_name in k]
        if not matched:
            logger.warning(
                "Expected collection name '%s' not found in health response. "
                "Collections present: %s",
                expected_name,
                list(collections.keys()),
            )
            continue

        for key in matched:
            coll_info = collections[key]
            assert "document_count" in coll_info, (
                f"Collection '{key}' in health response must have 'document_count'. "
                f"Got: {coll_info}"
            )
            count = coll_info["document_count"]
            assert isinstance(count, int) and count >= 0, (
                f"Collection '{key}' document_count must be a non-negative int, "
                f"got {count!r}"
            )
            logger.info(
                "Collection '%s': document_count=%d, status=%s",
                key,
                count,
                coll_info.get("status"),
            )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_d_index_status(api_client: httpx.AsyncClient) -> None:
    """
    GET /api/system/index-status must return 200 with at least a vector_index or
    recommendations field.

    This is a soft test: we do not assert that the index is ready (it may be
    building or empty on a fresh environment), only that the endpoint responds
    with a well-formed payload.
    """
    response = await api_client.get("/api/system/index-status")
    await assert_status(response, 200, "GET /api/system/index-status")
    data = response.json()

    # At minimum one of these keys must be present.
    assert "vector_index" in data or "recommendations" in data, (
        f"index-status response must include 'vector_index' or 'recommendations'. "
        f"Got keys: {list(data.keys())}"
    )

    if "recommendations" in data:
        assert isinstance(data["recommendations"], list), (
            f"'recommendations' must be a list, got {type(data['recommendations'])}"
        )

    if "vector_index" in data:
        vi = data["vector_index"]
        assert "name" in vi, (
            f"'vector_index' must include a 'name' field. Got: {vi}"
        )
        assert "status" in vi, (
            f"'vector_index' must include a 'status' field. Got: {vi}"
        )
        logger.info(
            "Vector index: name='%s', status='%s'",
            vi.get("name"),
            vi.get("status"),
        )

    if "verification" in data:
        verification = data["verification"]
        assert "searchable" in verification, (
            f"'verification' must include 'searchable'. Got: {verification}"
        )
        logger.info(
            "Index verification: searchable=%s, chunks_found=%d",
            verification.get("searchable"),
            verification.get("chunks_found", 0),
        )

    logger.info(
        "Index status recommendations (%d): %s",
        len(data.get("recommendations", [])),
        data.get("recommendations"),
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e_verify_nonexistent_document(
    api_client: httpx.AsyncClient,
) -> None:
    """
    GET /api/system/verify-document/{id} with a valid-format but nonexistent ObjectId
    must return HTTP 200 with exists=False and chunks_in_database=0.

    The endpoint always returns 200; it uses the payload to communicate
    non-existence rather than returning 404.
    """
    url = (
        f"/api/system/verify-document/{_NONEXISTENT_DOC_ID}"
        "?max_retries=1&retry_delay_seconds=0.5"
    )
    response = await api_client.get(url)
    await assert_status(response, 200, f"GET {url}")
    data = response.json()

    assert "exists" in data, (
        f"verify-document response must include 'exists'. Got keys: {list(data.keys())}"
    )
    assert data["exists"] is False, (
        f"A nonexistent document must have exists=False, got {data['exists']}"
    )

    assert "chunks_in_database" in data, (
        f"verify-document response must include 'chunks_in_database'. Got: {data}"
    )
    assert data["chunks_in_database"] == 0, (
        f"A nonexistent document must have chunks_in_database=0, "
        f"got {data['chunks_in_database']}"
    )

    logger.info(
        "verify-document for nonexistent id returned: exists=%s, message='%s'",
        data.get("exists"),
        data.get("message"),
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_f_verify_invalid_document_id_format(
    api_client: httpx.AsyncClient,
) -> None:
    """
    GET /api/system/verify-document/{id} with a string that is not a valid
    MongoDB ObjectId must return HTTP 400 (ValidationError).

    The endpoint calls validate_object_id() which raises a ValidationError
    that the middleware converts to HTTP 400.
    """
    response = await api_client.get("/api/system/verify-document/not_a_valid_objectid")
    await assert_status(
        response, 400,
        "GET /api/system/verify-document/not_a_valid_objectid must return 400"
    )
    logger.info(
        "verify-document with invalid ObjectId correctly returned 400: %s",
        response.text[:200],
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_g_admin_background_tasks_status(
    api_client: httpx.AsyncClient,
) -> None:
    """
    GET /api/admin/background-tasks/status must return a valid structure.

    The current admin implementation does not enforce a hard API key check
    (verify_admin_key always returns True), so this is expected to return 200.
    If a future implementation adds real auth and returns 401, the test logs
    the behaviour instead of failing the suite.
    """
    response = await api_client.get("/api/admin/background-tasks/status")

    if response.status_code == 401:
        logger.warning(
            "Admin endpoint returned 401 — skipping structure assertion. "
            "Add X-Admin-Key header if auth is required."
        )
        return

    await assert_status(response, 200, "GET /api/admin/background-tasks/status")
    data = response.json()

    assert "enabled" in data, (
        f"background-tasks/status must include 'enabled'. Got keys: {list(data.keys())}"
    )
    assert "running" in data, (
        f"background-tasks/status must include 'running'. Got keys: {list(data.keys())}"
    )
    assert isinstance(data["enabled"], bool), (
        f"'enabled' must be a bool, got {type(data['enabled'])}"
    )
    assert isinstance(data["running"], bool), (
        f"'running' must be a bool, got {type(data['running'])}"
    )

    logger.info(
        "Admin background-tasks status: enabled=%s, running=%s",
        data.get("enabled"),
        data.get("running"),
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_h_system_health_is_not_unhealthy(
    api_client: httpx.AsyncClient,
) -> None:
    """
    GET /api/system/health must not return 'unhealthy' when the backend is running.

    'unhealthy' means the MongoDB connection has failed entirely, which would
    make the backend non-functional.  A 'degraded' status (e.g. empty collections)
    is acceptable and is logged as a warning; 'unhealthy' causes an explicit
    test failure with an informative message.
    """
    response = await api_client.get("/api/system/health")
    await assert_status(response, 200, "GET /api/system/health (not-unhealthy check)")
    data = response.json()

    status = data.get("status", "unknown")

    if status == "unhealthy":
        db_info = data.get("database", {})
        pytest.fail(
            f"Backend health is 'unhealthy' — possible database connection issue. "
            f"Database info: {db_info}. "
            f"Full response: {data}"
        )

    if status == "degraded":
        logger.warning(
            "Backend health is 'degraded' — some collections may be empty or "
            "the vector index may be missing. Collections: %s",
            data.get("collections", {}),
        )

    assert status in ("healthy", "degraded"), (
        f"Expected health status 'healthy' or 'degraded', got '{status}'"
    )
    logger.info("System health status confirmed acceptable: '%s'", status)


# ---------------------------------------------------------------------------
# Error / failure tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_fail1_verify_document_bad_objectid(
    api_client: httpx.AsyncClient,
) -> None:
    """
    GET /api/system/verify-document/{id} with a completely invalid id string must
    return HTTP 400.

    Complements test_f which uses a different invalid string; here we use a
    string that is clearly not hex-encoded.
    """
    response = await api_client.get(
        "/api/system/verify-document/this_is_not_a_valid_id_at_all"
    )
    await assert_status(
        response, 400,
        "GET /api/system/verify-document/this_is_not_a_valid_id_at_all must return 400"
    )
    logger.info(
        "verify-document with invalid id correctly returned 400: %s",
        response.text[:200],
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_fail2_index_status_with_invalid_document_id(
    api_client: httpx.AsyncClient,
) -> None:
    """
    GET /api/system/index-status?document_id=not_valid must return 400 or 422.

    When an invalid document_id query parameter is supplied the endpoint may
    validate it and return 400 (ValidationError) or FastAPI may return 422
    (query parameter type mismatch).  Both indicate the API is correctly
    rejecting the bad input.
    """
    response = await api_client.get("/api/system/index-status?document_id=not_valid")
    assert response.status_code in (400, 422), (
        f"GET /api/system/index-status?document_id=not_valid must return 400 or 422, "
        f"got {response.status_code}: {response.text[:300]}"
    )
    logger.info(
        "index-status with invalid document_id returned %d (expected 400 or 422): %s",
        response.status_code,
        response.text[:200],
    )
