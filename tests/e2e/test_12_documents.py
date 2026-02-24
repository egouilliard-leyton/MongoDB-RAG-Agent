"""
Document upload and management E2E tests.

Covers the full lifecycle for standalone document management:
  upload (markdown) -> list -> get detail -> search -> pagination ->
  delete -> not-found and validation error cases.

Depends on e2e_state["project_id"] being set by test_02_project_creation.py.
State keys populated here:
  e2e_state["uploaded_document_id"] — document_id from the upload response

The upload API accepts multipart/form-data with an optional project_id query
parameter. Supported formats: PDF, DOCX, PPTX, DOC, XLSX, XLS, HTML, MD, TXT.
"""

import logging

import httpx
import pytest

from tests.e2e.conftest import assert_status

logger = logging.getLogger(__name__)

# Sentinel ObjectId that is guaranteed not to exist in any test database.
_NONEXISTENT_ID = "000000000000000000000000"

# Minimal markdown content used for upload tests (~200 bytes).
_MARKDOWN_CONTENT = (
    b"# E2E Test Document\n\n"
    b"This is a test document created by the MongoDB RAG Agent E2E test suite.\n\n"
    b"## Section 1\n\n"
    b"Content for section 1: IP Box and R&D tax relief eligibility in Poland.\n\n"
    b"## Section 2\n\n"
    b"Content for section 2: qualifying expenditures and the Nexus formula.\n"
)

_MARKDOWN_FILENAME = "test_e2e_document.md"
_MARKDOWN_CONTENT_TYPE = "text/markdown"


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_a_upload_markdown_document(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    POST /api/documents/upload uploads a markdown file and returns 201.

    Requires e2e_state["project_id"] from test_02. Stores the resulting
    document_id in e2e_state["uploaded_document_id"] for all subsequent tests.

    The response includes:
      - document_id (non-empty string)
      - job_id
      - chunks_created (may be 0 for tiny files; that is acceptable)
    """
    project_id = e2e_state.get("project_id")
    assert project_id, (
        "e2e_state['project_id'] must be set by test_02_project_creation — "
        "run the full E2E suite in order"
    )

    files = {
        "file": (_MARKDOWN_FILENAME, _MARKDOWN_CONTENT, _MARKDOWN_CONTENT_TYPE)
    }
    response = await api_client.post(
        "/api/documents/upload",
        params={"project_id": project_id},
        files=files,
    )
    await assert_status(response, 201, "POST /api/documents/upload (markdown)")
    data = response.json()

    document_id = data.get("document_id")
    assert document_id, (
        f"Upload response must include a non-empty 'document_id'. Got: {data}"
    )

    chunks_created = data.get("chunks_created", 0)
    assert isinstance(chunks_created, int) and chunks_created >= 0, (
        f"'chunks_created' must be a non-negative integer. Got: {chunks_created}"
    )

    e2e_state["uploaded_document_id"] = document_id
    logger.info(
        "Uploaded document id=%s; chunks_created=%d; job_id=%s",
        document_id,
        chunks_created,
        data.get("job_id"),
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_b_list_documents_shows_upload(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    GET /api/documents returns a paginated list that includes the uploaded document.

    Verifies the response envelope shape (documents list + total count) and
    confirms the uploaded document id appears among the results.
    """
    project_id = e2e_state.get("project_id")
    assert project_id, (
        "e2e_state['project_id'] must be set by test_02_project_creation"
    )
    uploaded_document_id = e2e_state.get("uploaded_document_id")
    assert uploaded_document_id, (
        "e2e_state['uploaded_document_id'] must be set by test_a_upload_markdown_document"
    )

    response = await api_client.get(
        "/api/documents",
        params={"project_id": project_id, "limit": 50},
    )
    await assert_status(response, 200, "GET /api/documents (scoped to project)")
    data = response.json()

    assert "documents" in data, (
        f"Response must include a 'documents' key. Got keys: {list(data.keys())}"
    )
    assert "total" in data, (
        f"Response must include a 'total' key. Got keys: {list(data.keys())}"
    )
    documents = data["documents"]
    total = data["total"]

    assert isinstance(documents, list), (
        f"'documents' must be a list. Got type: {type(documents)}"
    )
    assert isinstance(total, int) and total >= 1, (
        f"'total' must be >= 1 after uploading a document. Got: {total}"
    )

    # Confirm our upload is present.
    doc_ids = [str(d.get("_id") or d.get("id")) for d in documents]
    assert uploaded_document_id in doc_ids, (
        f"Uploaded document id={uploaded_document_id} not found in document list. "
        f"Found ids: {doc_ids[:10]}"
    )
    logger.info(
        "Document list for project_id=%s has %d entries; upload confirmed present",
        project_id,
        total,
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_c_get_document_details(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    GET /api/documents/{id} returns full document details.

    Verifies the response includes the expected fields: _id/id, title, created_at,
    and the project_id (when provided at upload time).
    """
    uploaded_document_id = e2e_state.get("uploaded_document_id")
    assert uploaded_document_id, (
        "e2e_state['uploaded_document_id'] must be set by test_a_upload_markdown_document"
    )
    project_id = e2e_state.get("project_id")

    response = await api_client.get(f"/api/documents/{uploaded_document_id}")
    await assert_status(response, 200, f"GET /api/documents/{uploaded_document_id}")
    data = response.json()

    returned_id = str(data.get("_id") or data.get("id") or "")
    assert returned_id == uploaded_document_id, (
        f"Returned document id must match requested id. "
        f"Expected '{uploaded_document_id}', got '{returned_id}'"
    )
    assert data.get("title"), (
        f"Document detail must include a non-empty 'title'. Got: {data}"
    )
    assert data.get("created_at"), (
        f"Document detail must include a 'created_at' timestamp. Got: {data}"
    )

    # project_id association: present and matching, or None if the backend
    # did not store it (soft assertion — both are acceptable).
    returned_project_id = data.get("project_id")
    if returned_project_id is not None:
        assert str(returned_project_id) == str(project_id), (
            f"Document project_id mismatch. Expected '{project_id}', "
            f"got '{returned_project_id}'"
        )
        logger.info(
            "Document id=%s is correctly scoped to project_id=%s",
            uploaded_document_id,
            returned_project_id,
        )
    else:
        logger.info(
            "Document id=%s returned project_id=None (no project association stored)",
            uploaded_document_id,
        )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_d_list_documents_with_search(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    GET /api/documents?search=... filters documents by keyword.

    Searches for 'test_e2e' which appears in the uploaded filename.
    The search may or may not match (depends on backend implementation),
    so the assertion is only on response shape, not on result count.
    """
    response = await api_client.get(
        "/api/documents",
        params={"search": "test_e2e", "limit": 20},
    )
    await assert_status(response, 200, "GET /api/documents?search=test_e2e")
    data = response.json()

    assert "documents" in data, (
        f"Search response must include a 'documents' key. Got keys: {list(data.keys())}"
    )
    assert isinstance(data["documents"], list), (
        f"'documents' in search response must be a list. Got: {type(data['documents'])}"
    )

    matched = len(data["documents"])
    logger.info(
        "Search for 'test_e2e' returned %d document(s) (may be 0 — soft check)",
        matched,
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e_list_documents_pagination(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    GET /api/documents with limit=1&skip=0 validates pagination envelope.

    When total >= 2: has_more must be True and exactly 1 document is returned.
    When total == 1: has_more must be False.
    """
    project_id = e2e_state.get("project_id")
    assert project_id, (
        "e2e_state['project_id'] must be set by test_02_project_creation"
    )

    response = await api_client.get(
        "/api/documents",
        params={"project_id": project_id, "limit": 1, "skip": 0},
    )
    await assert_status(response, 200, "GET /api/documents?limit=1&skip=0")
    data = response.json()

    assert "documents" in data and "total" in data and "has_more" in data, (
        f"Paginated response must include 'documents', 'total', and 'has_more'. "
        f"Got keys: {list(data.keys())}"
    )

    documents = data["documents"]
    total = data["total"]
    has_more = data["has_more"]

    assert len(documents) <= 1, (
        f"With limit=1, at most 1 document must be returned. Got {len(documents)}"
    )

    if total >= 2:
        assert has_more is True, (
            f"has_more must be True when total={total} and limit=1. Got has_more={has_more}"
        )
        assert len(documents) == 1, (
            f"With limit=1 and total={total}, exactly 1 document expected. Got {len(documents)}"
        )
        logger.info(
            "Pagination: total=%d, limit=1, has_more=True — verified", total
        )
    else:
        assert has_more is False, (
            f"has_more must be False when total={total} and limit=1. Got has_more={has_more}"
        )
        logger.info(
            "Pagination: total=%d, limit=1, has_more=False — verified (single-doc project)",
            total,
        )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_f_delete_document(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    DELETE /api/documents/{id} removes the document and returns 204.

    Follows up with a GET to confirm the record is truly gone (404).
    This test intentionally runs last among the happy-path tests to keep
    the document available for tests c, d, and e.
    """
    uploaded_document_id = e2e_state.get("uploaded_document_id")
    assert uploaded_document_id, (
        "e2e_state['uploaded_document_id'] must be set by test_a_upload_markdown_document"
    )

    # Delete the uploaded document.
    delete_response = await api_client.delete(
        f"/api/documents/{uploaded_document_id}"
    )
    await assert_status(
        delete_response, 204,
        f"DELETE /api/documents/{uploaded_document_id}"
    )

    # Verify deletion: subsequent GET must return 404.
    get_response = await api_client.get(f"/api/documents/{uploaded_document_id}")
    await assert_status(
        get_response, 404,
        f"GET /api/documents/{uploaded_document_id} after deletion must return 404"
    )
    logger.info(
        "Document id=%s deleted and confirmed absent (404)", uploaded_document_id
    )


# ---------------------------------------------------------------------------
# Error / failure tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_fail1_upload_to_nonexistent_project(
    api_client: httpx.AsyncClient,
) -> None:
    """
    POST /api/documents/upload with a nonexistent project_id must return 404.

    The server must validate that the project exists before accepting the upload
    to prevent orphaned documents.
    """
    files = {
        "file": (_MARKDOWN_FILENAME, _MARKDOWN_CONTENT, _MARKDOWN_CONTENT_TYPE)
    }
    response = await api_client.post(
        "/api/documents/upload",
        params={"project_id": _NONEXISTENT_ID},
        files=files,
    )
    await assert_status(
        response, 404,
        f"Upload with project_id={_NONEXISTENT_ID} must return 404"
    )
    logger.info(
        "Upload to nonexistent project correctly returned 404: %s",
        response.text[:200],
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_fail2_get_nonexistent_document(
    api_client: httpx.AsyncClient,
) -> None:
    """
    GET /api/documents/{id} with a valid-format but nonexistent ObjectId must return 404.

    Verifies the API returns a proper not-found response rather than an
    unhandled server error.
    """
    response = await api_client.get(f"/api/documents/{_NONEXISTENT_ID}")
    await assert_status(
        response, 404,
        f"GET /api/documents/{_NONEXISTENT_ID} must return 404"
    )
    logger.info(
        "GET nonexistent document correctly returned 404: %s",
        response.text[:200],
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_fail3_delete_nonexistent_document(
    api_client: httpx.AsyncClient,
) -> None:
    """
    DELETE /api/documents/{id} with a nonexistent ObjectId must return 404.

    The API must not silently succeed when the target document does not exist.
    """
    response = await api_client.delete(f"/api/documents/{_NONEXISTENT_ID}")
    await assert_status(
        response, 404,
        f"DELETE /api/documents/{_NONEXISTENT_ID} must return 404"
    )
    logger.info(
        "DELETE nonexistent document correctly returned 404: %s",
        response.text[:200],
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_fail4_upload_unsupported_format(
    api_client: httpx.AsyncClient, e2e_state: dict
) -> None:
    """
    POST /api/documents/upload with an unsupported file extension must return 400 or 422.

    The API must reject files with extensions not in the allowed set
    (PDF, DOCX, PPTX, DOC, XLSX, XLS, HTML, MD, TXT) before attempting ingestion.
    Uses a .exe file as a representative unsupported type.
    """
    project_id = e2e_state.get("project_id")
    # project_id is optional here; test the format validation regardless.

    exe_content = b"MZ\x90\x00This is a fake executable - not a real file"
    files = {
        "file": ("malicious.exe", exe_content, "application/octet-stream")
    }

    params = {}
    if project_id:
        params["project_id"] = project_id

    response = await api_client.post(
        "/api/documents/upload",
        params=params,
        files=files,
    )
    assert response.status_code in (400, 422), (
        f"Uploading an .exe file must return 400 or 422 (unsupported file type). "
        f"Got {response.status_code}: {response.text[:300]}"
    )
    logger.info(
        "Unsupported .exe upload correctly rejected with HTTP %d: %s",
        response.status_code,
        response.text[:200],
    )
