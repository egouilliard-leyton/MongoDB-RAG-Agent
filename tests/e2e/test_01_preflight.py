"""
Pre-flight checks: verify backend health, vector index, workflow seeded,
and at least one document in the knowledge base.
"""

import asyncio
import logging

import httpx
import pytest
import pytest_asyncio

from tests.e2e.conftest import assert_status

logger = logging.getLogger(__name__)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_backend_health(api_client: httpx.AsyncClient) -> None:
    """Backend must be running and healthy before any E2E test can proceed."""
    try:
        response = await api_client.get("/api/system/health")
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        pytest.skip(
            f"Backend not running at {api_client.base_url} — "
            "start with: uv run uvicorn src.api.main:app --reload\n"
            f"Error: {exc}"
        )
    assert response.status_code == 200, (
        f"Expected HTTP 200 from /api/system/health, got {response.status_code}: "
        f"{response.text[:300]}"
    )
    data = response.json()
    assert data.get("status") == "healthy", (
        f"Backend health status is not 'healthy': {data}"
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_vector_index_active(api_client: httpx.AsyncClient) -> None:
    """Check vector index status (soft check — does not fail the suite)."""
    response = await api_client.get("/api/system/index-status")
    assert response.status_code == 200, (
        f"Expected HTTP 200 from /api/system/index-status, got {response.status_code}: "
        f"{response.text[:300]}"
    )
    data = response.json()
    logger.info("Vector index status: %s", data)
    # Soft assertion: log whatever is returned but do not block the suite
    print(f"Vector index details: {data}")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_default_workflow_seeded(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """Verify at least one default workflow template exists with >= 4 stages."""
    response = await api_client.get("/api/workflows")
    await assert_status(response, 200, "GET /api/workflows")
    workflows = response.json()
    assert isinstance(workflows, list), (
        f"Expected list from /api/workflows, got: {type(workflows)}"
    )
    default_workflow = next(
        (w for w in workflows if w.get("is_default") is True), None
    )
    assert default_workflow is not None, (
        "No default workflow found — run seed: POST /api/workflows/seed-default"
    )
    # Retrieve full workflow to check stages
    wf_id = default_workflow.get("id") or default_workflow.get("_id")
    detail_resp = await api_client.get(f"/api/workflows/{wf_id}")
    await assert_status(detail_resp, 200, f"GET /api/workflows/{wf_id}")
    wf_detail = detail_resp.json()
    stages = wf_detail.get("stages", [])
    assert len(stages) >= 4, (
        f"Default workflow must have at least 4 stages, found {len(stages)}: {stages}"
    )
    e2e_state["default_workflow"] = wf_detail
    logger.info(
        "Default workflow '%s' has %d stages", wf_detail.get("name"), len(stages)
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_documents_exist_or_upload(
    api_client: httpx.AsyncClient,
) -> None:
    """Ensure at least one document exists in the knowledge base; upload one if needed."""
    # Check document count
    docs_resp = await api_client.get("/api/documents")
    await assert_status(docs_resp, 200, "GET /api/documents")
    docs_data = docs_resp.json()

    # Handle both list and paginated response shapes
    if isinstance(docs_data, list):
        doc_count = len(docs_data)
    elif isinstance(docs_data, dict):
        doc_count = docs_data.get("total", len(docs_data.get("items", [])))
    else:
        doc_count = 0

    if doc_count == 0:
        logger.info("No documents found — uploading a test document")
        test_content = b"""# R&D and IP Box Tax Relief in Poland

## IP Box Regime
The IP Box regime allows qualifying companies to apply a preferential 5% CIT rate
on income derived from qualified intellectual property rights, including patents,
utility models, and software copyrights under the Polish CIT Act Article 24d.

## R&D Relief Conditions
To qualify for R&D relief, expenditures must relate to research and development
activities: systematic, creative work aimed at increasing knowledge or creating
new applications. Software development activities may qualify when they involve
innovative problem-solving beyond routine work.

## Documentation Requirements
Companies must maintain separate accounting records for qualified IP income,
track all R&D expenditure categories (employee costs, external services, materials),
and apply the Nexus formula to calculate the qualifying fraction of IP income.

## Nexus Formula
Qualified IP income = actual IP income x (a+b)x1.3 / (a+b+c+d)
Where a=own R&D costs, b=contract R&D from unrelated parties,
c=acquisition from related parties, d=IP acquisition cost.
"""
        files = {
            "file": ("test_tax_relief.md", test_content, "text/markdown")
        }
        upload_response = await api_client.post(
            "/api/documents/upload", files=files
        )
        assert upload_response.status_code in (200, 201), (
            f"Test document upload failed: {upload_response.status_code} "
            f"{upload_response.text[:300]}"
        )
        upload_data = upload_response.json()
        job_id = upload_data.get("job_id")

        if job_id:
            # Poll for ingestion completion (up to 30 seconds)
            for _ in range(15):
                await asyncio.sleep(2)
                status_resp = await api_client.get(f"/api/documents/jobs/{job_id}")
                if status_resp.status_code == 200:
                    status_data = status_resp.json()
                    if status_data.get("status") in ("completed", "done", "finished"):
                        break
                    if status_data.get("status") == "failed":
                        pytest.fail(f"Document ingestion job failed: {status_data}")

        # Re-check document count
        docs_resp2 = await api_client.get("/api/documents")
        docs_data2 = docs_resp2.json()
        if isinstance(docs_data2, list):
            final_count = len(docs_data2)
        elif isinstance(docs_data2, dict):
            final_count = docs_data2.get("total", len(docs_data2.get("items", [])))
        else:
            final_count = 0

        assert final_count > 0, (
            "After uploading test document, still 0 documents found in the knowledge base"
        )
        logger.info("Test document uploaded successfully; document count: %d", final_count)
    else:
        logger.info("Knowledge base already has %d document(s)", doc_count)
