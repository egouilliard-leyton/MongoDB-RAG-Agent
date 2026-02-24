# Plan: Settings Page, Dashboard Improvements & Stage Workflow Builder

## Summary

The system has rich configuration locked in `.env` and hardcoded Python files with no UI. This plan introduces a MongoDB-backed Settings system (agent prompts with version history, RAG parameters, model config), a full visual Workflow Builder (dynamic stages with per-stage prompt/search overrides inheriting from global defaults), four new Dashboard panels (stage funnel, quality trends, KB health, system metrics), a Prompt Playground for testing prompt changes before deploying, and an analytics-driven feedback loop that suggests search parameter adjustments based on answer ratings.

## User Story

As a system operator / RAG practitioner
I want a Settings page with a visual Workflow Builder, an enhanced Dashboard, and tools to test and improve prompt/search configurations
So that I can configure the RAG agent, define project workflows, and monitor system health without touching code files

## Metadata

| Field | Value |
|-------|-------|
| Type | NEW_CAPABILITY + ENHANCEMENT |
| Complexity | HIGH |
| Systems Affected | Backend (src/), Frontend (frontend/src/), MongoDB (new collections) |

---

## Patterns to Follow

### Service Class (MongoDB + Motor)
```python
# SOURCE: src/services/qa_storage.py:16-29
class QAStorageService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.mongo_client: Optional[AsyncMongoClient] = None
        self.db: Optional[Any] = None

    async def initialize(self) -> None: ...
    async def cleanup(self) -> None: ...
```

### FastAPI Route
```python
# SOURCE: src/api/routes/sessions.py:22, 25-72
router = APIRouter(prefix="/api/sessions", tags=["sessions"])

@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(request: SessionCreateRequest):
    settings = load_settings()
    service = SomeService(settings)
    await service.initialize()
    try:
        result = await service.do_thing(...)
        return SomeResponse(**result)
    finally:
        await service.cleanup()
```

### Router Registration
```python
# SOURCE: src/api/main.py:71-84
app.include_router(sessions.router)
app.include_router(projects.router)
# ... etc
```

### Pydantic Request/Response Models
```python
# SOURCE: src/api/models.py:16-47, 50-64
class SomeRequest(BaseModel):
    field: str = Field(..., min_length=1)

    @field_validator('field')
    @classmethod
    def validate_field(cls, v: str) -> str: ...

class SomeResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str = Field(alias="_id", serialization_alias="_id")
```

### ObjectId Handling
```python
# SOURCE: src/services/qa_storage.py:82-88, 135-137
ObjectId(session_id)          # string → ObjectId for queries
str(result.inserted_id)       # ObjectId → string for responses
session["_id"] = str(session["_id"])  # normalize on read
```

### React Context
```typescript
// SOURCE: frontend/src/contexts/ProjectContext.tsx:5-22, 29-32, 63-77
interface CtxType { data: T | null; isLoading: boolean; error: string | null; doAction: () => Promise<void>; }
const Ctx = createContext<CtxType | undefined>(undefined);
export const useCtx = () => { const c = useContext(Ctx); if (!c) throw new Error('...'); return c; };

// State pattern
const [data, setData] = useState<T | null>(null);
const [isLoading, setIsLoading] = useState(false);
const [error, setError] = useState<string | null>(null);

// Async action pattern
const doAction = useCallback(async () => {
  setIsLoading(true); setError(null);
  try { const r = await api.call(); setState(r); }
  catch (err) { setError(err instanceof Error ? err.message : 'Failed'); throw err; }
  finally { setIsLoading(false); }
}, []);
```

### API Client Function
```typescript
// SOURCE: frontend/src/api/client.ts:247-252, 211-227
export const createSomething = async (data: CreateRequest): Promise<Response> => {
  return retryRequest(async () => {
    const response = await apiClient.post<Response>('/api/endpoint', data);
    return response.data;
  });
};
```

---

## Architecture: Settings Inheritance Model

Three-layer inheritance — global → stage-default → per-stage override:

```
Global Settings (app_settings collection)
  main_system_prompt         ← base prompt, always included
  stage_defaults.system_prompt_append  ← appended to ALL stages (if set)
  stage_defaults.search_params         ← default for all stages
  ↓ (each stage can override)
WorkflowStage.config.system_prompt_append  ← stage-specific append (additive)
WorkflowStage.config.search_params         ← stage-specific param overrides
  ↓ (future: project-level override)
Project.settings_overrides (optional, phase 2)
```

**Prompts are ADDITIVE**: `final_prompt = main_system_prompt + "\n" + stage_defaults.append + "\n" + stage.append`
**Search params are REPLACEMENT**: stage value replaces global value for that field only; null = use global.

---

## New MongoDB Collections

### `app_settings`
```json
{
  "_id": ObjectId,
  "type": "global_config",
  "version": 1,
  "created_at": datetime,
  "updated_at": datetime,
  "main_system_prompt": "string",
  "follow_up_context_prompt": "string",
  "qa_history_prompt": "string",
  "stage_defaults": {
    "system_prompt_append": null,
    "search_params": { "match_count": null, "rrf_k": null, "qa_history_match_count": null }
  },
  "default_match_count": 10,
  "max_match_count": 50,
  "enable_question_decomposition": true,
  "enable_iterative_refinement": true,
  "enable_qa_history_search": true,
  "rrf_k_constant": 60,
  "qa_history_match_count": 3,
  "llm_model": "anthropic/claude-haiku-4.5",
  "llm_base_url": "https://openrouter.ai/api/v1",
  "embedding_model": "text-embedding-3-small",
  "show_full_citations": false
}
```
Version history: `type: "version"` documents with same fields + `version` incremented.

### `workflow_templates`
```json
{
  "_id": ObjectId,
  "name": "Polish Tax Interpretation",
  "description": "string",
  "is_default": true,
  "created_at": datetime,
  "updated_at": datetime,
  "stages": [
    {
      "id": "prep_docs",
      "position": 0,
      "name": "Prepare Documents",
      "description": "string",
      "color": "#6366f1",
      "config": {
        "system_prompt_append": null,
        "search_params": { "match_count": null, "rrf_k": null, "qa_history_match_count": null },
        "metadata_fields": [
          { "key": "deadline", "label": "Submission Deadline", "type": "date", "required": false, "options": [] }
        ],
        "transition_conditions": []
      },
      "transitions": [
        { "to_stage_id": "submit_first_instance", "event": "submit", "label": "Submit Application", "outcome_type": "positive" }
      ]
    }
  ]
}
```

---

## New API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/settings` | Get current global settings |
| PUT | `/api/settings` | Update settings (auto-versions) |
| GET | `/api/settings/history` | Last 20 versions |
| POST | `/api/settings/restore/{version}` | Restore to version |
| POST | `/api/settings/prompt-test` | Test a prompt against sample Q |
| GET | `/api/settings/suggestions` | Parameter adjustment suggestions |
| POST | `/api/settings/suggestions/{id}/apply` | Apply a suggestion |
| GET | `/api/workflows` | List workflow templates |
| POST | `/api/workflows` | Create template |
| GET | `/api/workflows/{id}` | Get template |
| PUT | `/api/workflows/{id}` | Update template |
| DELETE | `/api/workflows/{id}` | Delete (blocked if used by projects) |
| POST | `/api/workflows/{id}/duplicate` | Clone template |
| POST | `/api/workflows/seed-default` | Seed Polish tax workflow |
| GET | `/api/dashboard/stage-funnel` | Projects by stage + time-in-stage |
| GET | `/api/dashboard/answer-quality-trends` | Quality metrics over time (configurable range) |
| GET | `/api/dashboard/kb-health` | Docs, chunks, index, ingestion stats |
| GET | `/api/dashboard/system-metrics` | API latency, error rates, token usage |

---

## Files to Change

### New Files — Backend
| File | Action | Purpose |
|------|--------|---------|
| `.agents/docs/architecture-decisions.md` | CREATE | Data model, API contracts, inheritance semantics for all agents |
| `src/models/settings_models.py` | CREATE | Pydantic models: GlobalSettings, StageDefaultConfig, SearchParamsOverride, SettingsUpdateRequest, SettingsResponse, SettingsVersion |
| `src/models/workflow_models.py` | CREATE | Pydantic models: WorkflowTemplate, WorkflowStage, StageConfig, StageTransition, MetadataFieldDef, TransitionCondition, WorkflowCreateRequest, WorkflowResponse |
| `src/services/settings_service.py` | CREATE | SettingsService: get/update/history/restore + test_prompt + suggestions |
| `src/services/workflow_service.py` | CREATE | WorkflowService: CRUD + seed_default + get_resolved_stage_config() |
| `src/api/routes/settings.py` | CREATE | Settings router (8 endpoints) |
| `src/api/routes/workflows.py` | CREATE | Workflows router (6 endpoints) |

### Modified Files — Backend
| File | Action | Purpose |
|------|--------|---------|
| `src/settings.py` | UPDATE | Add `load_runtime_settings()` that merges env + MongoDB overrides |
| `src/prompts.py` | UPDATE | Load prompts from SettingsService; accept stage_id to build additive prompt |
| `src/agent.py` | UPDATE | Use runtime settings for RAG parameters (rrf_k, match_count, feature flags) |
| `src/tools.py` | UPDATE | Accept optional settings_override dict to use stage-resolved search params |
| `src/services/project_stages.py` | UPDATE | Load stage definitions from WorkflowService instead of hardcoded dict |
| `src/api/routes/projects.py` | UPDATE | Accept workflow_template_id on project creation; use dynamic stages |
| `src/services/analytics_service.py` | UPDATE | Add 4 new aggregation methods (funnel, quality trends, kb health, sys metrics) |
| `src/api/routes/dashboard.py` | UPDATE | Add 4 new endpoints using new analytics methods |
| `src/api/main.py` | UPDATE | Register settings.router and workflows.router |

### New Files — Frontend
| File | Action | Purpose |
|------|--------|---------|
| `frontend/src/contexts/SettingsContext.tsx` | CREATE | Global settings state: current settings, versions, loading, update/restore actions |
| `frontend/src/components/settings/PromptEditor.tsx` | CREATE | Large textarea for editing prompts with character count + syntax hints |
| `frontend/src/components/settings/PromptVersionHistory.tsx` | CREATE | Modal listing versions with restore button and diff preview |
| `frontend/src/components/settings/RAGParametersPanel.tsx` | CREATE | Toggle switches (decomposition, refinement, history) + number inputs (match_count, rrf_k) |
| `frontend/src/components/settings/ModelConfigPanel.tsx` | CREATE | LLM model text input, base_url, embedding model selector |
| `frontend/src/components/settings/StageDefaultsPanel.tsx` | CREATE | Edit global stage defaults: prompt append, search param defaults |
| `frontend/src/components/settings/ParameterSuggestions.tsx` | CREATE | Card list of suggested param adjustments with approve/dismiss |
| `frontend/src/components/prompt-playground/PromptPlayground.tsx` | CREATE | Split-pane: edit prompt left, test question + result right |
| `frontend/src/components/prompt-playground/PromptComparison.tsx` | CREATE | Side-by-side before/after answers when comparing prompt versions |
| `frontend/src/components/workflow-builder/WorkflowBuilder.tsx` | CREATE | Main builder: stage list (drag-reorder), add/delete stages, transitions graph |
| `frontend/src/components/workflow-builder/StageCard.tsx` | CREATE | Stage card in builder: name, color, transition arrows, edit/delete buttons |
| `frontend/src/components/workflow-builder/StageEditor.tsx` | CREATE | Right-panel editor for a stage: name, color, prompt append, search params, metadata fields |
| `frontend/src/components/workflow-builder/TransitionEditor.tsx` | CREATE | Define transitions: to_stage, event label, outcome_type |
| `frontend/src/components/dashboard/StageFunnelChart.tsx` | CREATE | Horizontal funnel/bar showing project counts per stage + avg days-in-stage |
| `frontend/src/components/dashboard/AnswerQualityTrends.tsx` | CREATE | Line chart: good/bad/unrated % over time; configurable date range |
| `frontend/src/components/dashboard/KBHealthPanel.tsx` | CREATE | Stat cards: doc count, chunk count, index status, last ingestion, coverage warning |
| `frontend/src/components/dashboard/SystemMetricsPanel.tsx` | CREATE | Stat cards + sparklines: avg API latency, error rate, background task status |
| `frontend/src/pages/SettingsPage.tsx` | CREATE | Tabbed page: Prompts / RAG Parameters / Model Config / Workflow Builder / Playground |

### Modified Files — Frontend
| File | Action | Purpose |
|------|--------|---------|
| `frontend/src/api/types.ts` | UPDATE | Add: GlobalSettings, SettingsVersion, WorkflowTemplate, WorkflowStage, StageFunnelData, QualityTrendsData, KBHealthData, SystemMetricsData |
| `frontend/src/api/client.ts` | UPDATE | Add all new API functions for settings, workflows, and dashboard endpoints |
| `frontend/src/pages/Dashboard.tsx` | UPDATE | Add 4 new panels below existing charts; add tabs or sections |
| `frontend/src/contexts/DashboardContext.tsx` | UPDATE | Add state + loaders for 4 new data types |
| `frontend/src/components/Layout.tsx` | UPDATE | Add Settings tab (gear icon) in navigation |
| `frontend/src/App.tsx` | UPDATE | Add Settings view to view switcher |

---

## Tasks

Execute in the order shown. Research task first; backend tasks can parallelize within their group; frontend waits on backend contracts.

---

### Research Phase

### Task R1: Architecture Decisions Document

- **File**: `.agents/docs/architecture-decisions.md`
- **Action**: CREATE
- **Agent**: `backend-settings` creates this as its first task
- **Implement**:
  - Document the full `app_settings` MongoDB schema (exact field names, types, defaults)
  - Document the `workflow_templates` schema (exact field names, embedded arrays)
  - Document the settings inheritance resolution algorithm (global → stage_defaults → per-stage override)
  - Document all API endpoint contracts: exact URLs, request bodies, response shapes, status codes
  - Document TypeScript type definitions for frontend agents to implement
  - Document the additive prompt construction logic with pseudocode
  - Document migration strategy: how existing `.env` settings seed the first MongoDB document
- **Validate**: File exists and covers all contracts needed by `backend-workflows`, `frontend-settings`, `frontend-dashboard`

---

### Implementation Phase — Backend Settings (backend-settings agent)

### Task 1: Settings Pydantic Models

- **File**: `src/models/settings_models.py`
- **Action**: CREATE
- **Mirror**: `src/api/models.py:16-64` — follow field validators, ConfigDict, alias pattern
- **Implement**:
  - `SearchParamsOverride(BaseModel)`: `match_count`, `rrf_k`, `qa_history_match_count` all `Optional[int]`
  - `StageDefaultConfig(BaseModel)`: `system_prompt_append: Optional[str]`, `search_params: SearchParamsOverride`
  - `GlobalSettings(BaseModel)`: all 16 configurable fields listed in architecture doc
  - `SettingsUpdateRequest(BaseModel)`: partial update — all fields `Optional`, at least one required
  - `SettingsResponse(BaseModel)`: `id`, `version`, `updated_at`, all GlobalSettings fields
  - `SettingsVersion(BaseModel)`: `version`, `created_at`, `summary` (first 60 chars of what changed)
- **Validate**: `uv run python -c "from src.models.settings_models import GlobalSettings; print('ok')"`

### Task 2: Settings Service

- **File**: `src/services/settings_service.py`
- **Action**: CREATE
- **Mirror**: `src/services/qa_storage.py:16-233` — same init/cleanup/Motor client pattern
- **Implement**:
  - `SettingsService(settings: Settings)` class
  - `get_current() -> dict`: find `type: "global_config"`, if absent seed from env defaults
  - `update(changes: dict, updated_by: str) -> dict`: write new `global_config` doc + archive old as `type: "version"` with incremented version number
  - `get_history(limit=20) -> list[dict]`: return version docs sorted by version desc
  - `restore(version: int) -> dict`: find version doc, re-promote as global_config (creates new version)
  - `test_prompt(prompt: str, test_question: str) -> dict`: instantiate a minimal agent run with given prompt, return answer + latency (reuse `process_question_batch_standalone` with prompt override)
  - `get_suggestions() -> list[dict]`: query last 30 days of qa_pairs; correlate `rating_good` with `match_count` in session metadata; return suggestions if correlation > threshold; include `suggestion_id`, `parameter`, `current_value`, `suggested_value`, `confidence`, `rationale`
  - `apply_suggestion(suggestion_id: str) -> dict`: apply the parameter change via `update()`
  - `_seed_from_env(settings: Settings) -> dict`: build default GlobalSettings from env values + hardcoded prompts from `src/prompts.py`
- **Validate**: `uv run python -c "from src.services.settings_service import SettingsService; print('ok')"`

### Task 3: Settings API Routes

- **File**: `src/api/routes/settings.py`
- **Action**: CREATE
- **Mirror**: `src/api/routes/sessions.py:22-72` — router prefix, post/get pattern, try/finally cleanup
- **Implement**:
  - `router = APIRouter(prefix="/api/settings", tags=["settings"])`
  - `GET /api/settings` → `SettingsResponse`
  - `PUT /api/settings` body `SettingsUpdateRequest` → `SettingsResponse` (201)
  - `GET /api/settings/history` → `list[SettingsVersion]`
  - `POST /api/settings/restore/{version}` → `SettingsResponse`
  - `POST /api/settings/prompt-test` body `{prompt: str, test_question: str}` → `{answer: str, latency_ms: int}`
  - `GET /api/settings/suggestions` → `list[ParameterSuggestion]`
  - `POST /api/settings/suggestions/{suggestion_id}/apply` → `SettingsResponse`
- **Validate**: `uv run python -c "from src.api.routes.settings import router; print(len(router.routes), 'routes')"`

### Task 4: Update Settings Loader

- **File**: `src/settings.py`
- **Action**: UPDATE
- **Implement**:
  - Add `load_runtime_settings(db) -> dict` async function: calls `SettingsService(base_settings).get_current()`, merges over base env settings. Returns merged dict. Falls back to env-only if MongoDB unavailable (log warning).
  - This function is called at request time (not startup) to get latest prompt/RAG params
- **Validate**: `uv run python -c "from src.settings import load_runtime_settings; print('ok')"`

### Task 5: Update Prompts to Use Settings Service

- **File**: `src/prompts.py`
- **Action**: UPDATE
- **Implement**:
  - Add `async def get_main_prompt(db, stage_id: Optional[str] = None) -> str`: fetch GlobalSettings; build additive prompt = `main_system_prompt + "\n" + stage_defaults.system_prompt_append + "\n" + stage.config.system_prompt_append` (skip None segments)
  - Add `async def get_follow_up_prompt(db) -> str`: fetch `follow_up_context_prompt` from settings
  - Add `async def get_history_prompt(db) -> str`: fetch `qa_history_prompt` from settings
  - Keep existing `MAIN_SYSTEM_PROMPT` constant as fallback only
- **Validate**: `uv run python -c "from src.prompts import get_main_prompt; print('ok')"`

### Task 6: Update Agent to Use Runtime Settings

- **File**: `src/agent.py`
- **Action**: UPDATE
- **Implement**:
  - In `process_question_batch_standalone()`: after initializing deps, call `load_runtime_settings(deps.db)` to get current `match_count`, `rrf_k`, feature flags
  - Pass resolved settings to search tools via context
  - Use `get_main_prompt(deps.db, stage_id)` for dynamic prompt building
  - Keep env-based settings as fallback when MongoDB unreachable
- **Validate**: `uv run python -c "from src.agent import rag_agent; print('ok')"`

---

### Implementation Phase — Backend Workflows (backend-workflows agent)

### Task 7: Workflow Pydantic Models

- **File**: `src/models/workflow_models.py`
- **Action**: CREATE
- **Mirror**: `src/api/models.py:16-64`
- **Implement**:
  - `TransitionCondition(BaseModel)`: `type: Literal["min_qa_pairs","session_exported","outcome_marked"]`, `value: Any`
  - `MetadataFieldDef(BaseModel)`: `key`, `label`, `type: Literal["text","date","select","number"]`, `required: bool`, `options: list[str]`
  - `StageConfig(BaseModel)`: `system_prompt_append: Optional[str]`, `search_params: SearchParamsOverride`, `metadata_fields: list[MetadataFieldDef]`, `transition_conditions: list[TransitionCondition]`
  - `StageTransition(BaseModel)`: `to_stage_id: str`, `event: str`, `label: str`, `outcome_type: Literal["positive","negative","neutral"]`
  - `WorkflowStage(BaseModel)`: `id: str`, `position: int`, `name: str`, `description: str`, `color: str`, `transitions: list[StageTransition]`, `config: StageConfig`
  - `WorkflowCreateRequest(BaseModel)`: `name`, `description`, `stages: list[WorkflowStage]`
  - `WorkflowResponse(BaseModel)`: `id`, `name`, `description`, `is_default`, `created_at`, `updated_at`, `stages`
- **Validate**: `uv run python -c "from src.models.workflow_models import WorkflowTemplate; print('ok')"`

### Task 8: Workflow Service

- **File**: `src/services/workflow_service.py`
- **Action**: CREATE
- **Mirror**: `src/services/qa_storage.py:16-233`
- **Implement**:
  - `WorkflowService(settings: Settings)` class, Motor client
  - `list_templates() -> list[dict]`: list all templates sorted by `is_default` desc, `name` asc
  - `create(data: dict) -> dict`
  - `get(workflow_id: str) -> dict`
  - `update(workflow_id: str, data: dict) -> dict`: bump `updated_at`
  - `delete(workflow_id: str) -> None`: raise `ConflictError` if any project references this template
  - `duplicate(workflow_id: str, new_name: str) -> dict`: deep copy, set `is_default=False`
  - `seed_default() -> dict`: if no template exists with `is_default=True`, create from the hardcoded stage list currently in `project_stages.py`
  - `get_stage(workflow_id: str, stage_id: str) -> dict`
  - `get_resolved_stage_config(workflow_id: str, stage_id: str, global_settings: dict) -> dict`: applies inheritance — returns final search params + prompt for that stage
- **Validate**: `uv run python -c "from src.services.workflow_service import WorkflowService; print('ok')"`

### Task 9: Workflow API Routes

- **File**: `src/api/routes/workflows.py`
- **Action**: CREATE
- **Mirror**: `src/api/routes/sessions.py:22-72`
- **Implement**:
  - `router = APIRouter(prefix="/api/workflows", tags=["workflows"])`
  - `GET /api/workflows` → `list[WorkflowResponse]`
  - `POST /api/workflows` body `WorkflowCreateRequest` → `WorkflowResponse` (201)
  - `GET /api/workflows/{id}` → `WorkflowResponse`
  - `PUT /api/workflows/{id}` body `WorkflowCreateRequest` → `WorkflowResponse`
  - `DELETE /api/workflows/{id}` → 204
  - `POST /api/workflows/{id}/duplicate` body `{new_name: str}` → `WorkflowResponse` (201)
  - `POST /api/workflows/seed-default` → `WorkflowResponse` (idempotent)
- **Validate**: `uv run python -c "from src.api.routes.workflows import router; print(len(router.routes), 'routes')"`

### Task 10: Update Project Stages Service

- **File**: `src/services/project_stages.py`
- **Action**: UPDATE
- **Implement**:
  - Add `async def get_stage_definitions(db, workflow_id: Optional[str] = None) -> dict`: if `workflow_id` provided, fetch from WorkflowService; otherwise fetch the `is_default=True` template; fallback to hardcoded dict if MongoDB unavailable
  - Wrap existing `get_stage_options()`, `validate_transition()`, etc. to call `get_stage_definitions()` for stage data
  - Keep hardcoded dict as `FALLBACK_STAGES` constant
- **Validate**: `uv run python -c "from src.services.project_stages import get_stage_definitions; print('ok')"`

### Task 11: Update Projects Route for Workflow Assignment

- **File**: `src/api/routes/projects.py`
- **Action**: UPDATE
- **Implement**:
  - Add optional `workflow_template_id: Optional[str]` to `ProjectCreateRequest`
  - On create, store `workflow_template_id` in project doc metadata
  - In stage transition endpoints, resolve stage definitions from the project's assigned workflow
- **Validate**: `uv run python -c "from src.api.routes.projects import router; print('ok')"`

---

### Implementation Phase — Backend Dashboard (backend-dashboard agent)

### Task 12: Analytics Service — New Aggregation Methods

- **File**: `src/services/analytics_service.py`
- **Action**: UPDATE
- **Mirror**: existing aggregation methods in the same file
- **Implement**:
  - `get_stage_funnel(db) -> list[dict]`: aggregate `projects` collection: group by `stage`, count, compute `avg_days_in_stage` from `stage_history`; return `[{stage_id, stage_name, count, avg_days_in_stage, color}]`
  - `get_quality_trends(db, days=30, granularity="day") -> list[dict]`: aggregate `qa_pairs` by `created_at` bucket; for each bucket return `{date, good_count, bad_count, unrated_count, good_pct}`
  - `get_kb_health(db) -> dict`: return `{total_documents, total_chunks, avg_chunks_per_doc, documents_without_chunks, last_ingestion_at, vector_index_status, text_index_status, index_coverage_pct}`
  - `get_system_metrics(db) -> dict`: compute from request logs (or placeholder if no log collection); return `{avg_response_ms_24h, p95_response_ms_24h, error_rate_24h, total_requests_24h, background_task_last_run, background_task_status}`
- **Validate**: `uv run python -c "from src.services.analytics_service import AnalyticsService; print('ok')"`

### Task 13: Dashboard API Routes — New Endpoints

- **File**: `src/api/routes/dashboard.py`
- **Action**: UPDATE
- **Mirror**: existing endpoints in same file
- **Implement**:
  - `GET /api/dashboard/stage-funnel` → `list[StageFunnelItem]`
  - `GET /api/dashboard/answer-quality-trends?days=30&granularity=day` → `list[QualityTrendPoint]`
  - `GET /api/dashboard/kb-health` → `KBHealthResponse`
  - `GET /api/dashboard/system-metrics` → `SystemMetricsResponse`
- **Validate**: `uv run python -c "from src.api.routes.dashboard import router; print(len(router.routes), 'routes')"`

### Task 14: Register New Routers

- **File**: `src/api/main.py`
- **Action**: UPDATE
- **Mirror**: `src/api/main.py:71-84`
- **Implement**:
  - Import `settings` and `workflows` routers from `src/api/routes/`
  - Add `app.include_router(settings.router)` and `app.include_router(workflows.router)` after existing routers
  - In lifespan startup: call `WorkflowService(settings_obj).seed_default()` to ensure default template exists
- **Validate**: `uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8001 --reload &; sleep 3; curl -s http://localhost:8001/api/settings | python3 -m json.tool; kill %1`

---

### Implementation Phase — Frontend Types & Client (general agent)

### Task 15: TypeScript Types

- **File**: `frontend/src/api/types.ts`
- **Action**: UPDATE
- **Mirror**: `frontend/src/api/types.ts:2-100` — existing interface patterns
- **Implement** (add to end of file):
  - `SearchParamsOverride`: optional int fields for `match_count`, `rrf_k`, `qa_history_match_count`
  - `StageDefaultConfig`: `system_prompt_append`, `search_params`
  - `GlobalSettings`: all 16 configurable fields matching backend model
  - `SettingsResponse`: extends GlobalSettings with `id`, `version`, `updated_at`
  - `SettingsVersion`: `version`, `created_at`, `summary`
  - `MetadataFieldDef`, `TransitionCondition`, `StageConfig`, `StageTransition`, `WorkflowStage`
  - `WorkflowTemplate`: `_id`, `name`, `description`, `is_default`, `created_at`, `updated_at`, `stages`
  - `StageFunnelItem`: `stage_id`, `stage_name`, `count`, `avg_days_in_stage`, `color`
  - `QualityTrendPoint`: `date`, `good_count`, `bad_count`, `unrated_count`, `good_pct`
  - `KBHealthData`: all fields from analytics method
  - `SystemMetricsData`: all fields from analytics method
  - `ParameterSuggestion`: `suggestion_id`, `parameter`, `current_value`, `suggested_value`, `confidence`, `rationale`
- **Validate**: `cd frontend && npx tsc --noEmit`

### Task 16: API Client Functions

- **File**: `frontend/src/api/client.ts`
- **Action**: UPDATE
- **Mirror**: `frontend/src/api/client.ts:247-252` — `retryRequest` wrapping pattern
- **Implement** (add after existing functions):
  - Settings functions: `getSettings`, `updateSettings`, `getSettingsHistory`, `restoreSettings`, `testPrompt`, `getParameterSuggestions`, `applySuggestion`
  - Workflow functions: `listWorkflows`, `createWorkflow`, `getWorkflow`, `updateWorkflow`, `deleteWorkflow`, `duplicateWorkflow`, `seedDefaultWorkflow`
  - Dashboard functions: `getStageFunnel`, `getQualityTrends(days, granularity)`, `getKBHealth`, `getSystemMetrics`
  - Import all new types from `./types`
- **Validate**: `cd frontend && npx tsc --noEmit`

---

### Implementation Phase — Frontend Settings (frontend-settings agent)

### Task 17: Settings Context

- **File**: `frontend/src/contexts/SettingsContext.tsx`
- **Action**: CREATE
- **Mirror**: `frontend/src/contexts/ProjectContext.tsx:5-77`
- **Implement**:
  - State: `currentSettings: SettingsResponse | null`, `versionHistory: SettingsVersion[]`, `isLoading`, `isSaving`, `error`
  - Actions: `loadSettings()`, `saveSettings(changes)`, `loadHistory()`, `restoreVersion(version)`, `clearError()`
  - Export `SettingsProvider` and `useSettings` hook
  - Wrap in `frontend/src/App.tsx` provider tree
- **Validate**: `cd frontend && npx tsc --noEmit`

### Task 18: Prompt Editor Component

- **File**: `frontend/src/components/settings/PromptEditor.tsx`
- **Action**: CREATE
- **Skill**: `/frontend-design` — use for styling the split-panel textarea layout
- **Implement**:
  - Props: `value: string`, `onChange: (v: string) => void`, `label: string`, `placeholder?: string`, `rows?: number`
  - Large `<textarea>` with Tailwind styling matching existing `Textarea.tsx` pattern
  - Character count display
  - `{/* Tip: use {query}, {context}, {history} placeholders */}` tooltip
  - "Reset to default" button that reverts to the seeded value from `.env`
- **Validate**: `cd frontend && npm run build`

### Task 19: Version History Component

- **File**: `frontend/src/components/settings/PromptVersionHistory.tsx`
- **Action**: CREATE
- **Mirror**: `frontend/src/components/Modal.tsx` for modal wrapper
- **Implement**:
  - Props: `versions: SettingsVersion[]`, `currentVersion: number`, `onRestore: (v: number) => void`, `onClose: () => void`
  - List each version: version number, timestamp, summary snippet, "Restore" button
  - Confirm before restoring (inline confirmation or Modal)
  - Use `StatusBadge` for current version
- **Validate**: `cd frontend && npm run build`

### Task 20: RAG Parameters Panel

- **File**: `frontend/src/components/settings/RAGParametersPanel.tsx`
- **Action**: CREATE
- **Skill**: `/frontend-design` — for clean toggle + slider layout
- **Implement**:
  - Boolean toggles (using styled checkbox/switch): `enable_question_decomposition`, `enable_iterative_refinement`, `enable_qa_history_search`, `show_full_citations`
  - Number inputs: `default_match_count` (1-50), `max_match_count`, `rrf_k_constant` (10-120), `qa_history_match_count` (1-10)
  - Descriptive label and tooltip for each parameter explaining what it does
  - "Unsaved changes" indicator when form is dirty
- **Validate**: `cd frontend && npm run build`

### Task 21: Model Config Panel

- **File**: `frontend/src/components/settings/ModelConfigPanel.tsx`
- **Action**: CREATE
- **Implement**:
  - Text inputs for `llm_model` (with common model suggestions as datalist), `llm_base_url`, `embedding_model`, `embedding_base_url`
  - Note: "API keys are managed in .env — not shown here for security"
  - Warning badge if base_url looks like OpenAI direct (suggest using OpenRouter for cost control)
- **Validate**: `cd frontend && npm run build`

### Task 22: Stage Defaults Panel

- **File**: `frontend/src/components/settings/StageDefaultsPanel.tsx`
- **Action**: CREATE
- **Implement**:
  - `PromptEditor` for `stage_defaults.system_prompt_append` with label "Default Stage Prompt Addition (appended to all stages unless overridden)"
  - Number inputs for `stage_defaults.search_params` fields with note "null = use global defaults"
  - Explanation: "These defaults apply to every stage. Individual stages can override or add to these."
- **Validate**: `cd frontend && npm run build`

### Task 23: Parameter Suggestions Component

- **File**: `frontend/src/components/settings/ParameterSuggestions.tsx`
- **Action**: CREATE
- **Implement**:
  - Load suggestions from `GET /api/settings/suggestions`
  - Each suggestion as a card: parameter name, current vs. suggested value, confidence bar, rationale text, "Apply" + "Dismiss" buttons
  - Empty state when no suggestions
  - "Last analyzed: X days ago" footer
- **Validate**: `cd frontend && npm run build`

### Task 24: Prompt Playground

- **File**: `frontend/src/components/prompt-playground/PromptPlayground.tsx`
- **Action**: CREATE
- **Skill**: `/frontend-design` — for the split-pane layout
- **Implement**:
  - Left pane: `PromptEditor` + test question `<textarea>`
  - "Test" button → POST `/api/settings/prompt-test`
  - Right pane: response text + latency badge
  - "Compare with current" toggle: shows current deployed answer alongside test answer
  - Loading spinner during test execution
- **Validate**: `cd frontend && npm run build`

### Task 25: Workflow Builder

- **File**: `frontend/src/components/workflow-builder/WorkflowBuilder.tsx` (+ StageCard, StageEditor, TransitionEditor)
- **Action**: CREATE
- **Skill**: `/frontend-design` — for the builder canvas layout
- **Implement**:
  - `WorkflowBuilder`: fetch templates list; show active template; add new template button
  - `StageCard`: stage name, color dot, transition count badge, edit/delete icon buttons; drag handle for reorder (use HTML5 drag-and-drop or simple up/down arrows — keep it simple)
  - `StageEditor` (right panel or modal): `name`, `description`, `color` picker, `PromptEditor` for `config.system_prompt_append`, search param overrides inputs, `MetadataFieldDef` list editor (add/remove fields), `TransitionEditor` for each transition
  - `TransitionEditor`: target stage dropdown (stages from same template), event label, outcome_type select
  - "Save Template" button → PUT `/api/workflows/{id}`
  - "Add Stage" button → appends blank stage at end
  - "Delete Stage" confirmation → removes stage and any transitions pointing to it
- **Validate**: `cd frontend && npm run build`

### Task 26: Settings Page Assembly

- **File**: `frontend/src/pages/SettingsPage.tsx`
- **Action**: CREATE
- **Skill**: `/frontend-design` — for the tabbed page layout matching existing Dashboard style
- **Implement**:
  - Tabs: "Prompts" | "RAG Parameters" | "Model Config" | "Stage Defaults" | "Workflow Builder" | "Playground"
  - Each tab renders the relevant component(s)
  - "Prompts" tab: three `PromptEditor` sections (Main, Follow-up, History) + `PromptVersionHistory` button + `ParameterSuggestions`
  - Global save button at top right: calls `saveSettings()` with all dirty fields
  - Unsaved changes warning on tab navigate if form is dirty
  - Use `useSettings()` context for state
- **Validate**: `cd frontend && npm run build`

### Task 27: Wire Settings into App

- **File**: `frontend/src/App.tsx` and `frontend/src/components/Layout.tsx`
- **Action**: UPDATE
- **Mirror**: existing view switching pattern in `App.tsx`
- **Implement**:
  - Add `settings` view to the view switcher in `App.tsx`
  - Wrap app with `SettingsProvider`
  - Add Settings tab in `Layout.tsx` navigation (gear/cog icon, label "Settings") after Dashboard tab
- **Validate**: `cd frontend && npm run build && npm run dev` — confirm Settings tab appears

---

### Implementation Phase — Frontend Dashboard (frontend-dashboard agent)

### Task 28: Stage Funnel Chart

- **File**: `frontend/src/components/dashboard/StageFunnelChart.tsx`
- **Action**: CREATE
- **Mirror**: `frontend/src/components/DashboardCharts.tsx` — Recharts BarChart pattern
- **Implement**:
  - Horizontal `BarChart` from Recharts: y-axis = stage names, x-axis = project count
  - Each bar colored by stage's `color` field
  - Tooltip showing: project count, avg days in stage
  - "Stalled" badge on stages with avg_days > threshold (configurable, default 14)
  - Title "Pipeline Status" with refresh button
- **Validate**: `cd frontend && npm run build`

### Task 29: Answer Quality Trends Chart

- **File**: `frontend/src/components/dashboard/AnswerQualityTrends.tsx`
- **Action**: CREATE
- **Mirror**: existing `LineChart` usage in `DashboardCharts.tsx`
- **Implement**:
  - Stacked `AreaChart` or `LineChart`: three lines (good%, bad%, unrated%)
  - Date range selector: 7d / 14d / 30d / 90d
  - Granularity toggle: daily / weekly
  - Summary stat: "Average good rate: X% over selected period"
  - Fetches from `GET /api/dashboard/answer-quality-trends?days=30&granularity=day`
- **Validate**: `cd frontend && npm run build`

### Task 30: Knowledge Base Health Panel

- **File**: `frontend/src/components/dashboard/KBHealthPanel.tsx`
- **Action**: CREATE
- **Mirror**: summary cards pattern from `Dashboard.tsx`
- **Implement**:
  - Stat cards: Total Documents, Total Chunks, Avg Chunks/Doc, Index Status (badge: healthy/warning/error), Last Ingestion (relative time)
  - Warning card if `documents_without_chunks > 0`: "X documents have no indexed chunks"
  - Index status colors: green (healthy), yellow (degraded), red (error/missing)
  - Fetches from `GET /api/dashboard/kb-health`
- **Validate**: `cd frontend && npm run build`

### Task 31: System Metrics Panel

- **File**: `frontend/src/components/dashboard/SystemMetricsPanel.tsx`
- **Action**: CREATE
- **Implement**:
  - Stat cards: Avg Response (ms), P95 Response (ms), Error Rate (%), Requests (24h)
  - Background task card: last run time, next scheduled run, status badge (running/idle/error)
  - Color-coded: green (<200ms avg), yellow (200-500ms), red (>500ms)
  - Auto-refresh every 60s
  - Fetches from `GET /api/dashboard/system-metrics`
- **Validate**: `cd frontend && npm run build`

### Task 32: Dashboard Page Assembly

- **File**: `frontend/src/pages/Dashboard.tsx` and `frontend/src/contexts/DashboardContext.tsx`
- **Action**: UPDATE
- **Implement**:
  - Add state + loaders in `DashboardContext` for: `stageFunnel`, `qualityTrends`, `kbHealth`, `systemMetrics`
  - Add 4 new panels in `Dashboard.tsx` below existing charts:
    - Full-width: `StageFunnelChart`
    - Two-column: `AnswerQualityTrends` (left) | `KBHealthPanel` (right)
    - Full-width: `SystemMetricsPanel`
  - Load new data in `loadAllData()` (parallel with `Promise.all`)
- **Validate**: `cd frontend && npm run build`

---

## Validation

```bash
# Backend: type check + lint
cd /path/to/project
uv run python -c "from src.api.main import app; print('Backend imports OK')"
uv run ruff check src/

# Frontend: type check + build
cd frontend
npx tsc --noEmit
npm run build

# Integration: start backend + check endpoints
uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8000 &
sleep 3
curl -s http://localhost:8000/api/settings | python3 -m json.tool
curl -s http://localhost:8000/api/workflows | python3 -m json.tool
curl -s http://localhost:8000/api/dashboard/stage-funnel | python3 -m json.tool
curl -s http://localhost:8000/api/dashboard/kb-health | python3 -m json.tool
kill %1

# Frontend: start dev server + manual check
cd frontend && npm run dev
# Navigate to Settings tab, Workflow Builder tab, Dashboard new panels
```

---

## Agent Team

8 agents (5 feature + 3 standing). Execute via `/build-with-agent-team .agents/plans/settings-dashboard-workflow-builder.plan.md 8`.

### Feature Agents

#### Agent: backend-settings

- **Owns**: `src/models/settings_models.py`, `src/services/settings_service.py`, `src/api/routes/settings.py`, `.agents/docs/architecture-decisions.md`
- **Also updates**: `src/settings.py`, `src/prompts.py`, `src/agent.py`
- **Does NOT touch**: `frontend/`, `src/models/workflow_models.py`, `src/services/workflow_service.py`
- **Responsibilities**:
  - CREATE architecture decisions doc first (Task R1) — all other agents wait on this
  - CREATE settings models, service, routes (Tasks 1–3)
  - UPDATE settings loader, prompts, agent to use runtime settings (Tasks 4–6)
- **Publishes contract**: Architecture decisions doc at `.agents/docs/architecture-decisions.md` containing exact MongoDB schemas, API response shapes, TypeScript type definitions, and inheritance resolution algorithm
- **Consumes contract from**: None — this agent goes first
- **Validation**: `uv run python -c "from src.api.routes.settings import router; print('settings routes ok')" && uv run ruff check src/models/settings_models.py src/services/settings_service.py src/api/routes/settings.py`

#### Agent: backend-workflows

- **Owns**: `src/models/workflow_models.py`, `src/services/workflow_service.py`, `src/api/routes/workflows.py`
- **Also updates**: `src/services/project_stages.py`, `src/api/routes/projects.py`
- **Does NOT touch**: `frontend/`, `src/services/settings_service.py`
- **MUST read before starting**: `.agents/docs/architecture-decisions.md` (for workflow schema)
- **Responsibilities**:
  - CREATE workflow models, service, routes (Tasks 7–9)
  - UPDATE project stages to be DB-driven (Tasks 10–11)
- **Publishes contract**: Workflow API endpoints with exact request/response shapes — appended to architecture decisions doc
- **Consumes contract from**: `backend-settings` (architecture doc must exist)
- **Validation**: `uv run python -c "from src.api.routes.workflows import router; print('workflow routes ok')"`

#### Agent: backend-dashboard

- **Owns**: Changes to `src/services/analytics_service.py`, `src/api/routes/dashboard.py`
- **Does NOT touch**: `frontend/`, other services
- **MUST read before starting**: `.agents/docs/architecture-decisions.md`
- **Responsibilities**:
  - ADD 4 aggregation methods to analytics service (Task 12)
  - ADD 4 new dashboard endpoints (Task 13)
  - Register new routers in `src/api/main.py` (Task 14)
- **Publishes contract**: New dashboard endpoint shapes appended to architecture decisions doc
- **Consumes contract from**: `backend-settings` (architecture doc)
- **Validation**: `uv run python -c "from src.api.routes.dashboard import router; print(len(router.routes), 'dashboard routes')"`

#### Agent: frontend-settings

- **Owns**: `frontend/src/contexts/SettingsContext.tsx`, `frontend/src/components/settings/`, `frontend/src/components/workflow-builder/`, `frontend/src/components/prompt-playground/`, `frontend/src/pages/SettingsPage.tsx`
- **Also updates**: `frontend/src/App.tsx`, `frontend/src/components/Layout.tsx`
- **Does NOT touch**: `src/` (backend), `frontend/src/components/dashboard/`, `frontend/src/api/types.ts` (general agent owns), `frontend/src/api/client.ts` (general agent owns)
- **MUST read before starting**: `.agents/docs/architecture-decisions.md` (for all type shapes and API contracts)
- **Skill**: Uses `/frontend-design` for SettingsPage tabs, PromptEditor layout, WorkflowBuilder canvas, PromptPlayground split-pane
- **Responsibilities**:
  - CREATE all settings, workflow builder, playground components (Tasks 17–25)
  - CREATE SettingsPage (Task 26) and wire into App (Task 27)
- **Publishes contract**: None — consumes contracts from backend agents via architecture doc
- **Consumes contract from**: `backend-settings`, `backend-workflows` via architecture decisions doc + `general` agent for types/client
- **Validation**: `cd frontend && npx tsc --noEmit && npm run build`

#### Agent: frontend-dashboard

- **Owns**: `frontend/src/components/dashboard/StageFunnelChart.tsx`, `AnswerQualityTrends.tsx`, `KBHealthPanel.tsx`, `SystemMetricsPanel.tsx`
- **Also updates**: `frontend/src/pages/Dashboard.tsx`, `frontend/src/contexts/DashboardContext.tsx`
- **Does NOT touch**: `src/` (backend), `frontend/src/components/settings/`, `frontend/src/api/types.ts`, `frontend/src/api/client.ts`
- **MUST read before starting**: `.agents/docs/architecture-decisions.md` (for new dashboard endpoint shapes)
- **Responsibilities**:
  - CREATE 4 new dashboard components (Tasks 28–31)
  - UPDATE Dashboard page and context (Task 32)
- **Publishes contract**: None — consumes from `backend-dashboard` via architecture doc
- **Consumes contract from**: `backend-dashboard` via architecture decisions doc + `general` agent for types/client
- **Validation**: `cd frontend && npx tsc --noEmit && npm run build`

### Standing Agents

#### Agent: general

- **Owns**: `frontend/src/api/types.ts`, `frontend/src/api/client.ts`, `src/api/main.py` (router registration), integration wiring
- **Does NOT touch**: Component files owned by feature agents, service files owned by backend agents
- **MUST read before starting**: `.agents/docs/architecture-decisions.md` (for exact type shapes and API signatures)
- **Responsibilities**:
  - ADD TypeScript types to `frontend/src/api/types.ts` (Task 15)
  - ADD API client functions to `frontend/src/api/client.ts` (Task 16)
  - Register new routers in `src/api/main.py` (Task 14, coordinates with backend-dashboard)
  - Cross-cutting config or wiring that no feature agent owns
- **Delegation rules**: Feature agents request type/client additions from this agent via message
- **Validation**: `cd frontend && npx tsc --noEmit && uv run python -c "from src.api.main import app; print('main ok')"`

#### Agent: tester-unit

- **Owns**: `tests/test_settings_service.py`, `tests/test_workflow_service.py`, `tests/test_dashboard_analytics.py`
- **Does NOT touch**: Source implementation files
- **Responsibilities**:
  - Unit tests for `SettingsService`: get/update/versioning/restore/seed, inheritance resolution
  - Unit tests for `WorkflowService`: CRUD, seed_default, get_resolved_stage_config
  - Unit tests for new analytics methods: stage funnel, quality trends, kb health
  - Mock MongoDB using `mongomock` or `unittest.mock`
  - Run `uv run ruff check src/` and report lint issues to responsible agent
- **Runs after**: `backend-settings`, `backend-workflows`, `backend-dashboard` complete
- **Validation**: `uv run pytest tests/test_settings_service.py tests/test_workflow_service.py tests/test_dashboard_analytics.py -v`

#### Agent: tester-e2e

- **Owns**: `e2e/` or `ui_tests/` directory
- **Does NOT touch**: Source implementation or unit test files
- **Skills**:
  - Uses `/agent-browser` — `agent-browser open`, `agent-browser snapshot`, `agent-browser click`, `agent-browser type`
  - Uses `/document-skills:webapp-testing` if available for Playwright-based checks
- **Responsibilities**:
  - Navigate to Settings tab: verify it loads, all 6 sub-tabs render
  - Test Prompt Editor: edit text, click Save, verify success toast
  - Test Version History: click History button, verify modal shows versions
  - Test Workflow Builder: add a stage, rename it, save
  - Test Prompt Playground: enter test question, click Test, verify response appears
  - Dashboard: navigate to Dashboard, verify all 4 new panels render with data or empty states
  - Take screenshots of each completed test
- **Runs after**: `tester-unit` passes and app is running (`npm run dev` + `uvicorn`)
- **Validation**: All E2E flows pass with screenshots captured in `e2e/screenshots/`

### Spawn Order

1. **backend-settings** — first; produces architecture decisions doc (`.agents/docs/architecture-decisions.md`). All other agents WAIT until this doc exists and settings API contract is published.
2. **backend-workflows** + **backend-dashboard** + **general** — spawn in parallel after `backend-settings` publishes its contract. `general` should tackle types/client as soon as architecture doc is ready.
3. **frontend-settings** + **frontend-dashboard** — spawn after `general` has published types and client functions (or can start with stubs and update).
4. **tester-unit** — after backend feature agents complete their tasks.
5. **tester-e2e** — after `tester-unit` passes and both frontend agents complete their builds.

### Cross-Cutting Concerns

| Concern | Owner | Detail |
|---------|-------|--------|
| MongoDB collection name for settings | `backend-settings` | Use `app_settings` (constant in `src/settings.py` as `mongodb_collection_app_settings = "app_settings"`) |
| MongoDB collection name for workflows | `backend-workflows` | Use `workflow_templates` (add constant to `src/settings.py`) |
| Settings cache invalidation | `backend-settings` | `load_runtime_settings()` fetches fresh on each request — no in-memory cache to avoid stale config |
| Prompt fallback | `backend-settings` | If MongoDB unavailable, fall back to `src/prompts.py` constants |
| Stage colors | `backend-workflows` | Seed default uses distinct hex palette; frontend builder provides a color picker |
| API key security | `general` | API keys stay in `.env` only; `llm_api_key` and `embedding_api_key` NEVER written to MongoDB or returned by settings API |
| TypeScript strict mode | `general` | Maintain `"strict": true` in `tsconfig.json` — no `any` without `// eslint-disable` comment |
| Tailwind class consistency | `frontend-settings` + `frontend-dashboard` | Match existing component patterns from `Button.tsx`, `StatusBadge.tsx`, `CollapsibleSection.tsx` |

---

## Acceptance Criteria

- [ ] Task R1 complete: `.agents/docs/architecture-decisions.md` exists and covers all contracts
- [ ] `GET /api/settings` returns current settings (seeded from env on first call)
- [ ] `PUT /api/settings` saves changes and creates a version entry
- [ ] `GET /api/settings/history` returns version list
- [ ] `GET /api/workflows` returns at least the seeded default workflow
- [ ] `PUT /api/workflows/{id}` saves stage changes (name, color, transitions, per-stage config)
- [ ] `GET /api/dashboard/stage-funnel` returns projects grouped by stage
- [ ] `GET /api/dashboard/answer-quality-trends` returns time-series quality data
- [ ] `GET /api/dashboard/kb-health` returns document/index health
- [ ] `GET /api/dashboard/system-metrics` returns system performance data
- [ ] Settings tab appears in frontend navigation
- [ ] All 6 sub-tabs render without errors
- [ ] Prompt editor shows current prompts and saves changes
- [ ] Version history modal lists versions with restore capability
- [ ] Workflow Builder shows stages, allows adding/editing/deleting stages
- [ ] Per-stage config (prompt append, search params, metadata fields, transitions) saves correctly
- [ ] Prompt Playground executes a test question and shows result
- [ ] All 4 new dashboard panels render with real or empty-state data
- [ ] `cd frontend && npx tsc --noEmit` passes (zero type errors)
- [ ] `uv run ruff check src/` passes (zero lint errors)
- [ ] Unit tests pass for settings service, workflow service, analytics methods
- [ ] E2E screenshots captured for all user flows
