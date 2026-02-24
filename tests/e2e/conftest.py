"""
E2E test configuration and session-scoped fixtures.

All tests in tests/e2e/ use httpx.AsyncClient against a running backend.
Start the backend with:
    uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
"""

import os

import httpx
import pytest
import pytest_asyncio

E2E_BASE_URL = os.getenv("E2E_BASE_URL", "http://localhost:8000")


@pytest_asyncio.fixture(scope="function")
async def api_client() -> httpx.AsyncClient:
    """Function-scoped async HTTP client — one fresh client per test to avoid event loop boundary errors."""
    async with httpx.AsyncClient(
        base_url=E2E_BASE_URL,
        timeout=httpx.Timeout(180.0),  # LLM batch calls can take >60s
        follow_redirects=True,
    ) as client:
        yield client


@pytest.fixture(scope="session")
def e2e_state() -> dict:
    """
    Shared mutable state across all e2e test files.

    Keys populated as tests run:
      project_id, session_id, qa_pair_ids (list), follow_up_session_id,
      nsa_project_id, nsa_success_project_id, positive_first_project_id,
      stage_intake_id, stage_analysis_id, stage_review_id, stage_complete_id,
      review_qa_pair_id, was_promoted_to_exemplar, default_workflow
    """
    return {"qa_pair_ids": []}


async def assert_status(
    response: httpx.Response, expected: int, context: str = ""
) -> None:
    """
    Assert an HTTP response has the expected status code.

    Args:
        response: The httpx Response to check.
        expected: Expected HTTP status code.
        context: Optional description of the call site for clearer assertion messages.
    """
    assert response.status_code == expected, (
        f"{context} — Expected HTTP {expected}, got {response.status_code}.\n"
        f"Response body: {response.text[:500]}"
    )
