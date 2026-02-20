"""Ingestion tracking and monitoring endpoints."""

import asyncio
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ConfigDict

from src.api.validators import validate_object_id
from src.api.exceptions import NotFoundError
from src.settings import load_settings
from src.services.ingestion_tracker import (
    IngestionTracker,
    IngestionJob,
    IngestionJobFilter,
    IngestionStatistics,
    IngestionStage,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ingestion", tags=["ingestion"])


# =============================================================================
# Response Models
# =============================================================================


class IngestionJobResponse(BaseModel):
    """Response model for a single ingestion job."""
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id", serialization_alias="_id")
    document_id: Optional[str] = None
    project_id: Optional[str] = None
    filename: str
    file_size_bytes: int = 0
    content_type: Optional[str] = None
    status: str
    current_stage: str
    progress_pct: int = 0
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None
    statistics: IngestionStatistics
    metadata_extracted: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class IngestionJobListResponse(BaseModel):
    """Response model for paginated ingestion job list."""
    jobs: List[IngestionJobResponse]
    total: int
    limit: int
    skip: int
    has_more: bool


class IngestionAggregateStats(BaseModel):
    """Aggregate statistics for ingestion jobs."""
    total_jobs: int = 0
    by_status: Dict[str, int] = Field(default_factory=dict)
    total_chunks_created: int = 0
    total_tokens_processed: int = 0
    avg_duration_ms: float = 0.0


class IngestionStatsResponse(BaseModel):
    """Response model for ingestion statistics."""
    stats: IngestionAggregateStats
    project_id: Optional[str] = None


# =============================================================================
# Helper Functions
# =============================================================================


def job_to_response(job: IngestionJob) -> IngestionJobResponse:
    """Convert IngestionJob model to response model."""
    return IngestionJobResponse(
        _id=job.id,
        document_id=job.document_id,
        project_id=job.project_id,
        filename=job.filename,
        file_size_bytes=job.file_size_bytes,
        content_type=job.content_type,
        status=job.status,
        current_stage=job.current_stage.value if isinstance(job.current_stage, IngestionStage) else job.current_stage,
        progress_pct=job.progress_pct,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        duration_ms=job.duration_ms,
        statistics=job.statistics,
        metadata_extracted=job.metadata_extracted,
        warnings=job.warnings,
        errors=job.errors,
    )


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/jobs", response_model=IngestionJobListResponse)
async def list_ingestion_jobs(
    status: Optional[str] = Query(
        None,
        description="Filter by status: pending, in_progress, success, partial, failed",
    ),
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    filename_contains: Optional[str] = Query(
        None, description="Filter by filename (partial match)"
    ),
    created_after: Optional[datetime] = Query(
        None, description="Filter jobs created after this datetime"
    ),
    created_before: Optional[datetime] = Query(
        None, description="Filter jobs created before this datetime"
    ),
    limit: int = Query(50, ge=1, le=100, description="Maximum jobs to return"),
    skip: int = Query(0, ge=0, description="Number of jobs to skip"),
):
    """
    List ingestion jobs with optional filtering and pagination.

    Returns a paginated list of ingestion jobs sorted by creation date (newest first).

    Filters:
    - status: Filter by job status (pending, in_progress, success, partial, failed)
    - project_id: Filter by project ID
    - filename_contains: Filter by filename (partial case-insensitive match)
    - created_after/created_before: Filter by creation date range
    """
    settings = load_settings()

    # Validate project_id if provided
    if project_id:
        validate_object_id(project_id, "Project")

    tracker = IngestionTracker(settings)
    await tracker.initialize()

    try:
        # Build filter
        filters = IngestionJobFilter(
            status=status,
            project_id=project_id,
            filename_contains=filename_contains,
            created_after=created_after,
            created_before=created_before,
        )

        # Get total count
        total = await tracker.get_job_count(filters)

        # Get jobs
        jobs = await tracker.list_jobs(filters=filters, limit=limit, skip=skip)

        # Convert to response models
        job_responses = [job_to_response(job) for job in jobs]

        has_more = skip + len(job_responses) < total

        return IngestionJobListResponse(
            jobs=job_responses,
            total=total,
            limit=limit,
            skip=skip,
            has_more=has_more,
        )

    finally:
        await tracker.cleanup()


@router.get("/jobs/{job_id}", response_model=IngestionJobResponse)
async def get_ingestion_job(job_id: str):
    """
    Get details of a single ingestion job by ID.

    Returns the full job record including progress history, statistics,
    extracted metadata, warnings, and errors.
    """
    validate_object_id(job_id, "Ingestion Job")

    settings = load_settings()
    tracker = IngestionTracker(settings)
    await tracker.initialize()

    try:
        job = await tracker.get_job(job_id)

        if not job:
            raise NotFoundError("Ingestion Job", job_id)

        return job_to_response(job)

    finally:
        await tracker.cleanup()


@router.get("/jobs/{job_id}/status")
async def get_ingestion_job_status_stream(job_id: str):
    """
    Stream real-time status updates for an ingestion job via Server-Sent Events (SSE).

    This endpoint opens a persistent connection and streams progress updates
    as the ingestion job progresses through its stages. The stream closes
    automatically when the job reaches a terminal state (success, partial, or failed).

    Event format:
    ```
    data: {"id": "...", "status": "in_progress", "current_stage": "chunking", "progress_pct": 45, ...}
    ```

    Usage:
    ```javascript
    const eventSource = new EventSource('/api/ingestion/jobs/{job_id}/status');
    eventSource.onmessage = (event) => {
        const job = JSON.parse(event.data);
        console.log(`Progress: ${job.progress_pct}%`);
        if (['success', 'partial', 'failed'].includes(job.status)) {
            eventSource.close();
        }
    };
    ```
    """
    validate_object_id(job_id, "Ingestion Job")

    settings = load_settings()
    tracker = IngestionTracker(settings)
    await tracker.initialize()

    # Check if job exists before starting stream
    job = await tracker.get_job(job_id)
    if not job:
        await tracker.cleanup()
        raise NotFoundError("Ingestion Job", job_id)

    async def event_stream():
        """Generate SSE events for job status updates."""
        try:
            terminal_states = {"success", "partial", "failed"}
            poll_interval = 0.5  # 500ms between polls
            max_polls = 600  # 5 minutes maximum (600 * 0.5s)
            poll_count = 0

            while poll_count < max_polls:
                job = await tracker.get_job(job_id)

                if not job:
                    # Job was deleted - send error and close
                    yield f"data: {{\"error\": \"Job not found\"}}\n\n"
                    break

                # Convert job to response and serialize
                response = job_to_response(job)
                data = response.model_dump_json(by_alias=True)
                yield f"data: {data}\n\n"

                # Check if job has reached terminal state
                if job.status in terminal_states:
                    break

                poll_count += 1
                await asyncio.sleep(poll_interval)

            # If we hit the max polls, send a final timeout message
            if poll_count >= max_polls:
                yield f"data: {{\"error\": \"Status stream timeout\", \"job_id\": \"{job_id}\"}}\n\n"

        finally:
            await tracker.cleanup()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.get("/stats", response_model=IngestionStatsResponse)
async def get_ingestion_stats(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
):
    """
    Get aggregate statistics for ingestion jobs.

    Returns overall statistics including:
    - Total number of jobs
    - Jobs by status (success, failed, etc.)
    - Total chunks created
    - Total tokens processed
    - Average processing duration

    Optionally filter by project_id to get project-specific stats.
    """
    settings = load_settings()

    # Validate project_id if provided
    if project_id:
        validate_object_id(project_id, "Project")

    tracker = IngestionTracker(settings)
    await tracker.initialize()

    try:
        stats = await tracker.get_aggregate_stats(project_id=project_id)

        return IngestionStatsResponse(
            stats=IngestionAggregateStats(
                total_jobs=stats.get("total_jobs", 0),
                by_status=stats.get("by_status", {}),
                total_chunks_created=stats.get("total_chunks_created", 0),
                total_tokens_processed=stats.get("total_tokens_processed", 0),
                avg_duration_ms=stats.get("avg_duration_ms", 0.0),
            ),
            project_id=project_id,
        )

    finally:
        await tracker.cleanup()


@router.delete("/jobs/{job_id}", status_code=204)
async def delete_ingestion_job(job_id: str):
    """
    Delete an ingestion job record.

    This only deletes the job tracking record, not the document or chunks
    that were created during ingestion. Use this to clean up old job records.

    Note: This does NOT delete the ingested document or its chunks.
    To delete the document, use DELETE /api/documents/{document_id}.
    """
    validate_object_id(job_id, "Ingestion Job")

    settings = load_settings()
    tracker = IngestionTracker(settings)
    await tracker.initialize()

    try:
        # Check if job exists
        job = await tracker.get_job(job_id)
        if not job:
            raise NotFoundError("Ingestion Job", job_id)

        # Delete the job
        from bson import ObjectId
        await tracker.collection.delete_one({"_id": ObjectId(job_id)})

        logger.info(f"Deleted ingestion job: {job_id}")

        return None

    finally:
        await tracker.cleanup()
