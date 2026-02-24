# Plan: Full Senior E2E Workflow Testing

## Summary

End-to-end test suite for the complete Senior consultant workflow. Covers project creation
with full metadata → Senior session creation → Q&A processing across all 4 workflow stages
(intake → analysis → review → complete) with 3–5 scenarios per stage including 2 expected-
failure cases each → project-level stage machine progression through the 14-stage Polish tax
appeal process, ending at NSA decision (both successful and negative_final outcomes).

The system has TWO independent stage systems that this test exercises:
1. **Workflow template stages** (intake → analysis → review → complete) — used by Q&A sessions
2. **Project stage machine** (project_stages.py: 14 stages, prep_docs → ... → nsa_decision) —
   tracks the broader legal/administrative process for each client project

Tests run against a live backend (`http://localhost:8000`) using `httpx.AsyncClient` with
pytest session-scoped fixtures that share state (project_id, session_id, qa_pair_ids) across
ordered test files (prefixed 01–08 for deterministic execution order).

## User Story

As a Senior consultant
I want to work through the complete system — from creating a project to reaching an NSA decision
So that every scenario is verified: happy paths, validation failures, edge cases, and final outcomes

## Metadata

| Field | Value |
|-------|-------|
| Type | NEW_CAPABILITY |
| Complexity | HIGH |
| Systems Affected | `tests/e2e/` (all new), `pyproject.toml` (update) |

---

## Architecture Context

### Two Stage Systems (CRITICAL for test writer to understand)

```
SYSTEM 1 — Workflow Template Stages (Q&A session workflow)
──────────────────────────────────────────────────────────
intake ──► analysis ──► review ──► complete
  │           │           │
  │    (match_count=10)   │
  │    (prompt append)    │
  │                       └──► (back to analysis if needed)
  └── Sessions are created here, questions are asked per stage

SYSTEM 2 — Project Stage Machine (src/services/project_stages.py)
──────────────────────────────────────────────────────────────────
prep_docs
  │ next
submit_first_instance
  │ next
await_response
  │ next
inquiry_check ──(yes)──► prepare_answers ──(next)──► await_response (loop)
  │ no
first_instance_outcome ──(positive)──► end_refund [TERMINAL]
  │ negative
appeal_second_instance ──(no)──► end_no_appeal [TERMINAL]
  │ yes
second_instance_decision ──(successful)──► return_reconsideration ──(next)──► submit_first_instance
  │ negative
complaint_wsa ──(no)──► end_no_appeal [TERMINAL]
  │ yes
wsa_decision ──(successful)──► return_reconsideration
  │ negative
complaint_nsa ──(no)──► end_no_appeal [TERMINAL]
  │ yes
nsa_decision ──(negative_final)──► end_no_appeal [TERMINAL]
            └──(successful)──────► return_reconsideration
```

Fast path to NSA (all "negative" decisions): 10 transitions total.

### Q&A Pair Statuses
- `outcome_status`: `"successful"` | `"partial"` | `"negative"` | `null`
- `rating_good`: `true` (good) | `false` (bad) | `null` (not reviewed)
- `review.verdict`: `"good"` | `"needs_info"` | `"risk"`
- `is_exemplar`: auto-promoted when rating_good=True AND review.verdict="good" AND confidence≥0.8 AND citations≥2

### Senior vs Junior Role
- **Junior**: no Q&A pair storage (save_qa_pair returns None), no review agent
- **Senior**: full flow — Q&A pair saved to MongoDB, review agent runs, rating/exemplar supported
- All E2E tests use `user_role="senior"`

---

## Patterns to Follow

### Async Fixture Pattern
```python
# SOURCE: tests/test_workflow_service.py:1-35
import pytest
from unittest.mock import AsyncMock

@pytest.fixture
def mock_settings():
    settings = AsyncMock()
    settings.mongodb_uri = "mongodb://localhost:27017"
    settings.mongodb_database = "test_rag_db"
    return settings

@pytest.mark.asyncio
@pytest.mark.unit
async def test_seed_default_creates_template(mock_settings):
    service = WorkflowService(mock_settings)
    await service.initialize()
    try:
        result = await service.seed_default()
        assert result["name"] == "Polish Tax Interpretations"
    finally:
        await service.cleanup()
```

### E2E HTTP Assertion Pattern (adapt for httpx)
```python
# Pattern: always include response body in assertion messages
async def assert_status(response, expected: int, context: str = "") -> None:
    assert response.status_code == expected, (
        f"{context} — Expected {expected}, got {response.status_code}: {response.text}"
    )
```

### Session-Scoped State Sharing Pattern
```python
# conftest.py — e2e_state dict shared across all test files
@pytest_asyncio.fixture(scope="session")
async def api_client():
    async with httpx.AsyncClient(
        base_url=os.getenv("E2E_BASE_URL", "http://localhost:8000"),
        timeout=httpx.Timeout(60.0),
        follow_redirects=True,
    ) as client:
        yield client

@pytest.fixture(scope="session")
def e2e_state() -> dict:
    """Mutable dict shared across all session-scoped tests."""
    return {}
```

---

## Files to Change

| File | Action | Purpose |
|------|--------|---------|
| `tests/e2e/__init__.py` | CREATE | Python package marker |
| `tests/e2e/conftest.py` | CREATE | Session-scoped fixtures: api_client, e2e_state, assert_status helper |
| `tests/e2e/test_01_preflight.py` | CREATE | Health, index, workflow seeded, document upload if none |
| `tests/e2e/test_02_project_creation.py` | CREATE | Project CRUD: 3 happy + 2 fail scenarios |
| `tests/e2e/test_03_session_creation.py` | CREATE | Senior session: 3 happy + 2 fail scenarios |
| `tests/e2e/test_04_intake_stage.py` | CREATE | Intake Q&A: 3 happy + 2 fail + advance to analysis |
| `tests/e2e/test_05_analysis_stage.py` | CREATE | Analysis Q&A: 3 happy + 2 fail + advance to review |
| `tests/e2e/test_06_review_stage.py` | CREATE | Review/rating/exemplar: 6 happy + 2 fail + advance to complete |
| `tests/e2e/test_07_complete_stage.py` | CREATE | Completion/export/follow-up: 3 happy + 2 fail |
| `tests/e2e/test_08_project_stages_nsa.py` | CREATE | Project stage machine: full fast path to NSA + both outcomes + 2 fail |
| `pyproject.toml` | UPDATE | Add `e2e` marker, asyncio-mode=auto, `tests/e2e` testpath, verify httpx dep |

---

## Tasks

### Task 1: Create package and conftest

- **Files**: `tests/e2e/__init__.py`, `tests/e2e/conftest.py`
- **Action**: CREATE
- **Implement**:

  **`tests/e2e/__init__.py`**: Empty file.

  **`tests/e2e/conftest.py`**:
  ```python
  import os
  import httpx
  import pytest
  import pytest_asyncio

  E2E_BASE_URL = os.getenv("E2E_BASE_URL", "http://localhost:8000")

  @pytest_asyncio.fixture(scope="session")
  async def api_client():
      async with httpx.AsyncClient(
          base_url=E2E_BASE_URL,
          timeout=httpx.Timeout(60.0),
          follow_redirects=True,
      ) as client:
          yield client

  @pytest.fixture(scope="session")
  def e2e_state() -> dict:
      """Shared mutable state across all e2e test files.
      Keys populated as tests run:
        project_id, session_id, qa_pair_ids (list), follow_up_session_id,
        nsa_project_id, nsa_success_project_id, positive_first_project_id
      """
      return {"qa_pair_ids": []}

  async def assert_status(response: httpx.Response, expected: int, context: str = "") -> None:
      assert response.status_code == expected, (
          f"{context} — Expected HTTP {expected}, got {response.status_code}.\n"
          f"Response body: {response.text[:500]}"
      )
  ```

- **Validate**: `uv run pytest tests/e2e/ --collect-only -q`

---

### Task 2: Pre-flight checks

- **File**: `tests/e2e/test_01_preflight.py`
- **Action**: CREATE
- **Implement**:

  Mark all tests `@pytest.mark.e2e` and `@pytest.mark.asyncio`.

  - **`test_backend_health`**: `GET /api/system/health` → assert 200, response JSON has `"status": "healthy"`. If fails: `pytest.skip("Backend not running at http://localhost:8000 — start with: uv run uvicorn src.api.main:app --reload")`

  - **`test_vector_index_active`**: `GET /api/system/index-status` → assert 200. Log index details even if not fully ready (soft check — don't skip test suite over this).

  - **`test_default_workflow_seeded`**: `GET /api/workflows` → assert 200. Find item with `is_default=True`. Assert it exists and has stages list with length ≥ 4. Store `e2e_state["default_workflow"] = matching_item`.

  - **`test_documents_exist_or_upload`**:
    1. `GET /api/documents` → assert 200, capture `total` or list length.
    2. If 0 documents: create a minimal test Markdown document and upload it.
       ```python
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
       Qualified IP income = actual IP income × (a+b)×1.3 / (a+b+c+d)
       Where a=own R&D costs, b=contract R&D from unrelated parties,
       c=acquisition from related parties, d=IP acquisition cost.
       """
       files = {"file": ("test_tax_relief.md", test_content, "text/markdown")}
       upload_response = await api_client.post("/api/documents/upload", files=files)
       assert upload_response.status_code in (200, 201), f"Upload failed: {upload_response.text}"
       ```
    3. Poll for ingestion completion (up to 30 seconds, check every 2s) if a job_id was returned.
    4. Assert final document count > 0.

- **Validate**: `uv run pytest tests/e2e/test_01_preflight.py -v --asyncio-mode=auto`

---

### Task 3: Project creation scenarios

- **File**: `tests/e2e/test_02_project_creation.py`
- **Action**: CREATE
- **Implement**:

  All tests: `@pytest.mark.e2e`, `@pytest.mark.asyncio`.

  Tests depend on `api_client` and `e2e_state` fixtures. They MUST run in order (alphabetical by function name or use `@pytest.mark.order` if pytest-ordering is available — default alphabetical is fine).

  - **`test_a_create_full_project`** (runs first — 'a' prefix):
    ```python
    payload = {
        "name": "E2E Senior Test Project — IP Box Analysis",
        "tax_office_id": 1,          # First tax office in DB
        "region": "Mazowieckie",
        "industry": "it",
    }
    response = await api_client.post("/api/projects", json=payload)
    await assert_status(response, 201, "create full project")
    data = response.json()
    assert "id" in data or "_id" in data
    assert data["name"] == payload["name"]
    project_id = data.get("id") or data.get("_id")
    e2e_state["project_id"] = project_id
    ```

  - **`test_b_create_minimal_project`**:
    `POST /api/projects` with only `{"name": "Minimal E2E Project"}` → 201. Do NOT store this id (we use the full project).

  - **`test_c_get_created_project`**:
    `GET /api/projects/{e2e_state["project_id"]}` → 200; verify `name == "E2E Senior Test Project — IP Box Analysis"`; verify `stage` field exists with a `key` sub-field.

  - **`test_d_list_projects_contains_new`**:
    `GET /api/projects` → 200; verify response list contains the project id.

  - **`test_fail1_create_project_missing_name`**:
    `POST /api/projects` with `{}` → 422; verify `detail` field in response.

  - **`test_fail2_create_project_name_empty_string`**:
    `POST /api/projects` with `{"name": ""}` → 422; verify validation error mentions `name`.

- **Validate**: `uv run pytest tests/e2e/test_02_project_creation.py -v --asyncio-mode=auto`

---

### Task 4: Senior session creation scenarios

- **File**: `tests/e2e/test_03_session_creation.py`
- **Action**: CREATE
- **Implement**:

  All tests: `@pytest.mark.e2e`, `@pytest.mark.asyncio`.

  - **`test_a_create_senior_session_full`**:
    ```python
    payload = {
        "name": "E2E Senior Session — Round 1",
        "user_role": "senior",
        "project_id": e2e_state["project_id"],
        "company_info": "Leyton Poland Sp. z o.o., R&D and IP Box tax consultancy",
        "region": "Mazowieckie",
    }
    response = await api_client.post("/api/sessions", json=payload)
    await assert_status(response, 201, "create full senior session")
    data = response.json()
    assert data["user_role"] == "senior"
    assert data["status"] == "active"
    session_id = data.get("id") or data.get("_id")
    e2e_state["session_id"] = session_id
    ```

  - **`test_b_create_senior_session_minimal`**:
    `POST /api/sessions` with `{"name": "Minimal Senior", "user_role": "senior"}` → 201; verify `user_role == "senior"`.

  - **`test_c_get_created_session`**:
    `GET /api/sessions/{e2e_state["session_id"]}` → 200; verify `user_role == "senior"`, `status == "active"`.

  - **`test_d_list_sessions_includes_new`**:
    `GET /api/sessions` → 200; verify session_id appears in list.

  - **`test_fail1_create_session_invalid_role`**:
    `POST /api/sessions` with `{"name": "Bad Role", "user_role": "manager"}` → 422.

  - **`test_fail2_create_session_missing_user_role`**:
    `POST /api/sessions` with `{"name": "No Role"}` → 422.

- **Validate**: `uv run pytest tests/e2e/test_03_session_creation.py -v --asyncio-mode=auto`

---

### Task 5: Intake stage Q&A scenarios

- **File**: `tests/e2e/test_04_intake_stage.py`
- **Action**: CREATE
- **Read before writing**: `src/api/routes/projects.py` — understand exact request body and response format for `PUT /api/projects/{project_id}/stage`
- **Implement**:

  All tests: `@pytest.mark.e2e`, `@pytest.mark.asyncio`.

  - **`test_a_verify_intake_stage`**:
    ```python
    # Verify project is in the first workflow stage
    wf_response = await api_client.get("/api/workflows")
    workflows = wf_response.json()
    default_wf = next(w for w in workflows if w.get("is_default"))
    # Get full workflow to see stages
    wf_detail = await api_client.get(f"/api/workflows/{default_wf['id']}")
    first_stage = wf_detail.json()["stages"][0]
    e2e_state["stage_intake_id"] = first_stage["id"]    # "intake"
    e2e_state["stage_analysis_id"] = wf_detail.json()["stages"][1]["id"]
    e2e_state["stage_review_id"] = wf_detail.json()["stages"][2]["id"]
    e2e_state["stage_complete_id"] = wf_detail.json()["stages"][3]["id"]
    # NOTE: project stage (project_stages.py) may differ from workflow stage
    # The project.stage.key reflects the project-level stage machine
    # This test simply records workflow stage IDs for later use
    ```

  - **`test_b_single_question_ip_box`**:
    ```python
    payload = {
        "questions": ["What are the conditions for applying the IP Box preferential 5% CIT rate in Poland?"],
        "user_role": "senior",
        "include_history": True,
    }
    response = await api_client.post(
        f"/api/sessions/{e2e_state['session_id']}/questions", json=payload
    )
    await assert_status(response, 200, "single question IP Box")
    data = response.json()
    assert data["questions_processed"] == 1
    qa_pairs = data["qa_pairs"]
    assert len(qa_pairs) == 1
    qa = qa_pairs[0]
    assert qa["final_answer"], "final_answer must not be empty"
    # Senior users: qa_pair_id should be populated
    qa_id = qa.get("_id") or qa.get("qa_pair_id")
    assert qa_id, "Senior session must save qa_pair with an ID"
    e2e_state["qa_pair_ids"].append(qa_id)
    ```

  - **`test_c_batch_three_questions`**:
    ```python
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
        f"/api/sessions/{e2e_state['session_id']}/questions", json=payload
    )
    await assert_status(response, 200, "batch 3 questions")
    data = response.json()
    assert data["questions_processed"] == 3
    for qa in data["qa_pairs"]:
        assert qa["final_answer"]
        qa_id = qa.get("_id") or qa.get("qa_pair_id")
        if qa_id:
            e2e_state["qa_pair_ids"].append(qa_id)
    ```

  - **`test_d_verify_qa_pairs_saved_for_senior`**:
    `GET /api/sessions/{session_id}/qa-pairs` → 200; verify list length ≥ 4 (all 4 questions from previous tests); each item has `_id`, `question`, `final_answer`.

  - **`test_fail1_empty_questions_list`**:
    `POST /api/sessions/{session_id}/questions` with `{"questions": [], "user_role": "senior"}` → 422.

  - **`test_fail2_question_over_10000_chars`**:
    `POST /api/sessions/{session_id}/questions` with `{"questions": ["x" * 10001], "user_role": "senior"}` → 422.

  - **`test_z_advance_intake_to_analysis`** ('z' prefix to run last):
    ```python
    # Read stage-options to find the transition event to analysis
    options_resp = await api_client.get(f"/api/projects/{e2e_state['project_id']}/stage-options")
    # NOTE: stage-options may return workflow template transitions OR project_stages transitions
    # Read src/api/routes/projects.py to confirm endpoint behavior before implementing
    options = options_resp.json()
    # Find transition to next stage (likely event "next" or label "Start Analysis")
    # Use that event to advance
    # Exact request body format: read src/api/routes/projects.py
    # Expected: PUT /api/projects/{id}/stage with body like {"event": "next"} or {"stage_id": "..."}
    advance_resp = await api_client.put(
        f"/api/projects/{e2e_state['project_id']}/stage",
        json={"event": "next"}   # VERIFY this format from projects.py route
    )
    assert advance_resp.status_code in (200, 201), f"Advance failed: {advance_resp.text}"
    ```

- **Validate**: `uv run pytest tests/e2e/test_04_intake_stage.py -v --asyncio-mode=auto`

---

### Task 6: Analysis stage Q&A scenarios

- **File**: `tests/e2e/test_05_analysis_stage.py`
- **Action**: CREATE
- **Implement**:

  All tests: `@pytest.mark.e2e`, `@pytest.mark.asyncio`.

  - **`test_a_verify_analysis_stage`**:
    `GET /api/projects/{project_id}` → 200; verify project has advanced to analysis stage (check `stage.key` or current stage label).

  - **`test_b_legal_analysis_question_with_nexus`**:
    ```python
    payload = {
        "questions": [
            "How should qualified IP income be calculated under the Nexus formula "
            "when a company has both own R&D costs and costs from related party acquisitions?"
        ],
        "user_role": "senior",
        "include_history": True,
    }
    response = await api_client.post(
        f"/api/sessions/{e2e_state['session_id']}/questions", json=payload
    )
    await assert_status(response, 200, "legal analysis Nexus question")
    data = response.json()
    qa = data["qa_pairs"][0]
    assert qa["final_answer"]
    # Analysis stage uses match_count=10 per workflow config — expect citations
    assert len(qa.get("citations", [])) >= 1, "Analysis stage should return citations"
    qa_id = qa.get("_id") or qa.get("qa_pair_id")
    if qa_id:
        e2e_state["qa_pair_ids"].append(qa_id)
    # Store one qa_pair_id for review stage tests
    e2e_state["review_qa_pair_id"] = qa_id
    ```

  - **`test_c_qa_history_integration`**:
    ```python
    # Submit follow-up using prior session context
    payload = {
        "questions": [
            "Based on the Nexus formula you explained, what is the maximum IP Box benefit "
            "for a company where 80% of expenditure is qualifying own R&D?"
        ],
        "user_role": "senior",
        "include_history": True,   # Should reuse prior Q&A history
    }
    response = await api_client.post(
        f"/api/sessions/{e2e_state['session_id']}/questions", json=payload
    )
    await assert_status(response, 200, "qa history follow-up question")
    data = response.json()
    assert data["questions_processed"] == 1
    assert data["qa_pairs"][0]["final_answer"]
    ```

  - **`test_d_create_follow_up_session`**:
    ```python
    payload = {
        "new_questions": [
            "What are the penalties for incorrectly claiming IP Box relief without proper documentation?"
        ]
    }
    response = await api_client.post(
        f"/api/sessions/{e2e_state['session_id']}/follow-up", json=payload
    )
    await assert_status(response, 201, "create follow-up session")
    data = response.json()
    follow_up_id = data.get("id") or data.get("_id")
    assert follow_up_id
    e2e_state["follow_up_session_id"] = follow_up_id
    # Verify round number incremented
    assert data.get("metadata", {}).get("round_number", 0) >= 2
    ```

  - **`test_fail1_too_many_questions`**:
    `POST /api/sessions/{session_id}/questions` with `{"questions": ["q"] * 101, "user_role": "senior"}` → 422.

  - **`test_fail2_qa_pairs_nonexistent_session`**:
    `GET /api/sessions/000000000000000000000000/qa-pairs` → assert status_code in (404, 200). If 200, assert empty list `[]`. Either behavior is acceptable — document which the system returns.

  - **`test_z_advance_analysis_to_review`** ('z' runs last):
    Use stage-options, find transition to review, advance project. Verify new stage is review.

- **Validate**: `uv run pytest tests/e2e/test_05_analysis_stage.py -v --asyncio-mode=auto`

---

### Task 7: Review stage scenarios

- **File**: `tests/e2e/test_06_review_stage.py`
- **Action**: CREATE
- **Implement**:

  All tests: `@pytest.mark.e2e`, `@pytest.mark.asyncio`.
  Use `e2e_state["qa_pair_ids"]` (list) and `e2e_state["review_qa_pair_id"]` from earlier.

  - **`test_a_verify_review_stage`**:
    `GET /api/projects/{project_id}` → 200; verify review stage active.

  - **`test_b_rate_qa_pair_good`**:
    ```python
    qa_id = e2e_state["review_qa_pair_id"]
    response = await api_client.put(
        f"/api/qa-pairs/{qa_id}/rating", json={"rating_good": True}
    )
    await assert_status(response, 200, "rate qa pair good")
    data = response.json()
    # Check if exemplar promotion happened (depends on LLM quality)
    promoted = data.get("promoted_to_exemplar", False)
    e2e_state["was_promoted_to_exemplar"] = promoted
    ```

  - **`test_c_edit_answer`**:
    ```python
    qa_id = e2e_state["qa_pair_ids"][0]  # First qa_pair from intake
    edited = (
        "Updated analysis: The IP Box regime in Poland (Article 24d CIT Act) allows "
        "a preferential 5% CIT rate on qualified IP income. Eligible IP includes patents, "
        "utility models, and software copyrights developed through own R&D activities."
    )
    response = await api_client.put(
        f"/api/qa-pairs/{qa_id}", json={"edited_answer": edited}
    )
    await assert_status(response, 200, "edit qa pair answer")
    # Verify edit was persisted
    pairs_resp = await api_client.get(f"/api/sessions/{e2e_state['session_id']}/qa-pairs")
    pairs = pairs_resp.json()
    edited_pair = next((p for p in pairs if (p.get("_id") or p.get("id")) == qa_id), None)
    assert edited_pair is not None, "edited qa pair not found"
    assert edited_pair.get("was_edited") is True
    assert edited_pair.get("final_answer") == edited
    ```

  - **`test_d_exemplar_check_after_good_rating`**:
    ```python
    # Re-read the rated qa_pair to verify is_exemplar field
    pairs_resp = await api_client.get(f"/api/sessions/{e2e_state['session_id']}/qa-pairs")
    pairs = pairs_resp.json()
    qa_id = e2e_state["review_qa_pair_id"]
    rated_pair = next((p for p in pairs if (p.get("_id") or p.get("id")) == qa_id), None)
    assert rated_pair is not None
    assert rated_pair.get("rating_good") is True
    # Exemplar promotion requires: good rating + good verdict + confidence>=0.8 + citations>=2
    # This may or may not trigger depending on LLM output — soft assertion
    is_exemplar = rated_pair.get("is_exemplar", False)
    print(f"Exemplar promotion triggered: {is_exemplar}")
    # If promoted, promoted_to_exemplar_at should be set
    if is_exemplar:
        assert rated_pair.get("promoted_to_exemplar_at") is not None
    ```

  - **`test_e_mark_outcome_successful`**:
    ```python
    qa_id = e2e_state["qa_pair_ids"][0]
    response = await api_client.put(
        f"/api/qa-pairs/{qa_id}/outcome", json={"outcome_status": "successful"}
    )
    await assert_status(response, 200, "mark outcome successful")
    ```

  - **`test_f_mark_outcome_partial`**:
    Use second qa_pair_id: `PUT /api/qa-pairs/{id}/outcome` with `{"outcome_status": "partial"}` → 200.

  - **`test_g_mark_outcome_negative`**:
    Use third qa_pair_id: `PUT /api/qa-pairs/{id}/outcome` with `{"outcome_status": "negative"}` → 200.

  - **`test_fail1_rate_nonexistent_qa_pair`**:
    `PUT /api/qa-pairs/000000000000000000000000/rating` with `{"rating_good": true}` → 404.

  - **`test_fail2_mark_invalid_outcome_status`**:
    `PUT /api/qa-pairs/{valid_id}/outcome` with `{"outcome_status": "approved"}` → 422.

  - **`test_z_advance_review_to_complete`** ('z' runs last):
    Use stage-options, find transition to complete stage, advance project. Verify complete.

- **Validate**: `uv run pytest tests/e2e/test_06_review_stage.py -v --asyncio-mode=auto`

---

### Task 8: Complete stage scenarios

- **File**: `tests/e2e/test_07_complete_stage.py`
- **Action**: CREATE
- **Read before writing**: `src/api/routes/export.py` — understand export endpoint request format and response shape.
- **Implement**:

  All tests: `@pytest.mark.e2e`, `@pytest.mark.asyncio`.

  - **`test_a_verify_complete_stage`**:
    `GET /api/projects/{project_id}` → verify complete stage is active.

  - **`test_b_stage_options_empty_or_terminal`**:
    `GET /api/projects/{project_id}/stage-options` → verify no outgoing workflow transitions from complete stage.

  - **`test_c_mark_session_outcome_successful`**:
    ```python
    response = await api_client.put(
        f"/api/sessions/{e2e_state['session_id']}/outcome",
        json={"outcome": "successful", "determined_by": "user"}
    )
    await assert_status(response, 200, "mark session outcome successful")
    # Verify via GET
    session_resp = await api_client.get(f"/api/sessions/{e2e_state['session_id']}")
    session = session_resp.json()
    assert session.get("outcome_status") == "successful"
    ```

  - **`test_d_export_session_markdown`**:
    ```python
    # Read src/api/routes/export.py to confirm exact request format before implementing
    # Likely: POST /api/sessions/{session_id}/export with {"format": "markdown"} or query param
    response = await api_client.post(
        f"/api/sessions/{e2e_state['session_id']}/export",
        json={"format": "markdown"}
    )
    assert response.status_code in (200, 201), f"Export failed: {response.text}"
    # Verify content has Q&A structure
    content = response.text if "text" in response.headers.get("content-type", "") else response.json()
    # Some form of content should be returned
    assert content, "Export must return non-empty content"
    ```

  - **`test_e_follow_up_session_context`**:
    ```python
    follow_up_id = e2e_state.get("follow_up_session_id")
    assert follow_up_id, "follow_up_session_id must be set from analysis stage test"
    response = await api_client.get(f"/api/sessions/{follow_up_id}")
    await assert_status(response, 200, "get follow-up session")
    data = response.json()
    meta = data.get("metadata", {})
    assert meta.get("parent_session_id") == e2e_state["session_id"], "Follow-up must link to parent"
    assert meta.get("round_number", 0) >= 2, "Round number must be incremented"
    ```

  - **`test_fail1_try_advancing_past_complete`**:
    ```python
    # Attempt to fire an event from complete stage — should fail
    response = await api_client.put(
        f"/api/projects/{e2e_state['project_id']}/stage",
        json={"event": "next"}
    )
    # Complete stage has no outgoing transitions — should be 400 or 422
    assert response.status_code in (400, 422), (
        f"Should not be able to advance past complete stage, got {response.status_code}"
    )
    ```

  - **`test_fail2_export_invalid_format`**:
    ```python
    response = await api_client.post(
        f"/api/sessions/{e2e_state['session_id']}/export",
        json={"format": "xml"}
    )
    assert response.status_code in (400, 422), (
        f"Invalid export format should be rejected, got {response.status_code}"
    )
    ```

- **Validate**: `uv run pytest tests/e2e/test_07_complete_stage.py -v --asyncio-mode=auto`

---

### Task 9: Project stage machine → NSA decision

- **File**: `tests/e2e/test_08_project_stages_nsa.py`
- **Action**: CREATE
- **Read before writing**:
  - `src/services/project_stages.py` — full 14-stage machine and all transitions
  - `src/api/routes/projects.py` — `PUT .../stage` endpoint request format

- **Implement**:

  All tests: `@pytest.mark.e2e`, `@pytest.mark.asyncio`.

  **Important**: These tests use SEPARATE projects from the session workflow project.
  Create 3 dedicated projects for stage machine testing:
  - `nsa_project_id` → fast path to `nsa_decision`, then `negative_final` → `end_no_appeal`
  - `nsa_success_project_id` → same fast path to `nsa_decision`, then `successful` → `return_reconsideration`
  - `positive_first_project_id` → `first_instance_outcome` + `positive` → `end_refund`

  **Fast path to `nsa_decision`** (10 transitions, all "negative" choices):
  ```
  prep_docs      →(next)→      submit_first_instance
  submit_first  →(next)→      await_response
  await_response →(next)→     inquiry_check
  inquiry_check  →(no)→       first_instance_outcome
  first_instance →(negative)→ appeal_second_instance
  appeal_second  →(yes)→      second_instance_decision
  second_instance→(negative)→ complaint_wsa
  complaint_wsa  →(yes)→      wsa_decision
  wsa_decision   →(negative)→ complaint_nsa
  complaint_nsa  →(yes)→      nsa_decision    ← NSA REACHED
  ```

  **Helper function** (define at module level for reuse):
  ```python
  async def advance_stage(client: httpx.AsyncClient, project_id: str, event: str) -> dict:
      """Advance project stage machine by firing an event."""
      response = await client.put(
          f"/api/projects/{project_id}/stage",
          json={"event": event}   # VERIFY format from projects.py
      )
      assert response.status_code in (200, 201), (
          f"Stage advance event='{event}' failed: {response.status_code} {response.text[:300]}"
      )
      return response.json()

  async def get_current_stage(client: httpx.AsyncClient, project_id: str) -> str:
      """Return the current stage key for a project."""
      resp = await client.get(f"/api/projects/{project_id}")
      data = resp.json()
      return data["stage"]["key"]
  ```

  - **`test_a_create_nsa_test_projects`**:
    Create 3 projects (nsa, nsa_success, positive_first); store IDs in e2e_state.
    Verify initial stage for each (likely `prep_docs` if using project_stages.py machine,
    or first workflow stage — check via `GET /api/projects/{id}/stage-options`).

  - **`test_b_stage_prep_docs_to_submit`**:
    `advance_stage(nsa_project_id, "next")` → verify stage is `submit_first_instance`.

  - **`test_c_stage_submit_to_await`**:
    `advance_stage(nsa_project_id, "next")` → `await_response`.

  - **`test_d_stage_await_to_inquiry`**:
    `advance_stage(nsa_project_id, "next")` → `inquiry_check`.

  - **`test_e_stage_inquiry_no_to_first_instance`**:
    `advance_stage(nsa_project_id, "no")` → `first_instance_outcome`.

  - **`test_f_stage_first_instance_negative`**:
    `advance_stage(nsa_project_id, "negative")` → `appeal_second_instance`.

  - **`test_g_stage_appeal_second_yes`**:
    `advance_stage(nsa_project_id, "yes")` → `second_instance_decision`.

  - **`test_h_stage_second_instance_negative`**:
    `advance_stage(nsa_project_id, "negative")` → `complaint_wsa`.

  - **`test_i_stage_complaint_wsa_yes`**:
    `advance_stage(nsa_project_id, "yes")` → `wsa_decision`.

  - **`test_j_stage_wsa_negative`**:
    `advance_stage(nsa_project_id, "negative")` → `complaint_nsa`.

  - **`test_k_stage_complaint_nsa_yes_reach_nsa`**:
    `advance_stage(nsa_project_id, "yes")` → `nsa_decision`.
    Log milestone: "✓ NSA stage reached!"
    Verify `GET /api/projects/{nsa_project_id}/stage-options` returns events `["negative_final", "successful"]`.

  - **`test_l_nsa_decision_negative_final`** (OUTCOME 1 — NSA rejects):
    ```python
    result = await advance_stage(api_client, e2e_state["nsa_project_id"], "negative_final")
    current = await get_current_stage(api_client, e2e_state["nsa_project_id"])
    assert current == "end_no_appeal", f"Expected end_no_appeal, got {current}"
    # Verify terminal: stage-options should be empty
    options_resp = await api_client.get(
        f"/api/projects/{e2e_state['nsa_project_id']}/stage-options"
    )
    options = options_resp.json()
    assert len(options) == 0, f"Terminal stage should have no transitions: {options}"
    ```

  - **`test_m_nsa_decision_successful`** (OUTCOME 2 — NSA grants, advance nsa_success_project):
    Advance `nsa_success_project_id` through the same 10-step fast path to `nsa_decision`,
    then fire `"successful"` → verify stage is `return_reconsideration`.

  - **`test_n_positive_first_instance`** (OUTCOME 3 — Early win, no appeal needed):
    Advance `positive_first_project_id`: `prep_docs` →(next)→ `submit_first_instance`
    →(next)→ `await_response` →(next)→ `inquiry_check` →(no)→ `first_instance_outcome`
    →(positive)→ `end_refund` (terminal). Verify terminal state.

  - **`test_fail1_invalid_event_from_stage`**:
    From `return_reconsideration` (nsa_success_project), fire invalid event `"jump_to_nsa"` →
    assert 400 or 422 with error message about invalid event.

  - **`test_fail2_advance_terminal_stage`**:
    From `end_no_appeal` (nsa_project), fire any event e.g. `"next"` →
    assert 400 or 422; terminal stages cannot be advanced further.

- **Validate**: `uv run pytest tests/e2e/test_08_project_stages_nsa.py -v --asyncio-mode=auto`

---

### Task 10: Update pyproject.toml

- **File**: `pyproject.toml`
- **Action**: UPDATE
- **Implement**:
  1. Add `"tests/e2e"` to `testpaths` list (alongside `"tests"`)
  2. Add `--asyncio-mode=auto` to `addopts` (if not already present)
  3. Add to `markers` list:
     ```toml
     "e2e: End-to-end integration tests requiring a running backend server",
     ```
  4. Verify `httpx` is in `[project.dependencies]` or `[project.optional-dependencies.test]`.
     If missing, add `"httpx>=0.27.0"` and `"pytest-asyncio>=0.23.0"` to test deps.
  5. Verify `pytest-asyncio` is available (check pyproject.toml dependencies).
- **Validate**: `uv run pytest tests/e2e/ --collect-only -q`

---

## Validation

```bash
# 1. Verify test collection (no server needed)
uv run pytest tests/e2e/ --collect-only -q

# 2. Start backend (required for actual execution)
uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

# 3. Run full e2e suite
uv run pytest tests/e2e/ -v --asyncio-mode=auto -m e2e

# 4. Run individual stage file
uv run pytest tests/e2e/test_04_intake_stage.py -v --asyncio-mode=auto

# 5. Run only NSA tests
uv run pytest tests/e2e/test_08_project_stages_nsa.py -v --asyncio-mode=auto -s

# 6. Confirm existing unit tests still pass
uv run pytest tests/ -m unit --asyncio-mode=auto

# 7. Full run with output on failure
uv run pytest tests/e2e/ -v --asyncio-mode=auto -s --tb=short
```

---

## Agent Team

4 agents (1 feature + 3 standing). Execute via:
```
/build-with-agent-team .agents/plans/senior-e2e-workflow-testing.plan.md 4
```

### Feature Agents

#### Agent: test-writer

- **Owns**: `tests/e2e/` (all `.py` files in this directory)
- **Does NOT touch**: `src/`, `frontend/`, `pyproject.toml`, `tests/` (non-e2e)
- **MUST read before starting**:
  - `src/services/project_stages.py` — full 14-stage machine (all stage keys and transition events)
  - `src/api/routes/projects.py` — `PUT /api/projects/{id}/stage` request body format; `GET .../stage-options` response shape
  - `src/api/routes/sessions.py` — session creation, outcome endpoint
  - `src/api/routes/questions.py` — question processing endpoint and response shape
  - `src/api/routes/qa_pairs.py` — rating, editing, outcome endpoints
  - `src/api/routes/export.py` — export endpoint format and supported formats
  - `src/api/models.py` — `QAPair`, `SessionResponse`, `ProjectResponse` models (field names)
  - `tests/test_workflow_service.py` — test style reference (markers, fixture usage)
- **Responsibilities**:
  - Create `tests/e2e/conftest.py` with session-scoped fixtures
  - Create all 8 test files (`test_01_preflight.py` through `test_08_project_stages_nsa.py`)
  - Each file: `@pytest.mark.e2e` on all test functions, `@pytest.mark.asyncio`
  - Clear assertion messages: `f"Expected {x}, got {response.status_code}: {response.text[:300]}"`
  - Shared state via `e2e_state` dict — always store IDs after creation
  - NSA tests: 3 separate projects per terminal outcome path
  - Import `from tests.e2e.conftest import assert_status` or define locally per file
- **Publishes contract**: All `tests/e2e/*.py` files created with valid Python syntax
- **Consumes contract from**: none
- **Validation**: `uv run pytest tests/e2e/ --collect-only -q` (no import errors, all functions collected)

### Standing Agents

#### Agent: general

- **Owns**: `pyproject.toml`, `tests/e2e/__init__.py`
- **Does NOT touch**: `tests/e2e/*.py` files
- **Responsibilities**:
  - Update `pyproject.toml` per Task 10
  - Create empty `tests/e2e/__init__.py`
  - Verify `httpx` and `pytest-asyncio` are in dependencies
- **Validation**: `uv run pytest tests/e2e/ --collect-only -q`

#### Agent: tester-unit

- **Owns**: No new files
- **Does NOT touch**: Source implementation files
- **Responsibilities**:
  - Run `uv run pytest tests/e2e/ --collect-only` → verify 0 errors, all functions found
  - Run `uv run pytest tests/ -m unit --asyncio-mode=auto` → verify existing tests still pass
  - Report any import errors or missing fixture issues back to test-writer
- **Runs after**: test-writer and general complete
- **Validation**: All tests discoverable, no import errors, unit tests pass

#### Agent: tester-e2e

- **Owns**: No new files — executes the test suite
- **Does NOT touch**: Source implementation or test files
- **Skill**: Uses `/agent-browser` for optional UI validation after API tests pass
- **Responsibilities**:
  - Check backend is running: `curl -s http://localhost:8000/api/system/health`
  - Execute: `uv run pytest tests/e2e/ -v --asyncio-mode=auto -m e2e --tb=short`
  - For each failure: capture full output, identify which test/stage failed, note expected vs actual
  - Optional UI validation with agent-browser:
    ```bash
    agent-browser open http://localhost:5173
    agent-browser snapshot -i
    # Navigate to Projects, verify E2E project appears
    # Navigate to Sessions, verify session exists with qa_pairs
    ```
  - Document final pass/fail summary per stage
- **Runs after**: tester-unit passes
- **Validation**: All e2e tests pass OR failures documented with root cause

### Spawn Order

1. **test-writer** — reads source files, creates all test files. Publishes: complete `tests/e2e/` directory.
2. **general** — can run in parallel with test-writer. Updates `pyproject.toml`, creates `__init__.py`.
3. **tester-unit** — after test-writer AND general complete. Runs collect-only and unit tests.
4. **tester-e2e** — after tester-unit passes. Executes full e2e suite.

### Cross-Cutting Concerns

| Concern | Owner | Detail |
|---------|-------|--------|
| Alphabetical test ordering | test-writer | Files 01–08 run in order; within files use `a_`, `b_`... prefixes or accept pytest default order |
| `e2e_state` thread safety | test-writer | All tests are sequential (single asyncio loop), dict mutations are safe |
| Backend not running | test-writer | `test_01_preflight.test_backend_health` calls `pytest.skip()` if backend unreachable — all dependent tests skip gracefully |
| Stage request body format | test-writer | MUST verify from `src/api/routes/projects.py` before implementing advance_stage helper |
| httpx import | general | Ensure `httpx` is in project dependencies before test-writer code is executed |
| Project stage vs Workflow stage | test-writer | Tests 01–07 use workflow template stage transitions; test 08 uses project_stages.py machine — these are separate systems driven by separate API endpoints |

---

## Acceptance Criteria

- [ ] 10 files created in `tests/e2e/` (`__init__.py` + `conftest.py` + 8 test files)
- [ ] `uv run pytest tests/e2e/ --collect-only` discovers all test functions with 0 errors
- [ ] All test functions marked `@pytest.mark.e2e`
- [ ] Happy path tests pass against running backend (backend + documents required)
- [ ] Fail tests correctly assert 422/404 responses (not 200)
- [ ] NSA test reaches `nsa_decision` stage via 10-step fast path
- [ ] Both NSA outcomes tested: `negative_final` → `end_no_appeal` and `successful` → `return_reconsideration`
- [ ] Terminal stages verified: no outgoing transitions from `end_no_appeal`, `end_refund`
- [ ] `pyproject.toml` updated with `e2e` marker and asyncio config
- [ ] Existing unit tests still pass: `uv run pytest tests/ -m unit`
