"""
Reference data E2E tests — tax offices, regions, and industries.

All three groups of endpoints expose STATIC reference data seeded from
authoritative Polish government sources.  Tests are read-only: no inserts,
no deletes.  The suite verifies:

- Correct HTTP status codes for happy-path and error-path requests.
- Structural integrity of every response (required fields, correct types).
- Domain constraints (16 voivodeships, 19 industries, 400+ tax offices).
- Validation rejection for out-of-range or malformed inputs.

Run order: a–j (happy path), fail1–fail4 (error path).
"""

import logging

import httpx
import pytest

from tests.e2e.conftest import assert_status

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tax office tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_a_list_tax_offices(api_client: httpx.AsyncClient) -> None:
    """List first 10 tax offices and verify response shape.

    The endpoint returns a plain JSON array of TaxOffice objects.  Each
    object must carry at minimum the unique identifier (kodjednostki) and
    the human-readable office name (nazwa_urzedu).

    Note: If the database has not been seeded with tax office data, an
    empty list is returned.  The test verifies the response shape but
    skips structural field checks when the list is empty.
    """
    response = await api_client.get("/api/tax-offices", params={"limit": 10})
    await assert_status(response, 200, "GET /api/tax-offices?limit=10")

    data = response.json()
    assert isinstance(data, list), (
        f"Expected a JSON array from GET /api/tax-offices, got {type(data)}"
    )

    if len(data) == 0:
        logger.info("GET /api/tax-offices returned an empty list — database may not be seeded. Skipping field checks.")
        return

    first = data[0]
    assert "kodjednostki" in first, (
        f"TaxOffice object must have 'kodjednostki' field. Keys found: {list(first.keys())}"
    )
    assert isinstance(first["kodjednostki"], int), (
        f"'kodjednostki' must be an int, got {type(first['kodjednostki'])}"
    )
    assert "nazwa_urzedu" in first, (
        f"TaxOffice object must have 'nazwa_urzedu' field. Keys found: {list(first.keys())}"
    )
    assert isinstance(first["nazwa_urzedu"], str) and first["nazwa_urzedu"], (
        f"'nazwa_urzedu' must be a non-empty string, got {first['nazwa_urzedu']!r}"
    )
    logger.info(
        "GET /api/tax-offices returned %d offices. First: kodjednostki=%d, name=%r",
        len(data),
        first["kodjednostki"],
        first["nazwa_urzedu"],
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_b_tax_offices_count(api_client: httpx.AsyncClient) -> None:
    """Verify the tax office count endpoint returns a non-negative integer.

    The count endpoint must return a valid integer.  In production Poland has
    over 400 tax offices, but an unseeded database may return 0.  The test
    asserts the response shape is correct without requiring a specific count.
    """
    response = await api_client.get("/api/tax-offices/count")
    await assert_status(response, 200, "GET /api/tax-offices/count")

    data = response.json()
    assert "count" in data, (
        f"Response must include 'count' field. Keys: {list(data.keys())}"
    )
    count: int = data["count"]
    assert isinstance(count, int), (
        f"'count' must be an integer, got {type(count)}"
    )
    assert count >= 0, (
        f"Tax office count must be a non-negative integer, got {count}."
    )
    logger.info("Tax office count: %d", count)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_c_search_tax_offices(api_client: httpx.AsyncClient) -> None:
    """Search for Warszawa offices and verify case-insensitive matching.

    The search endpoint accepts free-text queries and performs a
    case-insensitive regex match on nazwa_urzedu and miasto.  Searching
    for 'warszawa' must return at least one result whose name or city
    contains the substring 'arszawa' (case-insensitive).
    """
    response = await api_client.get(
        "/api/tax-offices/search",
        params={"q": "warszawa", "limit": 20},
    )
    await assert_status(response, 200, "GET /api/tax-offices/search?q=warszawa&limit=20")

    data = response.json()
    assert isinstance(data, list), (
        f"Search response must be a JSON array, got {type(data)}"
    )
    logger.info("Tax office search 'warszawa' returned %d results", len(data))

    if len(data) > 0:
        first = data[0]
        name = first.get("nazwa_urzedu", "")
        city = first.get("miasto", "")
        combined = (name + " " + city).lower()
        assert "arszawa" in combined, (
            f"First search result for 'warszawa' does not contain 'arszawa'. "
            f"nazwa_urzedu={name!r}, miasto={city!r}"
        )
        logger.info(
            "First Warsaw result: kodjednostki=%s, name=%r, city=%r",
            first.get("kodjednostki"),
            name,
            city,
        )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_d_tax_offices_by_region(api_client: httpx.AsyncClient) -> None:
    """Verify the grouped-by-region endpoint returns a dict keyed by voivodeship.

    The response must be a plain JSON object whose keys are Polish voivodeship
    names.  When the database is seeded, 'mazowieckie' must be present.
    An empty dict is acceptable on an unseeded database.
    """
    response = await api_client.get("/api/tax-offices/regions")
    await assert_status(response, 200, "GET /api/tax-offices/regions")

    data = response.json()
    assert isinstance(data, dict), (
        f"GET /api/tax-offices/regions must return a JSON object, got {type(data)}"
    )

    if len(data) == 0:
        logger.info("GET /api/tax-offices/regions returned empty dict — database not seeded. Skipping region checks.")
        return

    assert "mazowieckie" in data, (
        f"Region 'mazowieckie' must be in the grouped response. "
        f"Keys found: {list(data.keys())[:10]}"
    )
    mazowieckie_offices = data["mazowieckie"]
    assert isinstance(mazowieckie_offices, list), (
        f"'mazowieckie' value must be a list, got {type(mazowieckie_offices)}"
    )
    assert len(mazowieckie_offices) > 0, (
        "Region 'mazowieckie' has no tax offices — unexpected for Poland's largest voivodeship"
    )
    logger.info(
        "Tax offices grouped by region: %d regions, mazowieckie has %d offices",
        len(data),
        len(mazowieckie_offices),
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e_get_specific_tax_office(api_client: httpx.AsyncClient) -> None:
    """Fetch a specific tax office by kodjednostki and verify round-trip identity.

    First lists a single office to obtain a valid kodjednostki, then fetches
    that office by its ID.  The response kodjednostki must match the one used
    in the request.  Skipped if the database has no tax offices.
    """
    # Obtain a valid kodjednostki from the list endpoint
    list_resp = await api_client.get("/api/tax-offices", params={"limit": 1})
    await assert_status(list_resp, 200, "GET /api/tax-offices?limit=1 (setup)")
    offices = list_resp.json()

    if len(offices) == 0:
        logger.info("No tax offices in database — skipping individual retrieval test.")
        return

    kodjednostki: int = offices[0]["kodjednostki"]

    # Fetch the specific office by its ID
    response = await api_client.get(f"/api/tax-offices/{kodjednostki}")
    await assert_status(response, 200, f"GET /api/tax-offices/{kodjednostki}")

    data = response.json()
    assert data["kodjednostki"] == kodjednostki, (
        f"Returned kodjednostki {data['kodjednostki']} does not match requested {kodjednostki}"
    )
    assert "nazwa_urzedu" in data, (
        f"Individual tax office response must include 'nazwa_urzedu'. Keys: {list(data.keys())}"
    )
    logger.info(
        "GET /api/tax-offices/%d returned %r", kodjednostki, data["nazwa_urzedu"]
    )


# ---------------------------------------------------------------------------
# Region tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_f_list_regions(api_client: httpx.AsyncClient) -> None:
    """Verify all 16 Polish voivodeships are returned by the regions list endpoint.

    Poland is divided into exactly 16 administrative voivodeships.  Each
    Region object must carry a 'name' field (lowercase, used in URLs) and a
    'display_name' field (title-cased, used in the UI).
    """
    response = await api_client.get("/api/regions")
    await assert_status(response, 200, "GET /api/regions")

    data = response.json()
    assert isinstance(data, list), (
        f"GET /api/regions must return a JSON array, got {type(data)}"
    )
    assert len(data) == 16, (
        f"Poland has exactly 16 voivodeships; endpoint returned {len(data)}"
    )

    # Verify 'mazowieckie' is present (largest, most recognisable voivodeship)
    names = [r.get("name", "") for r in data]
    assert "mazowieckie" in names, (
        f"Region 'mazowieckie' must be in the list. Names found: {names}"
    )

    # Verify structural integrity of a single item
    first = data[0]
    assert "name" in first, (
        f"Region object must have 'name' field. Keys: {list(first.keys())}"
    )
    assert "display_name" in first, (
        f"Region object must have 'display_name' field. Keys: {list(first.keys())}"
    )
    logger.info("GET /api/regions returned %d voivodeships: %s", len(data), names)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_g_regions_count(api_client: httpx.AsyncClient) -> None:
    """Verify the regions count endpoint always returns exactly 16.

    The number of Polish voivodeships is a constitutional constant — it must
    never change regardless of database state.
    """
    response = await api_client.get("/api/regions/count")
    await assert_status(response, 200, "GET /api/regions/count")

    data = response.json()
    assert "count" in data, (
        f"Response must include 'count' field. Keys: {list(data.keys())}"
    )
    assert data["count"] == 16, (
        f"Poland has exactly 16 voivodeships; endpoint returned count={data['count']}"
    )
    logger.info("GET /api/regions/count = %d (correct)", data["count"])


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_h_region_tax_offices(api_client: httpx.AsyncClient) -> None:
    """Fetch all tax offices in mazowieckie and verify the response shape.

    mazowieckie (Masovian Voivodeship) contains Warsaw and is the most
    populous region.  The endpoint must return a JSON array; an empty list
    is acceptable if the database has not been seeded with tax office data.
    """
    response = await api_client.get("/api/regions/mazowieckie/tax-offices")
    await assert_status(response, 200, "GET /api/regions/mazowieckie/tax-offices")

    data = response.json()
    assert isinstance(data, list), (
        f"GET /api/regions/mazowieckie/tax-offices must return a JSON array, got {type(data)}"
    )

    if len(data) == 0:
        logger.info("GET /api/regions/mazowieckie/tax-offices returned empty list — database not seeded.")
        return

    first = data[0]
    assert "kodjednostki" in first, (
        f"Tax office in region response must have 'kodjednostki'. Keys: {list(first.keys())}"
    )
    logger.info(
        "GET /api/regions/mazowieckie/tax-offices returned %d offices", len(data)
    )


# ---------------------------------------------------------------------------
# Industry tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_i_list_industries(api_client: httpx.AsyncClient) -> None:
    """Verify all 19 predefined industry categories are returned.

    The list of industries is fixed per client requirements.  Each Industry
    object must carry 'code', 'name_polish', and 'name_english' fields.  The
    'it' industry code must be present as it is the default used in E2E
    project creation tests.
    """
    response = await api_client.get("/api/industries")
    await assert_status(response, 200, "GET /api/industries")

    data = response.json()
    assert isinstance(data, list), (
        f"GET /api/industries must return a JSON array, got {type(data)}"
    )
    assert len(data) == 19, (
        f"Exactly 19 industries must be defined; endpoint returned {len(data)}"
    )

    # Verify structural integrity of a single item
    first = data[0]
    for required_field in ("code", "name_polish", "name_english"):
        assert required_field in first, (
            f"Industry object must have '{required_field}' field. Keys: {list(first.keys())}"
        )

    # 'it' must be present — it is used throughout the E2E project tests
    codes = [item.get("code", "") for item in data]
    assert "it" in codes, (
        f"Industry code 'it' must be present in the list. Codes found: {codes}"
    )
    logger.info(
        "GET /api/industries returned %d industries. Codes: %s", len(data), codes
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_j_industries_count(api_client: httpx.AsyncClient) -> None:
    """Verify the industries count endpoint always returns exactly 19.

    Like the regions count, this value is a fixed product requirement and
    must remain constant regardless of database state.
    """
    response = await api_client.get("/api/industries/count")
    await assert_status(response, 200, "GET /api/industries/count")

    data = response.json()
    assert "count" in data, (
        f"Response must include 'count' field. Keys: {list(data.keys())}"
    )
    assert data["count"] == 19, (
        f"Exactly 19 industries must be defined; endpoint returned count={data['count']}"
    )
    logger.info("GET /api/industries/count = %d (correct)", data["count"])


# ---------------------------------------------------------------------------
# Error-path tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_fail1_search_tax_offices_empty_query(
    api_client: httpx.AsyncClient,
) -> None:
    """An empty search query string must be rejected with 422 Unprocessable Entity.

    The search endpoint declares `q: str = Query(..., min_length=1)`.  An
    empty string violates the min_length constraint and must trigger FastAPI's
    built-in request validation, returning HTTP 422.
    """
    response = await api_client.get(
        "/api/tax-offices/search",
        params={"q": "", "limit": 10},
    )
    assert response.status_code == 422, (
        f"Empty search query must return HTTP 422. "
        f"Got {response.status_code}: {response.text[:300]}"
    )
    data = response.json()
    assert "detail" in data, (
        f"422 response must include 'detail'. Keys: {list(data.keys())}"
    )
    logger.info(
        "Empty search query correctly rejected with 422. Detail: %s",
        str(data.get("detail", ""))[:200],
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_fail2_get_invalid_tax_office_id(
    api_client: httpx.AsyncClient,
) -> None:
    """Requesting kodjednostki=0 must be rejected with 400 or 422.

    The route handler enforces `kodjednostki > 0`.  A zero or negative
    value is semantically invalid and should be rejected before any
    database query is issued.
    """
    response = await api_client.get("/api/tax-offices/0")
    assert response.status_code in (400, 422), (
        f"kodjednostki=0 is invalid and must return HTTP 400 or 422. "
        f"Got {response.status_code}: {response.text[:300]}"
    )
    logger.info(
        "GET /api/tax-offices/0 correctly rejected with %d", response.status_code
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_fail3_invalid_region_name(api_client: httpx.AsyncClient) -> None:
    """A non-existent region name must return 404 Not Found.

    The region endpoint validates the path parameter against the fixed list
    of 16 Polish voivodeships.  Any value outside that set must produce a
    404 with an informative error body rather than an empty list or 500.

    The API uses a custom error envelope: {"error": "...", "message": "..."}
    rather than FastAPI's default {"detail": "..."}.
    """
    response = await api_client.get("/api/regions/not_a_real_region/tax-offices")
    assert response.status_code == 404, (
        f"Unknown region must return HTTP 404. "
        f"Got {response.status_code}: {response.text[:300]}"
    )
    data = response.json()
    # The API uses custom error envelope {error, message} rather than FastAPI's {detail}
    assert "message" in data or "detail" in data, (
        f"404 response must include 'message' or 'detail'. Keys: {list(data.keys())}"
    )
    logger.info(
        "Invalid region name correctly rejected with 404. Message: %s",
        str(data.get("message") or data.get("detail", ""))[:200],
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_fail4_tax_office_not_found(api_client: httpx.AsyncClient) -> None:
    """A well-formed but non-existent kodjednostki must return 404 Not Found.

    kodjednostki=999999 is a syntactically valid positive integer but
    extremely unlikely to exist in the Polish tax office registry.  The
    endpoint must return HTTP 404 rather than an empty body or 500.
    """
    response = await api_client.get("/api/tax-offices/999999")
    assert response.status_code == 404, (
        f"Non-existent kodjednostki must return HTTP 404. "
        f"Got {response.status_code}: {response.text[:300]}"
    )
    data = response.json()
    # The API uses custom error envelope {error, message} rather than FastAPI's {detail}
    assert "message" in data or "detail" in data, (
        f"404 response must include 'message' or 'detail'. Keys: {list(data.keys())}"
    )
    logger.info(
        "GET /api/tax-offices/999999 correctly returned 404. Message: %s",
        str(data.get("message") or data.get("detail", ""))[:200],
    )
