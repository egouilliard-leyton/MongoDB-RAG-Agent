# Plan: Multi-Workflow-Type Support in Settings

## Summary

The Settings Workflow Builder currently only shows/configures the single "project" workflow template type (intake → analysis → review → complete). We need to expose all four workflow types — Project, QA Session, QA Pair, and Agentic Pipeline — each with their own default stages, configurable from Settings via sub-tabs inside the existing Workflow Builder tab. The backend adds a `workflow_type` discriminator field to templates and a per-type seeding mechanism; the frontend adds sub-tabs that scope `WorkflowBuilder` to one type at a time.

## User Story

As a settings administrator
I want to see and configure all four workflow types (Project, QA Session, QA Pair, Agentic Pipeline) from Settings
So that I can customize the full system behavior — prompts, search params, metadata fields, and transitions — for every workflow in one place

## Metadata

| Field | Value |
|-------|-------|
| Type | ENHANCEMENT |
| Complexity | MEDIUM |
| Systems Affected | `src/models/`, `src/services/`, `src/api/routes/`, `src/api/main.py`, `frontend/src/api/`, `frontend/src/components/workflow-builder/`, `frontend/src/pages/` |

---

## Patterns to Follow

### Backend Service Pattern
```python
# SOURCE: src/services/workflow_service.py:183-214
async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.utcnow()
    if data.get("is_default"):
        await self.db[self.collection_name].update_many(
            {"is_default": True},
            {"$set": {"is_default": False, "updated_at": now}},
        )
    doc = {
        "name": data["name"],
        "description": data.get("description", ""),
        "is_default": data.get("is_default", False),
        "stages": data.get("stages", []),
        "created_at": now,
        "updated_at": now,
    }
    result = await self.db[self.collection_name].insert_one(doc)
    doc["_id"] = result.inserted_id
    return self._doc_to_api(doc)
```

### Route Handler Pattern
```python
# SOURCE: src/api/routes/workflows.py:23-33
@router.get("", response_model=List[WorkflowListItem])
async def list_workflows():
    settings = load_settings()
    service = WorkflowService(settings)
    await service.initialize()
    try:
        templates = await service.list_templates()
        return [WorkflowListItem(**t) for t in templates]
    finally:
        await service.cleanup()
```

### Static Route Before Parameterized (CRITICAL)
```python
# SOURCE: src/api/routes/workflows.py:52-63
# IMPORTANT: seed-default must be defined BEFORE /{workflow_id} routes
@router.post("/seed-default", response_model=WorkflowResponse)
async def seed_default_workflow():
    ...
@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(workflow_id: str):
    ...
```

### API Client Pattern (Frontend)
```typescript
// SOURCE: frontend/src/api/client.ts:1011-1016
export const listWorkflows = async (): Promise<WorkflowListItem[]> => {
  return retryRequest(async () => {
    const response = await apiClient.get<WorkflowListItem[]>('/api/workflows');
    return response.data;
  });
};
```

### Pydantic Model Pattern
```python
# SOURCE: src/models/workflow_models.py:56-96
class WorkflowCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    is_default: bool = False
    stages: list[WorkflowStage] = Field(default_factory=list)

class WorkflowResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    name: str
    ...
```

### Seed Default Pattern
```python
# SOURCE: src/services/workflow_service.py:375-399
async def seed_default(self) -> Dict[str, Any]:
    existing = await self.db[self.collection_name].find_one({"is_default": True})
    if existing:
        return self._doc_to_api(existing)
    now = datetime.utcnow()
    doc = { "name": ..., "is_default": True, "stages": DEFAULT_STAGES, ... }
    result = await self.db[self.collection_name].insert_one(doc)
    doc["_id"] = result.inserted_id
    return self._doc_to_api(doc)
```

---

## Files to Change

| File | Action | Purpose |
|------|--------|---------|
| `src/models/workflow_models.py` | UPDATE | Add `WorkflowType` literal + `workflow_type` field to 3 models |
| `src/services/workflow_service.py` | UPDATE | Add 3 default stage sets, `list_by_type()`, `seed_default_for_type()`, fix scoped `is_default` enforcement |
| `src/api/routes/workflows.py` | UPDATE | Add `workflow_type` query param to list; add `seed-default-for-type` static route |
| `src/api/main.py` | UPDATE | Seed all 4 types in lifespan |
| `frontend/src/api/types.ts` | UPDATE | Add `WorkflowType` type + `workflow_type` field to 3 interfaces |
| `frontend/src/api/client.ts` | UPDATE | Update `listWorkflows` + add `seedDefaultForType` |
| `frontend/src/components/workflow-builder/WorkflowBuilder.tsx` | UPDATE | Accept `workflowType` prop; scope all API calls + creation to type |
| `frontend/src/pages/SettingsPage.tsx` | UPDATE | Add `WORKFLOW_SUB_TABS` constant, `activeWorkflowType` state, sub-tab strip |

---

## Tasks

### Task 1: Add `WorkflowType` literal and field to backend models

- **File**: `src/models/workflow_models.py`
- **Action**: UPDATE
- **Implement**:
  - Add `WorkflowType = Literal["project", "qa_session", "qa_pair", "agentic"]` after imports
  - Add `workflow_type: WorkflowType = "project"` to `WorkflowCreateRequest` (line ~62, after `is_default`)
  - Add `workflow_type: WorkflowType = "project"` to `WorkflowResponse` (after `is_default`)
  - Add `workflow_type: WorkflowType = "project"` to `WorkflowListItem` (after `is_default`)
  - Default `"project"` ensures backwards compat — existing docs without the field still work
- **Mirror**: `src/models/workflow_models.py:56-96` — follow existing field ordering
- **Validate**: `cd /path && uv run python -c "from src.models.workflow_models import WorkflowResponse, WorkflowType; print('OK')"`

---

### Task 2: Add default stage sets for 3 new workflow types

- **File**: `src/services/workflow_service.py`
- **Action**: UPDATE — add after existing `DEFAULT_STAGES` block (line ~123)
- **Implement**: Add 6 constants (name + description + stages for each type):

  **`DEFAULT_QA_SESSION_TEMPLATE_NAME`** = `"Standard QA Session"`
  **`DEFAULT_QA_SESSION_STAGES`** (4 stages):
  - `open` (#3B82F6, order=0): description="Session started, questions being asked"; no prompt/param overrides; transition → `in_review` label="Submit for Review"
  - `in_review` (#F59E0B, order=1): `system_prompt_append="This session is under senior review. Provide concise, citation-heavy answers."`, `match_count=15`; transitions → `approved` "Approve" + → `open` "Return for Revision"
  - `approved` (#10B981, order=2): no overrides; transition → `exported` "Export"
  - `exported` (#8B5CF6, order=3): no overrides; no transitions (terminal)

  **`DEFAULT_QA_PAIR_TEMPLATE_NAME`** = `"Standard QA Pair Review"`
  **`DEFAULT_QA_PAIR_STAGES`** (5 stages):
  - `draft` (#9CA3AF, order=0): no overrides; transition → `needs_review` "Flag for Review"
  - `needs_review` (#F59E0B, order=1): `system_prompt_append="This answer requires careful review. Highlight any legal risks."`, `match_count=12`; transitions → `approved` "Approve" + → `rejected` "Reject"
  - `approved` (#10B981, order=2): no overrides; transition → `exemplar` "Promote to Exemplar"
  - `rejected` (#EF4444, order=3): `system_prompt_append="Regenerate this answer. The previous version was rejected."`, `match_count=15`; transition → `draft` "Re-generate"
  - `exemplar` (#8B5CF6, order=4): no overrides; no transitions (terminal)

  **`DEFAULT_AGENTIC_TEMPLATE_NAME`** = `"Standard Agentic Pipeline"`
  **`DEFAULT_AGENTIC_STAGES`** (5 stages, all `auto_advance=True` except last):
  - `question_analysis` (#3B82F6, order=0): `system_prompt_append="First, carefully read the question. Identify: (1) the main legal topic, (2) any sub-questions, (3) required context."`, `auto_advance=True`; transition → `retrieval` "Proceed to Retrieval"
  - `retrieval` (#06B6D4, order=1): `match_count=10`, `rrf_k=60`, `qa_history_match_count=3`, `auto_advance=True`; transition → `synthesis` "Synthesize Results"
  - `synthesis` (#8B5CF6, order=2): `system_prompt_append="Using the retrieved documents, compose a precise, citation-backed answer. Structure: (1) direct answer, (2) legal basis, (3) caveats."`, `auto_advance=True`; transition → `refinement` "Refine"
  - `refinement` (#F59E0B, order=3): `system_prompt_append="Review your answer for completeness. If key aspects are missing, note what additional context would help."`, `match_count=5`, `auto_advance=True`; transition → `output` "Finalize"
  - `output` (#10B981, order=4): `system_prompt_append="Format the final answer clearly. Include all citation numbers."`, `auto_advance=False`; no transitions (terminal)

- **Mirror**: `src/services/workflow_service.py:16-123` — follow exact dict structure of `DEFAULT_STAGES`
- **Validate**: `uv run python -c "from src.services.workflow_service import DEFAULT_QA_SESSION_STAGES, DEFAULT_QA_PAIR_STAGES, DEFAULT_AGENTIC_STAGES; print(len(DEFAULT_QA_SESSION_STAGES), len(DEFAULT_QA_PAIR_STAGES), len(DEFAULT_AGENTIC_STAGES))"`

---

### Task 3: Add `list_by_type()` and `seed_default_for_type()` to WorkflowService

- **File**: `src/services/workflow_service.py`
- **Action**: UPDATE — add new methods after `seed_default()` (line ~399)
- **Implement**:

  **`list_by_type(self, workflow_type: str) -> List[Dict[str, Any]]`**:
  ```
  Google docstring: "List workflow templates filtered by workflow_type."
  Args: workflow_type: str
  - If workflow_type == "project": query = {"$or": [{"workflow_type": "project"}, {"workflow_type": {"$exists": False}}]}
    (backwards compat: existing docs without the field are project workflows)
  - Else: query = {"workflow_type": workflow_type}
  - cursor = self.db[self.collection_name].find(query).sort("created_at", -1)
  - Iterate async, call _doc_to_api(), add stage_count, append to list
  - Return list
  ```

  **`seed_default_for_type(self, workflow_type: str) -> Dict[str, Any]`**:
  ```
  Google docstring: "Seed the default workflow template for a specific type. Idempotent."
  Args: workflow_type: str
  Raises: ValueError if workflow_type not in ("project", "qa_session", "qa_pair", "agentic")

  _CONFIG = {
      "project":    (DEFAULT_TEMPLATE_NAME, DEFAULT_TEMPLATE_DESCRIPTION, DEFAULT_STAGES),
      "qa_session": (DEFAULT_QA_SESSION_TEMPLATE_NAME, "Default lifecycle for Q&A sessions", DEFAULT_QA_SESSION_STAGES),
      "qa_pair":    (DEFAULT_QA_PAIR_TEMPLATE_NAME, "Default lifecycle for individual Q&A pair answers", DEFAULT_QA_PAIR_STAGES),
      "agentic":    (DEFAULT_AGENTIC_TEMPLATE_NAME, "Default multi-step AI agent processing pipeline", DEFAULT_AGENTIC_STAGES),
  }
  if workflow_type not in _CONFIG: raise ValueError(f"Unknown workflow_type: {workflow_type}")

  # Idempotency check (same $or backwards compat for "project")
  if workflow_type == "project":
      query = {"is_default": True, "$or": [{"workflow_type": "project"}, {"workflow_type": {"$exists": False}}]}
  else:
      query = {"is_default": True, "workflow_type": workflow_type}
  existing = await self.db[...].find_one(query)
  if existing: return self._doc_to_api(existing)

  name, description, stages = _CONFIG[workflow_type]
  now = datetime.utcnow()
  doc = {"name": name, "description": description, "is_default": True,
         "workflow_type": workflow_type, "stages": stages,
         "created_at": now, "updated_at": now}
  result = await self.db[...].insert_one(doc)
  doc["_id"] = result.inserted_id
  logger.info(f"Seeded default {workflow_type} workflow template: {result.inserted_id}")
  return self._doc_to_api(doc)
  ```

- **Mirror**: `src/services/workflow_service.py:168-181` (list_templates) + `375-399` (seed_default)

---

### Task 4: Fix scoped `is_default` enforcement + persist `workflow_type` in create/update/duplicate

- **File**: `src/services/workflow_service.py`
- **Action**: UPDATE — modify `create()`, `update()`, `duplicate()` methods

  **`create()` (line ~196-213)**:
  - Change `update_many({"is_default": True}, ...)` to `update_many({"is_default": True, "workflow_type": data.get("workflow_type", "project")}, ...)`
  - Add `"workflow_type": data.get("workflow_type", "project")` to the `doc` dict

  **`update()` (line ~276-293)**:
  - Change `update_many({"is_default": True, "_id": {"$ne": oid}}, ...)` to also include `"workflow_type": data.get("workflow_type", existing.get("workflow_type", "project"))`
  - Add `"workflow_type": data.get("workflow_type", existing.get("workflow_type", "project"))` to `update_fields` dict

  **`duplicate()` (line ~356-373)**:
  - Add `"workflow_type": source.get("workflow_type", "project")` to the `doc` dict

- **Mirror**: `src/services/workflow_service.py:196-214` (create pattern)
- **Validate**: Existing tests still pass

---

### Task 5: Update routes — add `workflow_type` query param + `seed-default-for-type` endpoint

- **File**: `src/api/routes/workflows.py`
- **Action**: UPDATE

  **Update `list_workflows` (line 23)**:
  ```python
  from fastapi import APIRouter, Query
  from typing import List, Optional

  @router.get("", response_model=List[WorkflowListItem])
  async def list_workflows(
      workflow_type: Optional[str] = Query(default=None, description="Filter by workflow type")
  ):
      ...
      templates = await service.list_by_type(workflow_type) if workflow_type \
                  else await service.list_templates()
      return [WorkflowListItem(**t) for t in templates]
  ```

  **Add `seed-default-for-type` BEFORE `/{workflow_id}` routes (after line 63)**:
  ```python
  @router.post("/seed-default-for-type", response_model=WorkflowResponse)
  async def seed_default_for_type_route(
      workflow_type: str = Query(..., description="project|qa_session|qa_pair|agentic")
  ):
      """Seed the default workflow template for a given type. Idempotent."""
      settings = load_settings()
      service = WorkflowService(settings)
      await service.initialize()
      try:
          result = await service.seed_default_for_type(workflow_type)
          return WorkflowResponse(**result)
      finally:
          await service.cleanup()
  ```

  Final route order must be: `GET ""` → `POST ""` → `POST /seed-default` → `POST /seed-default-for-type` → `GET /{id}` → `PUT /{id}` → `DELETE /{id}` → `POST /{id}/duplicate`

- **Mirror**: `src/api/routes/workflows.py:52-63` (seed-default pattern)
- **Validate**: `curl http://localhost:8000/api/workflows?workflow_type=qa_session` returns filtered results

---

### Task 6: Update lifespan to seed all 4 workflow types

- **File**: `src/api/main.py`
- **Action**: UPDATE — modify the seed block in `lifespan()` (lines 36-43)
- **Implement**:
  ```python
  try:
      from src.services.workflow_service import WorkflowService
      wf_service = WorkflowService(settings_obj)
      await wf_service.initialize()
      try:
          for wf_type in ("project", "qa_session", "qa_pair", "agentic"):
              await wf_service.seed_default_for_type(wf_type)
          logger.info("All default workflow templates seeded")
      finally:
          await wf_service.cleanup()
  except Exception as e:
      logger.warning(f"Could not seed default workflows: {e}")
  ```
  Replace the existing `await wf_service.seed_default()` call — `seed_default_for_type("project")` handles the same backwards-compatible logic.
- **Mirror**: `src/api/main.py:36-43`

---

### Task 7: Update frontend TypeScript types

- **File**: `frontend/src/api/types.ts`
- **Action**: UPDATE — around line 770, inside the workflow types section
- **Implement**:
  ```typescript
  // Add before WorkflowTemplate interface (line ~771)
  export type WorkflowType = "project" | "qa_session" | "qa_pair" | "agentic";

  // Add workflow_type to WorkflowTemplate (line ~771-779)
  export interface WorkflowTemplate {
    id: string;
    name: string;
    description: string;
    is_default: boolean;
    workflow_type: WorkflowType;   // ADD
    stages: WorkflowStage[];
    created_at: string;
    updated_at: string;
  }

  // Add workflow_type to WorkflowListItem (line ~781-789)
  export interface WorkflowListItem {
    id: string;
    name: string;
    description: string;
    is_default: boolean;
    workflow_type: WorkflowType;   // ADD
    stage_count: number;
    created_at: string;
    updated_at: string;
  }

  // Add workflow_type to WorkflowCreateRequest (line ~791-796)
  export interface WorkflowCreateRequest {
    name: string;
    description?: string;
    is_default?: boolean;
    workflow_type?: WorkflowType;  // ADD (optional, defaults to "project" on backend)
    stages: WorkflowStage[];
  }
  ```
- **Mirror**: `frontend/src/api/types.ts:771-796`
- **Validate**: `cd frontend && npm run build` (no TypeScript errors)

---

### Task 8: Update frontend API client

- **File**: `frontend/src/api/client.ts`
- **Action**: UPDATE — workflow section around line 1010
- **Implement**:
  - Add `WorkflowType` to the import from `'./types'` (line ~50)
  - Update `listWorkflows` to accept optional `workflowType` param:
    ```typescript
    export const listWorkflows = async (workflowType?: WorkflowType): Promise<WorkflowListItem[]> => {
      return retryRequest(async () => {
        const params = workflowType ? { workflow_type: workflowType } : undefined;
        const response = await apiClient.get<WorkflowListItem[]>('/api/workflows', { params });
        return response.data;
      });
    };
    ```
  - Add new `seedDefaultForType` function after `seedDefaultWorkflow`:
    ```typescript
    export const seedDefaultForType = async (workflowType: WorkflowType): Promise<WorkflowTemplate> => {
      return retryRequest(async () => {
        const response = await apiClient.post<WorkflowTemplate>(
          '/api/workflows/seed-default-for-type',
          undefined,
          { params: { workflow_type: workflowType } }
        );
        return response.data;
      });
    };
    ```
- **Mirror**: `frontend/src/api/client.ts:1011-1016` (listWorkflows pattern)
- **Validate**: `cd frontend && npm run build`

---

### Task 9: Update WorkflowBuilder component to accept `workflowType` prop

- **File**: `frontend/src/components/workflow-builder/WorkflowBuilder.tsx`
- **Action**: UPDATE
- **Implement**:
  - Import `WorkflowType` from `'../../api/types'`
  - Import `seedDefaultForType` from `'../../api/client'`
  - Add interface: `interface WorkflowBuilderProps { workflowType: WorkflowType; }`
  - Change function signature: `export const WorkflowBuilder: React.FC<WorkflowBuilderProps> = ({ workflowType }) => {`
  - Wrap `loadWorkflows` in `useCallback` with `[workflowType]` dependency
  - In `loadWorkflows`, call `api.listWorkflows(workflowType)` (pass the type)
  - When the list is empty (no templates for this type), auto-call `api.seedDefaultForType(workflowType)` and set the result as active template
  - In `handleCreateNew`, pass `workflow_type: workflowType` in the `createWorkflow` call
  - Add `useEffect` that resets `activeTemplate`, `editingStage`, `isDirty` to null/false when `workflowType` changes, then calls `loadWorkflows()`
- **Mirror**: `frontend/src/components/workflow-builder/WorkflowBuilder.tsx` (existing load/create patterns)
- **Validate**: `cd frontend && npm run build`

---

### Task 10: Add sub-tabs to SettingsPage for workflow types

- **File**: `frontend/src/pages/SettingsPage.tsx`
- **Action**: UPDATE
- **Implement**:
  - Import `WorkflowType` from `'../api/types'`
  - Add constant (outside component):
    ```typescript
    const WORKFLOW_SUB_TABS: { key: WorkflowType; label: string }[] = [
      { key: 'project',    label: 'Project Workflow' },
      { key: 'qa_session', label: 'QA Session' },
      { key: 'qa_pair',    label: 'QA Pair' },
      { key: 'agentic',    label: 'Agentic Pipeline' },
    ];
    ```
  - Add state inside component: `const [activeWorkflowType, setActiveWorkflowType] = useState<WorkflowType>('project');`
  - Replace the existing `{activeTab === 'workflows' && <WorkflowBuilder />}` line with:
    ```tsx
    {activeTab === 'workflows' && (
      <div>
        <div className="border-b border-gray-100 mb-5">
          <nav className="flex space-x-1 -mb-px">
            {WORKFLOW_SUB_TABS.map((sub) => (
              <button
                key={sub.key}
                onClick={() => setActiveWorkflowType(sub.key)}
                className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                  activeWorkflowType === sub.key
                    ? 'border-indigo-500 text-indigo-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-200'
                }`}
              >
                {sub.label}
              </button>
            ))}
          </nav>
        </div>
        <WorkflowBuilder workflowType={activeWorkflowType} />
      </div>
    )}
    ```
    Note: Uses `indigo` for sub-tab underline to visually distinguish from outer `blue` main tabs.
- **Mirror**: `frontend/src/pages/SettingsPage.tsx` (existing tab conditional rendering pattern)
- **Validate**: `cd frontend && npm run build` + visual check in browser

---

## Validation

```bash
# Backend type check
uv run python -c "from src.models.workflow_models import WorkflowType, WorkflowResponse, WorkflowListItem, WorkflowCreateRequest; print('Models OK')"
uv run python -c "from src.services.workflow_service import WorkflowService, DEFAULT_QA_SESSION_STAGES, DEFAULT_QA_PAIR_STAGES, DEFAULT_AGENTIC_STAGES; print('Service OK')"

# Run unit tests
uv run pytest tests/ -v -m unit

# Start backend and verify seeding
uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
# Check logs: should see 4 "Seeded default X workflow template" messages

# API smoke tests
curl -s "http://localhost:8000/api/workflows" | python3 -m json.tool
curl -s "http://localhost:8000/api/workflows?workflow_type=qa_session" | python3 -m json.tool
curl -s "http://localhost:8000/api/workflows?workflow_type=qa_pair" | python3 -m json.tool
curl -s "http://localhost:8000/api/workflows?workflow_type=agentic" | python3 -m json.tool
curl -s -X POST "http://localhost:8000/api/workflows/seed-default-for-type?workflow_type=agentic" | python3 -m json.tool

# Frontend build check
cd frontend && npm run build

# E2E tests (requires running backend)
uv run pytest tests/e2e/ -v -m e2e
```

---

## Agent Team

5 agents (2 feature + 3 standing). Execute via `/build-with-agent-team .agents/plans/multi-workflow-type-settings.plan.md 5`.

### Feature Agents

#### Agent: backend

- **Owns**: `src/models/workflow_models.py`, `src/services/workflow_service.py`, `src/api/routes/workflows.py`, `src/api/main.py`
- **Does NOT touch**: `frontend/`, `tests/`
- **Responsibilities**:
  - Task 1: Add `WorkflowType` literal + `workflow_type` fields to Pydantic models
  - Task 2: Add 3 new default stage constant sets to workflow service
  - Task 3: Add `list_by_type()` and `seed_default_for_type()` methods to `WorkflowService`
  - Task 4: Fix scoped `is_default` enforcement in `create()`/`update()`/`duplicate()`
  - Task 5: Update routes (add `workflow_type` query param, add `seed-default-for-type` static route — BEFORE `/{workflow_id}`)
  - Task 6: Update lifespan seeding in `main.py` to seed all 4 types
- **Publishes contract**: API contract — `GET /api/workflows?workflow_type={type}` returns `WorkflowListItem[]` each with `workflow_type` field; `POST /api/workflows/seed-default-for-type?workflow_type={type}` returns `WorkflowResponse` with `workflow_type` field
- **Consumes contract from**: none
- **Validation**: `uv run python -c "from src.models.workflow_models import WorkflowType; from src.services.workflow_service import DEFAULT_QA_SESSION_STAGES; print('OK')"`

#### Agent: frontend

- **Owns**: `frontend/src/api/types.ts`, `frontend/src/api/client.ts`, `frontend/src/components/workflow-builder/WorkflowBuilder.tsx`, `frontend/src/pages/SettingsPage.tsx`
- **Does NOT touch**: `src/`, `tests/`
- **Responsibilities**:
  - Task 7: Add `WorkflowType` type + `workflow_type` to 3 TypeScript interfaces in `types.ts`
  - Task 8: Update `listWorkflows()` to accept optional type param; add `seedDefaultForType()` to `client.ts`
  - Task 9: Add `workflowType: WorkflowType` prop to `WorkflowBuilder` component; scope all API calls; auto-seed when empty; reset state on type change
  - Task 10: Add sub-tabs in `SettingsPage` with `WORKFLOW_SUB_TABS` constant and `activeWorkflowType` state
- **Publishes contract**: none (UI only)
- **Consumes contract from**: backend (API shape with `workflow_type` field)
- **Validation**: `cd frontend && npm run build`

### Standing Agents

#### Agent: general

- **Owns**: Files not owned by feature agents (config, shared utilities, glue code)
- **Does NOT touch**: Files owned by feature agents unless explicitly delegated
- **Responsibilities**:
  - Cross-cutting fixes that span multiple agents' domains
  - Config and environment setup tasks
  - Glue code and integration wiring no feature agent owns
- **Validation**: `uv run python -m py_compile src/api/main.py src/models/workflow_models.py`

#### Agent: tester-unit

- **Owns**: `tests/` (excluding `tests/e2e/`)
- **Does NOT touch**: Source implementation files
- **Responsibilities**:
  - Add unit tests to `tests/test_workflow_service.py` (or create if missing):
    - `test_seed_default_for_type_creates_all_types` — mock insert_one, verify workflow_type field set correctly for each type
    - `test_seed_default_for_type_is_idempotent` — mock find_one returns existing, verify insert_one NOT called
    - `test_list_by_type_project_includes_legacy_docs` — mock cursor with mixed docs (has field + missing field), verify both returned for "project"
    - `test_list_by_type_excludes_other_types` — verify "qa_session" query only returns qa_session docs
    - `test_is_default_scoped_by_type` — verify create() update_many includes workflow_type filter
  - Run full test suite, report failures to backend agent
- **Runs after**: backend agent completes Tasks 1–6
- **Validation**: `uv run pytest tests/ -v -m unit`

#### Agent: tester-e2e

- **Owns**: `tests/e2e/`
- **Does NOT touch**: Source implementation files or unit test files
- **Responsibilities**:
  - Uses `/agent-browser` to open `http://localhost:5173`
  - Navigate to Settings → Workflow Builder tab
  - Verify 4 sub-tabs visible: "Project Workflow", "QA Session", "QA Pair", "Agentic Pipeline"
  - Click each sub-tab, verify correct stages load (e.g., Agentic Pipeline shows "Question Analysis", "Knowledge Retrieval", etc.)
  - Verify creating a new template in "QA Session" sub-tab appears only in that sub-tab, not "Project Workflow"
  - Take screenshots at each step
  - Report failures to frontend agent
- **Skills**: Uses `/agent-browser` for browser automation
- **Runs after**: frontend agent and tester-unit complete; requires running backend (`:8000`) + frontend (`:5173`)
- **Validation**: All E2E flows pass with screenshots

### Spawn Order

1. **backend** — runs Tasks 1–6, publishes API contract with `workflow_type` field
2. **frontend** — starts after backend API contract is published; runs Tasks 7–10 consuming the new `workflow_type` field shape
3. **general** — available from the start for cross-cutting work
4. **tester-unit** — spawned after backend completes; writes and runs unit tests
5. **tester-e2e** — spawned after all feature agents and tester-unit pass; needs running backend + frontend

### Cross-Cutting Concerns

| Concern | Owner | Detail |
|---------|-------|--------|
| Static routes before parameterized | backend | `seed-default-for-type` MUST be defined before `/{workflow_id}` in routes/workflows.py |
| Backwards compat for "project" type | backend | `$or` query includes docs with missing `workflow_type` field |
| `is_default` scoped per type | backend | `update_many` in create/update MUST include `workflow_type` filter |
| Sub-tab indigo vs outer blue | frontend | Use `border-indigo-500 text-indigo-600` for sub-tabs to distinguish from outer `border-blue-*` tabs |

---

## Acceptance Criteria

- [ ] All 10 tasks completed
- [ ] `GET /api/workflows?workflow_type=agentic` returns exactly 1 item with 5 stages
- [ ] `GET /api/workflows?workflow_type=project` returns the existing "Polish Tax Interpretations" template
- [ ] Backend startup logs show 4 seed messages (one per type), idempotent on restart
- [ ] Settings → Workflow Builder shows 4 sub-tabs
- [ ] Clicking each sub-tab loads its workflow stages correctly
- [ ] Creating a template in one sub-tab doesn't affect other sub-tabs
- [ ] `cd frontend && npm run build` passes with no TypeScript errors
- [ ] `uv run pytest tests/ -v -m unit` passes
