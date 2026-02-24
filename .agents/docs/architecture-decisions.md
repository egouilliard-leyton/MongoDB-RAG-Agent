# Architecture Decisions: Settings, Workflows & Dashboard

> Authoritative reference for all agents. Any conflict between this document and individual task descriptions: **this document wins**.

---

## 1. New MongoDB Collection Constants

Add to `src/settings.py` (inside the `Settings` class):

```python
mongodb_collection_app_settings: str = Field(
    default="app_settings", description="Collection for application settings and version history"
)
mongodb_collection_workflow_templates: str = Field(
    default="workflow_templates", description="Collection for workflow templates"
)
```

---

## 2. `app_settings` Collection Schema

A single collection stores both the **active configuration** and its **version history**.

### Active Document (`type: "global_config"`)

Only ONE document with `type: "global_config"` exists at any time.

```jsonc
{
  "_id": ObjectId,
  "type": "global_config",
  "version": 1,                           // monotonically incrementing integer
  "main_system_prompt": "<string>",       // seeded from MAIN_SYSTEM_PROMPT
  "follow_up_context_prompt": "<string>", // seeded from FOLLOW_UP_CONTEXT_PROMPT
  "qa_history_prompt": "<string>",        // seeded from QA_HISTORY_PROMPT
  "stage_defaults": {
    "system_prompt_append": null,         // Optional[str]
    "search_params": {
      "match_count": null,                // Optional[int]
      "rrf_k": null,                      // Optional[int]
      "qa_history_match_count": null      // Optional[int]
    }
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
  "show_full_citations": false,
  "updated_at": ISODate,
  "created_at": ISODate
}
```

### Version Document (`type: "version"`)

Created every time the active config is updated.

```jsonc
{
  "_id": ObjectId,
  "type": "version",
  "version": 1,                 // same version number as the config it archived
  "snapshot": { /* full copy of all GlobalSettings fields at that point */ },
  "changed_fields": ["main_system_prompt", "default_match_count"],
  "summary": "Updated main_system_prompt, default_match_count",
  "created_at": ISODate
}
```

### Version Numbering Strategy

- Version starts at `1` on first seed.
- Each `PUT /api/settings` call: increments version by 1, archives old config as a version doc, writes new config with the new version.
- `POST /api/settings/restore/{version}`: finds the version doc, creates a new version (current + 1) with the restored snapshot as the new global_config.

---

## 3. `workflow_templates` Collection Schema

```jsonc
{
  "_id": ObjectId,
  "name": "Polish Tax Interpretations",
  "description": "Standard workflow for IP Box / R&D tax interpretations",
  "is_default": true,                     // at most one template is default
  "stages": [
    {
      "id": "intake",                     // unique within template; kebab-case
      "label": "Intake",
      "description": "Initial document collection",
      "order": 0,
      "color": "#3B82F6",                 // hex color
      "config": {
        "system_prompt_append": null,     // Optional[str]
        "search_params": {
          "match_count": null,            // Optional[int]
          "rrf_k": null,                  // Optional[int]
          "qa_history_match_count": null  // Optional[int]
        },
        "metadata_fields": [
          {
            "key": "company_nip",
            "label": "Company NIP",
            "field_type": "text",         // "text" | "number" | "date" | "select"
            "required": true,
            "options": null               // only for "select" type
          }
        ],
        "auto_advance": false
      },
      "transitions": [
        {
          "to_stage_id": "analysis",
          "label": "Start Analysis",
          "condition": null               // Optional: { "type": "all_questions_answered" } etc.
        }
      ]
    },
    {
      "id": "analysis",
      "label": "Analysis",
      "description": "AI-assisted analysis phase",
      "order": 1,
      "color": "#8B5CF6",
      "config": {
        "system_prompt_append": "Focus on legal analysis and precedent identification.",
        "search_params": {
          "match_count": 10,
          "rrf_k": null,
          "qa_history_match_count": null
        },
        "metadata_fields": [],
        "auto_advance": false
      },
      "transitions": [
        { "to_stage_id": "review", "label": "Send to Review", "condition": null }
      ]
    },
    {
      "id": "review",
      "label": "Review",
      "description": "Senior consultant review",
      "order": 2,
      "color": "#F59E0B",
      "config": {
        "system_prompt_append": null,
        "search_params": { "match_count": null, "rrf_k": null, "qa_history_match_count": null },
        "metadata_fields": [],
        "auto_advance": false
      },
      "transitions": [
        { "to_stage_id": "complete", "label": "Approve", "condition": null },
        { "to_stage_id": "analysis", "label": "Return to Analysis", "condition": null }
      ]
    },
    {
      "id": "complete",
      "label": "Complete",
      "description": "Workflow complete",
      "order": 3,
      "color": "#10B981",
      "config": {
        "system_prompt_append": null,
        "search_params": { "match_count": null, "rrf_k": null, "qa_history_match_count": null },
        "metadata_fields": [],
        "auto_advance": false
      },
      "transitions": []
    }
  ],
  "created_at": ISODate,
  "updated_at": ISODate
}
```

---

## 4. Settings Inheritance Algorithm

When resolving settings for a given stage:

```
# Prompt inheritance (additive, skip None segments)
segments = [global.main_system_prompt]
if global.stage_defaults.system_prompt_append is not None:
    segments.append(global.stage_defaults.system_prompt_append)
if stage and stage.config.system_prompt_append is not None:
    segments.append(stage.config.system_prompt_append)
final_prompt = "\n".join(segments)

# Search param inheritance (stage overrides global, which overrides env defaults)
final_match_count = (
    stage.config.search_params.match_count
    ?? global.stage_defaults.search_params.match_count
    ?? global.default_match_count
)
final_rrf_k = (
    stage.config.search_params.rrf_k
    ?? global.stage_defaults.search_params.rrf_k
    ?? global.rrf_k_constant
)
final_qa_history_match_count = (
    stage.config.search_params.qa_history_match_count
    ?? global.stage_defaults.search_params.qa_history_match_count
    ?? global.qa_history_match_count
)
```

`??` = "use left if not None, else right" (Python: `left if left is not None else right`).

---

## 5. API Endpoint Contracts

### 5.1 Settings Endpoints

#### `GET /api/settings`

Returns the current active settings.

- **Response 200:**
```json
{
  "id": "6789abcdef012345",
  "version": 3,
  "main_system_prompt": "...",
  "follow_up_context_prompt": "...",
  "qa_history_prompt": "...",
  "stage_defaults": {
    "system_prompt_append": null,
    "search_params": {
      "match_count": null,
      "rrf_k": null,
      "qa_history_match_count": null
    }
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
  "show_full_citations": false,
  "updated_at": "2026-02-23T12:00:00Z"
}
```

#### `PUT /api/settings`

Partial update. Only provided fields are changed.

- **Request Body:**
```json
{
  "default_match_count": 15,
  "main_system_prompt": "Updated prompt..."
}
```
- **Validation:** At least one field must be provided. Unknown fields are ignored.
- **Side effect:** Archives current config as a version document, increments version.
- **Response 200:** Same shape as `GET /api/settings` (the new config).

#### `GET /api/settings/history`

- **Query params:** `limit` (int, default 20, max 100)
- **Response 200:**
```json
[
  {
    "version": 2,
    "changed_fields": ["default_match_count"],
    "summary": "Updated default_match_count",
    "created_at": "2026-02-23T11:00:00Z"
  },
  {
    "version": 1,
    "changed_fields": [],
    "summary": "Initial seed from environment",
    "created_at": "2026-02-23T10:00:00Z"
  }
]
```

#### `POST /api/settings/restore/{version}`

Restores a historical version as the new active config (creates a new version number).

- **Path param:** `version` (int)
- **Response 200:** Same shape as `GET /api/settings`.
- **Response 404:** `{"detail": "Version 99 not found"}`

#### `POST /api/settings/prompt-test`

Test a prompt against a sample question.

- **Request Body:**
```json
{
  "prompt": "You are a tax expert...",
  "test_question": "What is IP Box?"
}
```
- **Response 200:**
```json
{
  "answer": "IP Box is a tax relief mechanism...",
  "latency_ms": 1523
}
```

#### `GET /api/settings/suggestions`

Returns AI-generated parameter suggestions based on Q&A history analysis.

- **Response 200:**
```json
[
  {
    "suggestion_id": "increase_match_count",
    "parameter": "default_match_count",
    "current_value": 10,
    "suggested_value": 15,
    "confidence": 0.75,
    "rationale": "Low-rated answers had fewer search results on average"
  }
]
```
May return empty list `[]` if insufficient data.

#### `POST /api/settings/suggestions/{suggestion_id}/apply`

Apply a suggestion by ID.

- **Path param:** `suggestion_id` (string)
- **Response 200:** Same shape as `GET /api/settings` (updated config).
- **Response 404:** `{"detail": "Suggestion 'xyz' not found or expired"}`

---

### 5.2 Workflow Endpoints

#### `GET /api/workflows`

List all workflow templates.

- **Response 200:**
```json
[
  {
    "id": "6789abcdef012345",
    "name": "Polish Tax Interpretations",
    "description": "Standard workflow...",
    "is_default": true,
    "stage_count": 4,
    "created_at": "2026-02-23T10:00:00Z",
    "updated_at": "2026-02-23T10:00:00Z"
  }
]
```

#### `POST /api/workflows`

Create a new workflow template.

- **Request Body:**
```json
{
  "name": "Custom Workflow",
  "description": "A custom workflow",
  "is_default": false,
  "stages": [ /* full stage array */ ]
}
```
- **Validation:** `name` required, non-empty. Stage `id` must be unique within template. Stage `order` must be sequential starting from 0.
- **Response 201:** Full workflow template document (same shape as single GET).

#### `GET /api/workflows/{workflow_id}`

Get a single workflow template.

- **Response 200:**
```json
{
  "id": "6789abcdef012345",
  "name": "Polish Tax Interpretations",
  "description": "Standard workflow...",
  "is_default": true,
  "stages": [ /* full stage array with config, transitions */ ],
  "created_at": "2026-02-23T10:00:00Z",
  "updated_at": "2026-02-23T10:00:00Z"
}
```
- **Response 404:** `{"detail": "Workflow template not found: <id>"}`

#### `PUT /api/workflows/{workflow_id}`

Update a workflow template (full replacement of stages).

- **Request Body:** Same shape as POST body.
- **Response 200:** Updated workflow template.
- **Response 404:** `{"detail": "Workflow template not found: <id>"}`

#### `DELETE /api/workflows/{workflow_id}`

Delete a workflow template.

- **Response 204:** No content.
- **Response 404:** `{"detail": "Workflow template not found: <id>"}`
- **Response 409:** `{"detail": "Cannot delete the default workflow template"}`

#### `POST /api/workflows/{workflow_id}/duplicate`

Duplicate a workflow template.

- **Request Body (optional):**
```json
{
  "name": "Copy of My Workflow"
}
```
- **Response 201:** New workflow template.

---

### 5.3 Dashboard Endpoints (New Panels)

These extend the existing `/api/dashboard` router.

#### `GET /api/dashboard/stage-funnel`

Stage distribution across active projects.

- **Query params:** `workflow_id` (optional string)
- **Response 200:**
```json
{
  "funnel": [
    { "stage_id": "intake", "label": "Intake", "color": "#3B82F6", "count": 12, "percentage": 40.0 },
    { "stage_id": "analysis", "label": "Analysis", "color": "#8B5CF6", "count": 8, "percentage": 26.7 },
    { "stage_id": "review", "label": "Review", "color": "#F59E0B", "count": 7, "percentage": 23.3 },
    { "stage_id": "complete", "label": "Complete", "color": "#10B981", "count": 3, "percentage": 10.0 }
  ],
  "total_projects": 30
}
```

#### `GET /api/dashboard/quality-trend`

Answer quality over time.

- **Query params:** `days` (int, default 30), `granularity` ("day" | "week" | "month", default "day")
- **Response 200:**
```json
{
  "trend": [
    {
      "date": "2026-02-01",
      "good_count": 15,
      "bad_count": 3,
      "total_rated": 18,
      "good_ratio": 0.83
    }
  ],
  "period_days": 30,
  "granularity": "day"
}
```

#### `GET /api/dashboard/kb-health`

Knowledge base health metrics.

- **Response 200:**
```json
{
  "total_documents": 150,
  "total_chunks": 3200,
  "avg_chunks_per_doc": 21.3,
  "embedding_coverage": 1.0,
  "last_ingestion": "2026-02-20T15:00:00Z",
  "stale_document_count": 5,
  "stale_threshold_days": 90
}
```

#### `GET /api/dashboard/system-metrics`

System performance metrics.

- **Response 200:**
```json
{
  "avg_response_time_ms": 2340,
  "avg_search_time_ms": 450,
  "total_queries_24h": 156,
  "total_queries_7d": 892,
  "error_rate_24h": 0.02,
  "uptime_seconds": 86400
}
```

---

## 6. TypeScript Type Definitions

```typescript
// ======== Settings Types ========

export interface SearchParamsOverride {
  match_count: number | null;
  rrf_k: number | null;
  qa_history_match_count: number | null;
}

export interface StageDefaultConfig {
  system_prompt_append: string | null;
  search_params: SearchParamsOverride;
}

export interface GlobalSettings {
  main_system_prompt: string;
  follow_up_context_prompt: string;
  qa_history_prompt: string;
  stage_defaults: StageDefaultConfig;
  default_match_count: number;
  max_match_count: number;
  enable_question_decomposition: boolean;
  enable_iterative_refinement: boolean;
  enable_qa_history_search: boolean;
  rrf_k_constant: number;
  qa_history_match_count: number;
  llm_model: string;
  llm_base_url: string;
  embedding_model: string;
  show_full_citations: boolean;
}

export interface SettingsResponse extends GlobalSettings {
  id: string;
  version: number;
  updated_at: string; // ISO 8601
}

export interface SettingsUpdateRequest {
  main_system_prompt?: string;
  follow_up_context_prompt?: string;
  qa_history_prompt?: string;
  stage_defaults?: Partial<StageDefaultConfig>;
  default_match_count?: number;
  max_match_count?: number;
  enable_question_decomposition?: boolean;
  enable_iterative_refinement?: boolean;
  enable_qa_history_search?: boolean;
  rrf_k_constant?: number;
  qa_history_match_count?: number;
  llm_model?: string;
  llm_base_url?: string;
  embedding_model?: string;
  show_full_citations?: boolean;
}

export interface SettingsVersion {
  version: number;
  changed_fields: string[];
  summary: string;
  created_at: string; // ISO 8601
}

export interface ParameterSuggestion {
  suggestion_id: string;
  parameter: string;
  current_value: number | string | boolean;
  suggested_value: number | string | boolean;
  confidence: number; // 0.0 - 1.0
  rationale: string;
}

export interface PromptTestRequest {
  prompt: string;
  test_question: string;
}

export interface PromptTestResponse {
  answer: string;
  latency_ms: number;
}

// ======== Workflow Types ========

export interface MetadataFieldDef {
  key: string;
  label: string;
  field_type: "text" | "number" | "date" | "select";
  required: boolean;
  options: string[] | null; // for "select" type
}

export interface TransitionCondition {
  type: string; // e.g. "all_questions_answered", "min_rating"
  params?: Record<string, unknown>;
}

export interface StageConfig {
  system_prompt_append: string | null;
  search_params: SearchParamsOverride;
  metadata_fields: MetadataFieldDef[];
  auto_advance: boolean;
}

export interface StageTransition {
  to_stage_id: string;
  label: string;
  condition: TransitionCondition | null;
}

export interface WorkflowStage {
  id: string;
  label: string;
  description: string;
  order: number;
  color: string; // hex
  config: StageConfig;
  transitions: StageTransition[];
}

export interface WorkflowTemplate {
  id: string;
  name: string;
  description: string;
  is_default: boolean;
  stages: WorkflowStage[];
  created_at: string; // ISO 8601
  updated_at: string; // ISO 8601
}

export interface WorkflowListItem {
  id: string;
  name: string;
  description: string;
  is_default: boolean;
  stage_count: number;
  created_at: string;
  updated_at: string;
}

// ======== Dashboard Types ========

export interface StageFunnelItem {
  stage_id: string;
  label: string;
  color: string;
  count: number;
  percentage: number;
}

export interface StageFunnelResponse {
  funnel: StageFunnelItem[];
  total_projects: number;
}

export interface QualityTrendPoint {
  date: string;
  good_count: number;
  bad_count: number;
  total_rated: number;
  good_ratio: number;
}

export interface QualityTrendResponse {
  trend: QualityTrendPoint[];
  period_days: number;
  granularity: "day" | "week" | "month";
}

export interface KBHealthData {
  total_documents: number;
  total_chunks: number;
  avg_chunks_per_doc: number;
  embedding_coverage: number; // 0.0 - 1.0
  last_ingestion: string | null;
  stale_document_count: number;
  stale_threshold_days: number;
}

export interface SystemMetricsData {
  avg_response_time_ms: number;
  avg_search_time_ms: number;
  total_queries_24h: number;
  total_queries_7d: number;
  error_rate_24h: number;
  uptime_seconds: number;
}
```

---

## 7. Seeding Strategy (`_seed_from_env`)

On first call to `SettingsService.get_current()`:

1. Query `app_settings` for `{type: "global_config"}`.
2. If not found, build a default document:
   ```python
   from src.prompts import MAIN_SYSTEM_PROMPT, FOLLOW_UP_CONTEXT_PROMPT, QA_HISTORY_PROMPT
   from src.settings import load_settings

   settings = load_settings()
   default_doc = {
       "type": "global_config",
       "version": 1,
       "main_system_prompt": MAIN_SYSTEM_PROMPT,
       "follow_up_context_prompt": FOLLOW_UP_CONTEXT_PROMPT,
       "qa_history_prompt": QA_HISTORY_PROMPT,
       "stage_defaults": {
           "system_prompt_append": None,
           "search_params": {
               "match_count": None,
               "rrf_k": None,
               "qa_history_match_count": None
           }
       },
       "default_match_count": settings.default_match_count,
       "max_match_count": settings.max_match_count,
       "enable_question_decomposition": settings.enable_question_decomposition,
       "enable_iterative_refinement": settings.enable_iterative_refinement,
       "enable_qa_history_search": True,
       "rrf_k_constant": 60,
       "qa_history_match_count": 3,
       "llm_model": settings.llm_model,
       "llm_base_url": settings.llm_base_url or "https://openrouter.ai/api/v1",
       "embedding_model": settings.embedding_model,
       "show_full_citations": settings.show_full_citations,
       "created_at": datetime.utcnow(),
       "updated_at": datetime.utcnow()
   }
   ```
3. Insert into MongoDB.
4. Also insert a version document (version 1) with `summary: "Initial seed from environment"`.

---

## 8. Cross-Cutting Concerns

### API Keys

- `llm_api_key` and `embedding_api_key` are **NEVER** stored in MongoDB.
- They remain in `.env` only, loaded via `src/settings.py`.
- The settings API does not accept or return API key fields.

### No In-Memory Cache

- Every API request fetches settings fresh from MongoDB.
- This ensures multi-instance deployments always read the latest config.
- Acceptable for the current scale.

### Prompt Fallback

- If MongoDB is unavailable when loading prompts, fall back to the constant values in `src/prompts.py`:
  - `MAIN_SYSTEM_PROMPT`
  - `FOLLOW_UP_CONTEXT_PROMPT`
  - `QA_HISTORY_PROMPT`
- `load_runtime_settings()` catches MongoDB errors and returns env-only values.

### Stage Color Palette

Default hex colors for stage visualization:

| Index | Hex       | Name        |
|-------|-----------|-------------|
| 0     | `#3B82F6` | Blue        |
| 1     | `#8B5CF6` | Purple      |
| 2     | `#F59E0B` | Amber       |
| 3     | `#10B981` | Emerald     |
| 4     | `#EF4444` | Red         |
| 5     | `#06B6D4` | Cyan        |
| 6     | `#EC4899` | Pink        |
| 7     | `#F97316` | Orange      |

### MongoDB ObjectId Serialization

All endpoints that return MongoDB documents must convert `_id` (ObjectId) to `id` (string). Use the same pattern as `SessionResponse`:
```python
id: str = Field(alias="_id", serialization_alias="_id")
```
Or convert manually before returning:
```python
doc["_id"] = str(doc["_id"])
```

### Error Response Format

All error responses use FastAPI's standard `HTTPException`:
```json
{
  "detail": "Human-readable error message"
}
```
Status codes: 404 for not found, 409 for conflicts, 422 for validation errors (automatic from Pydantic).
