# Frontend-Backend Contract

This document defines the API contract between the React frontend (`frontend/src/`) and the FastAPI backend (`src/api/`). It specifies all endpoints, request/response shapes, error handling, and data flow expectations.

## Overview

The frontend communicates with the backend via REST API calls using Axios. All API calls are centralized in `frontend/src/api/client.ts` and use TypeScript types defined in `frontend/src/api/types.ts` that correspond to Pydantic models in `src/api/models.py`.

**Base URL**: Configured via `VITE_API_BASE_URL` environment variable (defaults to `http://localhost:8000`)

**Content-Type**: `application/json` for most endpoints, `multipart/form-data` for file uploads

## API Client Architecture

### Request/Response Interceptors

The API client (`frontend/src/api/client.ts`) includes:
- **Request interceptor**: Logs all outgoing requests with request ID, method, URL, params, and data
- **Response interceptor**: Logs all responses with request ID, status, duration, and data size
- **Error handler**: Converts Axios errors to `APIError` instances with user-friendly messages
- **Retry logic**: Automatically retries retryable errors (network errors, 5xx, 503, 429) up to 3 times with 1-second delay

### Error Handling

All API errors are wrapped in `APIError` class (`frontend/src/api/types.ts`):
- **Type classification**: `network`, `validation`, `not_found`, `conflict`, `unauthorized`, `server`, `unknown`
- **User-friendly messages**: `getUserMessage()` provides readable error text
- **Retry detection**: `isRetryable()` determines if error should be retried

## API Endpoints

### Projects

#### `GET /api/projects`
List all projects.

**Request**: None (query params not used)

**Response**: `Project[]`
```typescript
interface Project {
  _id: string;
  name: string;
  company_info?: Record<string, any>;
  created_at: string;  // ISO datetime
  updated_at: string;  // ISO datetime
  stage: {
    key: string;
    updated_at: string;  // ISO datetime
  };
  stage_history?: Array<{
    at: string;  // ISO datetime
    from?: string | null;
    to: string;
    event: string;
    note?: string | null;
    by?: string | null;
  }>;
}
```

**Errors**:
- `500`: Server error
- Network errors (retryable)

**Frontend Usage**: `api.listProjects()` → `ProjectContext.listProjects()`

---

#### `POST /api/projects`
Create a new project.

**Request**: `CreateProjectRequest`
```typescript
interface CreateProjectRequest {
  name: string;  // 1-200 chars
}
```

**Response**: `Project` (same as GET response)

**Errors**:
- `400`: Validation error (name too short/long, empty)
- `500`: Server error

**Frontend Usage**: `api.createProject()` → `ProjectContext.createProject()`

---

#### `GET /api/projects/{project_id}`
Get a specific project by ID.

**Request**: Path parameter `project_id` (MongoDB ObjectId string)

**Response**: `Project`

**Errors**:
- `400`: Invalid ObjectId format
- `404`: Project not found
- `500`: Server error

**Frontend Usage**: `api.getProject()` → `ProjectContext.loadProject()`

---

#### `PUT /api/projects/{project_id}/stage`
Update project stage (transition, rollback, or force).

**Request**: `UpdateProjectStageRequest`
```typescript
interface UpdateProjectStageRequest {
  mode: "transition" | "rollback" | "force";
  event: string;  // 1-50 chars, transition event name
  to_stage: string;  // 1-80 chars, target stage key
  note?: string | null;  // Optional, max 500 chars
}
```

**Response**: `Project` (updated)

**Errors**:
- `400`: Invalid ObjectId, invalid mode, invalid transition (for mode="transition")
- `404`: Project not found
- `500`: Server error

**Frontend Usage**: `api.updateProjectStage()` → `ProjectContext.updateStage()`

---

#### `GET /api/projects/{project_id}/stage-options`
Get available stage transitions and rollback targets for a project.

**Request**: Path parameter `project_id`

**Response**:
```typescript
{
  next_actions: Array<{
    event: string;
    to: string;
    to_label: string;
  }>;
  rollback_targets: string[];  // Array of stage keys
}
```

**Errors**:
- `400`: Invalid ObjectId
- `404`: Project not found
- `500`: Server error

**Frontend Usage**: `api.getProjectStageOptions()` → Used by `StageWorkflowVisualization` component

---

#### `POST /api/projects/{project_id}/uploads`
Upload a document to a project.

**Request**: `multipart/form-data` with field `file` (File object)

**Response**:
```typescript
{
  project_id: string;
  document_id: string;
  title: string;
  chunks_created: number;
  errors: string[];  // Array of error messages (empty if successful)
}
```

**Errors**:
- `400`: Invalid ObjectId, invalid file format, file too large
- `404`: Project not found
- `500`: Server error, ingestion failure

**Frontend Usage**: `api.uploadProjectDocument()` → `ProjectContext.uploadDocument()`

---

### Sessions

#### `POST /api/sessions`
Create a new Q&A session.

**Request**: `CreateSessionRequest`
```typescript
interface CreateSessionRequest {
  name: string;  // 1-500 chars, session name
  user_role: "junior" | "senior";
  company_info?: string;  // Optional, max 5000 chars, free-form text
  project_id?: string | null;  // Optional MongoDB ObjectId
}
```

**Response**: `QASession`
```typescript
interface QASession {
  _id: string;
  session_name: string;
  user_role: "junior" | "senior";
  status: "active" | "draft" | "exported" | "approved" | null;
  outcome_status: "pending" | "successful" | "unsuccessful" | null;
  project_id?: string | null;
  created_at: string;  // ISO datetime
  updated_at: string;  // ISO datetime
  metadata?: {
    company_info?: {
      company_name?: string | null;
      industry?: string | null;
      activities?: string | null;
      context?: string | null;
    };
    round_number?: number;
    parent_session_id?: string | null;
    review_summary?: {
      verdict_counts?: Record<string, number>;
      missing_info?: string[];
      updated_at?: string;
    };
  };
}
```

**Errors**:
- `400`: Validation error (invalid user_role, empty name, invalid project_id)
- `404`: Project not found (if project_id provided)
- `500`: Server error

**Frontend Usage**: `api.createSession()` → `SessionContext.createSession()`

---

#### `GET /api/sessions`
List Q&A sessions.

**Request**: Query parameters
- `limit?: number` (default: 100, min: 1, max: 1000)
- `skip?: number` (default: 0, min: 0)

**Response**: `QASession[]`

**Errors**:
- `400`: Invalid query parameters
- `500`: Server error

**Frontend Usage**: `api.listSessions()` → `SessionContext.listSessions()`

---

#### `GET /api/sessions/{session_id}`
Get a specific session by ID.

**Request**: Path parameter `session_id` (MongoDB ObjectId string)

**Response**: `QASession`

**Errors**:
- `400`: Invalid ObjectId format
- `404`: Session not found
- `500`: Server error

**Frontend Usage**: `api.getSession()` → `SessionContext.loadSession()`, `SessionContext.refreshCurrentSession()`

---

#### `PUT /api/sessions/{session_id}/outcome`
Mark session outcome (successful/unsuccessful).

**Request**:
```typescript
{
  outcome: "successful" | "unsuccessful";
}
```

**Response**: `void` (204 No Content)

**Errors**:
- `400`: Invalid ObjectId, invalid outcome value
- `404`: Session not found
- `500`: Server error

**Frontend Usage**: `api.markSessionOutcome()` → `SessionContext.markOutcome()`

---

#### `POST /api/sessions/{session_id}/follow-up`
Create a follow-up session from an existing session.

**Request**: `FollowUpSessionRequest`
```typescript
interface FollowUpSessionRequest {
  new_questions: string[];  // 1-100 questions, each 1-10000 chars
}
```

**Response**: `QASession` (new follow-up session)

**Errors**:
- `400`: Invalid ObjectId, empty questions list, too many questions, invalid question format
- `404`: Parent session not found
- `500`: Server error

**Frontend Usage**: `api.createFollowUpSession()` → Used by `FollowUpSessionCreator` component

---

### Questions & Q&A Pairs

#### `POST /api/sessions/{session_id}/questions`
Process questions and generate answers.

**Request**: `ProcessQuestionsRequest`
```typescript
interface ProcessQuestionsRequest {
  questions: string[];  // 1-100 questions, each 1-10000 chars
  user_role?: "junior" | "senior";  // Defaults to session's user_role
  include_history?: boolean;  // Default: true, include Q&A history in search
}
```

**Response**: `ProcessQuestionsResponse`
```typescript
interface ProcessQuestionsResponse {
  questions_processed: number;
  qa_pairs: QAPair[];
}
```

**QAPair Structure**:
```typescript
interface QAPair {
  _id: string;
  session_id: string;
  question: string;
  original_answer: string;
  edited_answer?: string;
  final_answer: string;  // edited_answer if exists, else original_answer
  rating_good?: boolean | null;  // null = not reviewed
  rated_at?: string | null;  // ISO datetime
  rated_by?: string | null;
  was_edited?: boolean;
  edited_at?: string | null;  // ISO datetime
  review?: {
    verdict: "good" | "needs_info" | "risk";
    summary: string;
    missing_info?: string[];
    confidence?: number;
  } | null;
  citations: Citation[];
  question_index: number;  // 0-based index
  outcome_status: "pending" | "successful" | "unsuccessful";
  created_at: string;  // ISO datetime
  updated_at: string;  // ISO datetime
}

interface Citation {
  document_id: string;
  document_title: string;
  citation_number: number;
  chunk_id?: string;
}
```

**Errors**:
- `400`: Invalid ObjectId, validation errors (empty questions, too many, invalid user_role)
- `404`: Session not found
- `503`: No documents in database (ServiceUnavailableError)
- `500`: Server error, agent processing failure

**Frontend Usage**: `api.processQuestions()` → `QABlocksContext.processQuestions()` → `useQuestionProcessing.processQuestionsText()`

**Processing Flow**:
1. Frontend extracts questions from text input (handles numbered lists, newlines)
2. Calls API with question array
3. Backend processes questions sequentially via RAG agent
4. Returns Q&A pairs with citations
5. Frontend updates QABlocksContext state and refreshes session metadata

---

#### `GET /api/sessions/{session_id}/qa-pairs`
Get all Q&A pairs for a session.

**Request**: Path parameter `session_id`

**Response**: `QAPair[]`

**Errors**:
- `400`: Invalid ObjectId
- `404`: Session not found
- `500`: Server error

**Frontend Usage**: `api.getQAPairs()` → `QABlocksContext.loadQAPairs()`

**Note**: Called automatically when session changes (via `useEffect` in `QABlockList`)

---

#### `PUT /api/qa-pairs/{qa_pair_id}`
Update a Q&A pair's edited answer.

**Request**: `UpdateAnswerRequest`
```typescript
interface UpdateAnswerRequest {
  edited_answer: string;  // 1-50000 chars
}
```

**Response**: `void` (204 No Content)

**Errors**:
- `400`: Invalid ObjectId, validation error (empty answer, too long)
- `404`: Q&A pair not found
- `500`: Server error

**Frontend Usage**: `api.updateAnswer()` → `QABlocksContext.updateAnswer()`

**Note**: Only available to senior users. Frontend optimistically updates UI, then syncs with backend.

---

#### `PUT /api/qa-pairs/{qa_pair_id}/rating`
Update a Q&A pair's rating (good/bad/clear).

**Request**: `UpdateQAPairRatingRequest`
```typescript
interface UpdateQAPairRatingRequest {
  rating_good: boolean | null;  // true=good, false=bad, null=clear rating
}
```

**Response**: `void` (204 No Content)

**Errors**:
- `400`: Invalid ObjectId
- `404`: Q&A pair not found
- `500`: Server error

**Frontend Usage**: `api.updateQAPairRating()` → `QABlocksContext.updateRating()`

**Note**: Only available to senior users. Frontend uses optimistic updates with rollback on error.

---

### Export

#### `POST /api/sessions/{session_id}/export`
Export session Q&A pairs to file.

**Request**: Query parameter
- `format: "markdown" | "pdf" | "docx"`

**Response**: `Blob` (file download)

**Errors**:
- `400`: Invalid ObjectId, invalid format
- `404`: Session not found
- `500`: Server error, export generation failure

**Frontend Usage**: `api.exportSession()` → Used by `ExportButton` component

**Note**: Response is a binary blob. Frontend creates download link and triggers download.

---

## Data Flow Patterns

### Context-Based State Management

The frontend uses React Context API for state management:

1. **ProjectContext** (`frontend/src/contexts/ProjectContext.tsx`):
   - Manages `currentProject` state
   - Provides `loadProject()`, `createProject()`, `updateStage()`, `uploadDocument()`
   - Handles loading/error states

2. **SessionContext** (`frontend/src/contexts/SessionContext.tsx`):
   - Manages `currentSession` and `userRole` state
   - Provides `createSession()`, `loadSession()`, `refreshCurrentSession()`, `markOutcome()`
   - Handles loading/error states

3. **QABlocksContext** (`frontend/src/contexts/QABlocksContext.tsx`):
   - Manages `qaPairs` array state
   - Provides `processQuestions()`, `updateAnswer()`, `updateRating()`, `loadQAPairs()`
   - Depends on `SessionContext` for current session
   - Automatically refreshes session metadata after processing questions

### Component Hierarchy

```
App.tsx
├── ProjectProvider (outermost)
│   ├── SessionProvider
│   │   ├── QABlocksProvider
│   │   │   └── Layout
│   │   │       ├── Sidebar (ProjectSelector, SessionSelector, etc.)
│   │   │       └── Main Content
│   │   │           ├── QuestionInput
│   │   │           └── QABlockList
│   │   │               └── QABlock (for each Q&A pair)
```

### Question Processing Flow

1. User enters questions in `QuestionInput` component
2. `useQuestionProcessing` hook extracts questions from text (handles numbered lists)
3. `QABlocksContext.processQuestions()` called with question array
4. API call to `POST /api/sessions/{session_id}/questions`
5. Backend processes questions via RAG agent
6. Response contains Q&A pairs with citations
7. Frontend updates `qaPairs` state (merges with existing, sorts by `question_index`)
8. `QABlocksContext` refreshes session metadata (for review summary updates)
9. `QABlockList` re-renders with new Q&A pairs

### Optimistic Updates

The frontend uses optimistic updates for:
- **Answer editing**: UI updates immediately, then syncs with backend
- **Rating updates**: UI updates immediately, rolls back on error

### Error Handling

- **Context-level**: Each context maintains `error` state and `clearError()` method
- **Component-level**: Components display errors via `ErrorAlert` component
- **API-level**: All errors wrapped in `APIError` with user-friendly messages
- **Retry logic**: Automatic retry for network/server errors (up to 3 attempts)

## Type Mapping

### Frontend Types → Backend Models

| Frontend Type | Backend Model | Notes |
|--------------|---------------|-------|
| `QASession` | `SessionResponse` | `_id` mapped to `id` in backend |
| `QAPair` | `QAPair` | Field normalization handled in backend |
| `Project` | `ProjectResponse` | `_id` mapped to `id` in backend |
| `Citation` | `Citation` | `document_title` normalized from `title` |

### Date Handling

- **Backend**: Returns ISO datetime strings (`created_at`, `updated_at`)
- **Frontend**: Uses strings directly, formats for display using `date-fns` library

### Null vs Undefined

- **Backend**: Uses `Optional[T]` which maps to `null` in JSON
- **Frontend**: Uses `T | null` or `T | undefined` depending on context
- **API Contract**: Prefers `null` for optional fields (matches backend)

## Request/Response Headers

### Request Headers
- `Content-Type: application/json` (for JSON requests)
- `Content-Type: multipart/form-data` (for file uploads)
- `X-Request-ID`: Generated by frontend interceptor (for logging)

### Response Headers
- `X-Request-ID`: Echoed from request (for request tracing)
- `Content-Type: application/json` (for JSON responses)
- `Content-Type: application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `text/markdown` (for exports)

## CORS Configuration

Backend allows all origins (`allow_origins=["*"]`). For production, configure specific origins.

## Environment Variables

**Frontend** (`frontend/.env`):
- `VITE_API_BASE_URL`: Backend API base URL (default: `http://localhost:8000`)

**Backend**: See `src/settings.py` for full configuration.

## Testing Considerations

- **Mock API**: Frontend can be tested with mocked API client
- **Error Scenarios**: Test network errors, validation errors, 404s, 500s
- **Loading States**: Test loading indicators during API calls
- **Optimistic Updates**: Test rollback behavior on error
- **Session Refresh**: Test automatic session metadata refresh after question processing
