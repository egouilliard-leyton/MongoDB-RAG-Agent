# CR: Document Ingestion Dashboard & Standalone Upload

**Created:** 2026-01-23
**Status:** Completed
**Completed:** 2026-01-23
**Scope:** Medium-Large
**Priority:** P1-High

## Summary

Add a comprehensive document ingestion UI with standalone uploads (no project required), real-time progress tracking, post-ingestion summaries, and historical ingestion logs. Also verify MongoDB Atlas vector index auto-sync behavior.

## Problem Statement

The current document upload system has three key limitations:

1. **No Visibility**: After uploading a document, users have no insight into what happened during ingestion - no chunk counts, no metadata extraction results, no error details
2. **Project Dependency**: Document uploads require an existing project context. Users cannot ingest standalone documents for exploration or general knowledge base building
3. **Index Uncertainty**: After uploading new documents, it's unclear whether the vector search index is updated and new documents are searchable

These gaps make the system difficult to use in practice and reduce confidence in the ingestion pipeline.

## Current Behavior

**Existing Upload Flow:**
1. User creates a project via ProjectCreator component
2. User navigates to project and uses ProjectUploads component
3. File is uploaded via `POST /api/projects/{project_id}/uploads`
4. Backend saves file, runs ingestion pipeline, returns basic result
5. User sees only: "Upload successful" or error message
6. No visibility into chunks created, metadata extracted, or ingestion quality

**Current API Response:**
```json
{
  "project_id": "...",
  "document_id": "...",
  "title": "...",
  "chunks_created": 10,
  "errors": []
}
```

## Desired Behavior

### 1. Standalone Document Ingestion

- New "Documents" section in UI (separate from Projects)
- Upload documents without project context
- Option to later associate documents with projects
- Same ingestion pipeline but with `project_id=None`

### 2. Real-Time Progress Tracking

During upload, show live status:
```
[=====>          ] 35%
✓ File uploaded
✓ Converting to markdown...
◉ Extracting metadata
○ Chunking document
○ Generating embeddings
○ Storing in database
```

### 3. Post-Ingestion Summary

After upload completes, display comprehensive results:
```
Document Ingested Successfully

📄 Title: "Tax Interpretation 2024-0113-IPTPP"
📊 Statistics:
   - Chunks created: 12
   - Total tokens: 4,832
   - Avg chunk size: 402 tokens

📋 Metadata Extracted:
   - Document Type: Tax Interpretation
   - ID: 0113-KDIPT3-2.4011.456.2024.2.AP
   - Signature: 0113-KDIPT3-2
   - Date: 2024-03-15
   - Outcome: Positive
   - Keywords: VAT, deduction, input tax

⚠️ Warnings:
   - Section "Przepis" not found (using fallback chunking)
```

### 4. Ingestion History Log

New collection `ingestion_logs` tracking all uploads:
```json
{
  "_id": "...",
  "document_id": "...",
  "project_id": null,
  "filename": "document.pdf",
  "status": "success",
  "started_at": "2026-01-23T10:00:00Z",
  "completed_at": "2026-01-23T10:00:05Z",
  "duration_ms": 5000,
  "statistics": {
    "chunks_created": 12,
    "total_tokens": 4832,
    "sections_found": 5,
    "sections_expected": 7
  },
  "metadata_extracted": {
    "document_type": "tax_interpretation",
    "id_informacji": "0113-KDIPT3-2.4011.456.2024.2.AP",
    "interpretation_stance": "positive"
  },
  "warnings": ["Section 'Przepis' not found"],
  "errors": []
}
```

UI shows filterable/sortable list of all ingestion attempts.

### 5. Index Verification

- After ingestion, verify document is searchable
- Add health check endpoint: `GET /api/system/index-status`
- Document MongoDB Atlas index sync behavior
- Add retry mechanism if document not immediately searchable

## Affected Areas

| File/Module | Type of Change | Description |
|-------------|----------------|-------------|
| `src/api/routes/documents.py` | Create | New standalone document upload routes |
| `src/api/routes/ingestion.py` | Create | Ingestion history and status routes |
| `src/api/routes/system.py` | Create | System health and index status routes |
| `src/services/ingestion_tracker.py` | Create | Service to track and log ingestion jobs |
| `src/ingestion/ingest.py` | Modify | Add progress callbacks and detailed result tracking |
| `src/api/main.py` | Modify | Register new routers |
| `src/api/models.py` | Modify | Add new Pydantic models for ingestion tracking |
| `frontend/src/components/DocumentUploader.tsx` | Create | Standalone document upload with progress |
| `frontend/src/components/IngestionDashboard.tsx` | Create | Ingestion history and statistics view |
| `frontend/src/components/IngestionProgress.tsx` | Create | Real-time progress component |
| `frontend/src/components/IngestionResult.tsx` | Create | Post-ingestion summary display |
| `frontend/src/api/client.ts` | Modify | Add new API methods |
| `frontend/src/api/types.ts` | Modify | Add TypeScript types for ingestion |
| `frontend/src/App.tsx` | Modify | Add Documents/Ingestion routes |
| `frontend/src/contexts/IngestionContext.tsx` | Create | State management for ingestion |

## Implementation Approach

### Backend Architecture

**New Routes:**
```
POST /api/documents/upload          # Standalone upload (no project)
GET  /api/documents                  # List all documents
GET  /api/documents/{id}             # Get document details

POST /api/ingestion/upload           # Upload with detailed tracking
GET  /api/ingestion/jobs             # List all ingestion jobs
GET  /api/ingestion/jobs/{id}        # Get job details
GET  /api/ingestion/jobs/{id}/status # Real-time status (SSE)

GET  /api/system/health              # System health check
GET  /api/system/index-status        # Vector index sync status
```

**Progress Tracking via Server-Sent Events (SSE):**
```python
@router.get("/ingestion/jobs/{job_id}/status")
async def ingestion_status_stream(job_id: str):
    async def event_generator():
        while True:
            status = await tracker.get_status(job_id)
            yield f"data: {status.model_dump_json()}\n\n"
            if status.completed:
                break
            await asyncio.sleep(0.5)
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

**Ingestion Pipeline Enhancement:**
```python
class IngestionProgress:
    stage: Literal["uploading", "converting", "extracting_metadata",
                   "chunking", "embedding", "storing", "verifying", "complete"]
    progress_pct: int
    message: str

class IngestionResult:
    document_id: str
    status: Literal["success", "partial", "failed"]
    statistics: IngestionStatistics
    metadata_extracted: dict[str, Any]
    warnings: list[str]
    errors: list[str]
```

### Frontend Architecture

**New Pages/Routes:**
- `/documents` - Document management (list, upload, view)
- `/ingestion` - Ingestion dashboard (history, statistics)

**Component Hierarchy:**
```
DocumentUploader
├── FileDropzone
├── IngestionProgress (during upload)
└── IngestionResult (after completion)

IngestionDashboard
├── IngestionFilters (date range, status, etc.)
├── IngestionStats (aggregate statistics)
└── IngestionJobList
    └── IngestionJobCard (per job)
```

### Key Changes

1. **IngestionTracker Service**: Manages ingestion job state, stores to MongoDB `ingestion_logs` collection, provides status queries
2. **Enhanced Ingestion Pipeline**: Add callback system for progress updates at each stage
3. **SSE Endpoint**: Stream real-time progress to frontend
4. **Index Verification**: After storing chunks, perform test vector search to confirm indexing
5. **Standalone Upload Route**: `POST /api/documents/upload` with no project requirement
6. **Frontend Dashboard**: React components for upload, progress, results, and history

## Dependencies

- [ ] MongoDB collection `ingestion_logs` will be created automatically on first write
- [ ] No schema migrations needed - MongoDB is schema-less
- [ ] SSE requires proper CORS configuration for streaming
- [ ] Frontend needs EventSource polyfill if supporting older browsers (optional)

## Breaking Changes

None expected. This is additive functionality:
- Existing `/api/projects/{id}/uploads` endpoint unchanged
- Existing ProjectUploads component unchanged
- New routes and components are additions

## Testing Plan

### Unit Tests
- [ ] IngestionTracker service: job creation, status updates, persistence
- [ ] Progress callback system in ingestion pipeline
- [ ] Ingestion result model validation
- [ ] Index verification logic

### Integration Tests
- [ ] End-to-end standalone upload flow
- [ ] SSE progress streaming
- [ ] MongoDB ingestion_logs persistence
- [ ] Vector search finds newly ingested document

### Manual Testing
- [ ] Upload PDF without project - verify success
- [ ] Watch real-time progress during upload
- [ ] Verify post-ingestion summary shows all metadata
- [ ] Check ingestion history displays all past uploads
- [ ] Search for content in newly uploaded document
- [ ] Upload invalid file - verify error handling
- [ ] Upload very large document - verify progress tracking

## Rollback Plan

All changes are additive:
1. Remove new routes from `main.py`
2. Remove new components from `App.tsx`
3. Delete new files (routes, services, components)
4. Existing functionality continues working

## Success Criteria

- [ ] Can upload document without creating a project first
- [ ] Real-time progress shown during upload (stages visible)
- [ ] Post-upload shows: chunks created, tokens, metadata extracted
- [ ] Ingestion history page shows all past uploads
- [ ] Can filter/sort ingestion history by date, status
- [ ] Newly uploaded documents appear in search results
- [ ] All tests pass
- [ ] No regressions in existing project upload functionality

---

## Task List

```json
[
  {
    "category": "setup",
    "description": "Create IngestionTracker service and models",
    "steps": [
      "Create src/services/ingestion_tracker.py with IngestionTracker class",
      "Define Pydantic models: IngestionJob, IngestionProgress, IngestionResult, IngestionStatistics",
      "Implement job lifecycle: create_job, update_status, complete_job, get_job",
      "Add MongoDB operations for ingestion_logs collection"
    ],
    "passes": true
  },
  {
    "category": "setup",
    "description": "Enhance ingestion pipeline with progress callbacks",
    "steps": [
      "Add ProgressCallback protocol to ingestion pipeline",
      "Emit progress events at each stage (convert, metadata, chunk, embed, store)",
      "Capture detailed statistics during processing",
      "Return IngestionResult instead of basic dict"
    ],
    "passes": true
  },
  {
    "category": "feature",
    "description": "Create standalone document upload API routes",
    "steps": [
      "Create src/api/routes/documents.py with upload endpoint",
      "Implement POST /api/documents/upload (no project required)",
      "Implement GET /api/documents (list with pagination)",
      "Implement GET /api/documents/{id} (single document)",
      "Register router in main.py"
    ],
    "passes": true
  },
  {
    "category": "feature",
    "description": "Create ingestion tracking API routes",
    "steps": [
      "Create src/api/routes/ingestion.py",
      "Implement GET /api/ingestion/jobs (list with filters)",
      "Implement GET /api/ingestion/jobs/{id} (job details)",
      "Implement GET /api/ingestion/jobs/{id}/status as SSE stream",
      "Register router in main.py"
    ],
    "passes": true
  },
  {
    "category": "feature",
    "description": "Create system health and index status API",
    "steps": [
      "Create src/api/routes/system.py",
      "Implement GET /api/system/health (database connectivity)",
      "Implement GET /api/system/index-status (vector index info)",
      "Add verification: search for known document to confirm index",
      "Register router in main.py"
    ],
    "passes": true
  },
  {
    "category": "setup",
    "description": "Add TypeScript types for ingestion",
    "steps": [
      "Define IngestionJob, IngestionProgress, IngestionResult types",
      "Define IngestionStatistics and metadata types",
      "Export all types from api/types.ts"
    ],
    "passes": true
  },
  {
    "category": "setup",
    "description": "Add API client methods for ingestion",
    "steps": [
      "Add uploadDocument(file) method for standalone upload",
      "Add getIngestionJobs(filters) method",
      "Add getIngestionJob(id) method",
      "Add subscribeToIngestionStatus(id) SSE method",
      "Add getDocuments(filters) method"
    ],
    "passes": true
  },
  {
    "category": "feature",
    "description": "Create IngestionContext for state management",
    "steps": [
      "Create frontend/src/contexts/IngestionContext.tsx",
      "Manage current upload state and progress",
      "Manage ingestion history cache",
      "Handle SSE subscription lifecycle"
    ],
    "passes": true
  },
  {
    "category": "feature",
    "description": "Create DocumentUploader component",
    "steps": [
      "Create file dropzone with drag-and-drop support",
      "Show file validation (type, size)",
      "Integrate with IngestionContext for upload",
      "Show IngestionProgress during upload",
      "Show IngestionResult after completion"
    ],
    "passes": true
  },
  {
    "category": "feature",
    "description": "Create IngestionProgress component",
    "steps": [
      "Display progress bar with percentage",
      "Show current stage with icons",
      "List completed stages with checkmarks",
      "Handle SSE updates from backend"
    ],
    "passes": true
  },
  {
    "category": "feature",
    "description": "Create IngestionResult component",
    "steps": [
      "Display document title and basic info",
      "Show statistics: chunks, tokens, sections",
      "Display extracted metadata in formatted view",
      "Show warnings/errors if any",
      "Add 'View Document' and 'Upload Another' actions"
    ],
    "passes": true
  },
  {
    "category": "feature",
    "description": "Create IngestionDashboard component",
    "steps": [
      "Create dashboard layout with filters sidebar",
      "Add date range filter, status filter",
      "Show aggregate statistics (total docs, success rate)",
      "Display paginated list of ingestion jobs",
      "Add click-through to job details"
    ],
    "passes": true
  },
  {
    "category": "integration",
    "description": "Add routes to App.tsx and navigation",
    "steps": [
      "Add /documents route with DocumentUploader",
      "Add /ingestion route with IngestionDashboard",
      "Update navigation to include new sections",
      "Wrap with IngestionProvider"
    ],
    "passes": true
  },
  {
    "category": "test",
    "description": "Write backend unit tests",
    "steps": [
      "Test IngestionTracker job lifecycle",
      "Test progress callback integration",
      "Test ingestion result model validation",
      "Test document routes with mocked ingestion"
    ],
    "passes": true
  },
  {
    "category": "test",
    "description": "Write integration tests",
    "steps": [
      "Test end-to-end standalone upload",
      "Test SSE progress streaming",
      "Test ingestion history persistence",
      "Test vector search finds new documents"
    ],
    "passes": true
  },
  {
    "category": "test",
    "description": "Verify MongoDB index auto-sync",
    "steps": [
      "Document current index configuration",
      "Upload test document and immediately search",
      "Measure time until document appears in search",
      "Add delay or retry if needed in verification",
      "Document findings in code comments"
    ],
    "passes": true
  }
]
```

---

## Implementation Notes

### MongoDB Atlas Vector Index Behavior

MongoDB Atlas Vector Search indexes update automatically when documents are inserted into the indexed collection. The sync is near-real-time but not instantaneous. Based on MongoDB documentation:

- New documents typically appear in search results within seconds
- No manual index refresh is needed
- For verification, implement a retry mechanism: after storing chunks, perform a test search with a small delay

**Recommended approach:**
```python
async def verify_document_indexed(document_id: str, max_retries: int = 3) -> bool:
    for attempt in range(max_retries):
        result = await chunks_collection.aggregate([
            {"$vectorSearch": {..., "filter": {"document_id": document_id}}},
            {"$limit": 1}
        ]).to_list(length=1)
        if result:
            return True
        await asyncio.sleep(1)  # Wait before retry
    return False
```

### SSE Implementation Pattern

Use FastAPI's StreamingResponse with async generators:

```python
from fastapi.responses import StreamingResponse

@router.get("/ingestion/jobs/{job_id}/status")
async def ingestion_status(job_id: str):
    async def event_stream():
        while True:
            job = await tracker.get_job(job_id)
            data = job.model_dump_json()
            yield f"data: {data}\n\n"
            if job.status in ("success", "failed"):
                break
            await asyncio.sleep(0.5)
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )
```

### Frontend SSE Handling

```typescript
const subscribeToProgress = (jobId: string, onProgress: (p: IngestionProgress) => void) => {
  const eventSource = new EventSource(`/api/ingestion/jobs/${jobId}/status`);
  eventSource.onmessage = (event) => {
    const progress = JSON.parse(event.data);
    onProgress(progress);
    if (progress.status === 'success' || progress.status === 'failed') {
      eventSource.close();
    }
  };
  return () => eventSource.close();
};
```

### File Size Considerations

For large files (>10MB):
- Show upload progress separately from ingestion progress
- Consider chunked upload for very large files (future enhancement)
- Set appropriate timeout on server (currently handled by FastAPI defaults)

## References

- [MongoDB Atlas Vector Search Docs](https://www.mongodb.com/docs/atlas/atlas-search/vector-search/)
- [FastAPI SSE](https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse)
- [React EventSource Hooks](https://developer.mozilla.org/en-US/docs/Web/API/EventSource)
- Current implementation: `src/ingestion/ingest.py`, `src/api/routes/projects.py`
