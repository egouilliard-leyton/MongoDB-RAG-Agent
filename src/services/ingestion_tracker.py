"""Ingestion tracking service for monitoring document ingestion jobs."""

import logging
from typing import Optional, Dict, List, Any, Literal
from datetime import datetime
from enum import Enum
from bson import ObjectId
from pymongo import AsyncMongoClient
from pydantic import BaseModel, Field, ConfigDict

from src.settings import Settings

logger = logging.getLogger(__name__)


# =============================================================================
# Pydantic Models for Ingestion Tracking
# =============================================================================


class IngestionStage(str, Enum):
    """Stages in the ingestion pipeline."""
    UPLOADING = "uploading"
    CONVERTING = "converting"
    EXTRACTING_METADATA = "extracting_metadata"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    STORING = "storing"
    VERIFYING = "verifying"
    COMPLETE = "complete"
    FAILED = "failed"


class IngestionStatistics(BaseModel):
    """Statistics collected during ingestion."""
    chunks_created: int = 0
    total_tokens: int = 0
    avg_chunk_tokens: float = 0.0
    sections_found: int = 0
    sections_expected: int = 0
    file_size_bytes: int = 0
    processing_time_ms: float = 0.0


class IngestionProgress(BaseModel):
    """Real-time progress update for an ingestion job."""
    stage: IngestionStage
    progress_pct: int = Field(ge=0, le=100)
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class IngestionResult(BaseModel):
    """Final result of an ingestion job."""
    document_id: Optional[str] = None
    status: Literal["success", "partial", "failed"]
    statistics: IngestionStatistics
    metadata_extracted: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class IngestionJob(BaseModel):
    """Complete ingestion job record."""
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id", serialization_alias="_id")
    document_id: Optional[str] = None
    project_id: Optional[str] = None
    filename: str
    file_size_bytes: int = 0
    content_type: Optional[str] = None

    # Status tracking
    status: Literal["pending", "in_progress", "success", "partial", "failed"] = "pending"
    current_stage: IngestionStage = IngestionStage.UPLOADING
    progress_pct: int = 0

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None

    # Results
    statistics: IngestionStatistics = Field(default_factory=IngestionStatistics)
    metadata_extracted: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)

    # Progress history
    progress_history: List[IngestionProgress] = Field(default_factory=list)


class IngestionJobCreate(BaseModel):
    """Request model for creating an ingestion job."""
    filename: str
    file_size_bytes: int = 0
    content_type: Optional[str] = None
    project_id: Optional[str] = None


class IngestionJobFilter(BaseModel):
    """Filter options for listing ingestion jobs."""
    status: Optional[Literal["pending", "in_progress", "success", "partial", "failed"]] = None
    project_id: Optional[str] = None
    filename_contains: Optional[str] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None


# =============================================================================
# Ingestion Tracker Service
# =============================================================================


class IngestionTracker:
    """
    Service for tracking and managing ingestion jobs.

    Provides job lifecycle management including creation, status updates,
    progress tracking, and historical logging.
    """

    COLLECTION_NAME = "ingestion_logs"

    def __init__(self, settings: Settings):
        """
        Initialize ingestion tracker service.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.mongo_client: Optional[AsyncMongoClient] = None
        self.db: Optional[Any] = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize MongoDB connection."""
        if self._initialized:
            return

        self.mongo_client = AsyncMongoClient(
            self.settings.mongodb_uri,
            serverSelectionTimeoutMS=5000
        )
        self.db = self.mongo_client[self.settings.mongodb_database]
        await self.mongo_client.admin.command("ping")
        self._initialized = True
        logger.info("Ingestion tracker service initialized")

    async def cleanup(self) -> None:
        """Clean up MongoDB connection."""
        if self.mongo_client:
            await self.mongo_client.close()
            self.mongo_client = None
            self.db = None
            self._initialized = False
            logger.info("Ingestion tracker service cleaned up")

    @property
    def collection(self):
        """Get the ingestion_logs collection."""
        if self.db is None:
            raise RuntimeError("IngestionTracker not initialized. Call initialize() first.")
        return self.db[self.COLLECTION_NAME]

    async def create_job(self, job_create: IngestionJobCreate) -> IngestionJob:
        """
        Create a new ingestion job.

        Args:
            job_create: Job creation parameters

        Returns:
            Created IngestionJob with assigned ID
        """
        await self.initialize()

        job_doc = {
            "document_id": None,
            "project_id": job_create.project_id,
            "filename": job_create.filename,
            "file_size_bytes": job_create.file_size_bytes,
            "content_type": job_create.content_type,
            "status": "pending",
            "current_stage": IngestionStage.UPLOADING.value,
            "progress_pct": 0,
            "created_at": datetime.utcnow(),
            "started_at": None,
            "completed_at": None,
            "duration_ms": None,
            "statistics": IngestionStatistics().model_dump(),
            "metadata_extracted": {},
            "warnings": [],
            "errors": [],
            "progress_history": []
        }

        result = await self.collection.insert_one(job_doc)
        job_id = str(result.inserted_id)

        logger.info(f"Created ingestion job: {job_id} for file: {job_create.filename}")

        return IngestionJob(
            _id=job_id,
            **{k: v for k, v in job_doc.items() if k != "_id"}
        )

    async def get_job(self, job_id: str) -> Optional[IngestionJob]:
        """
        Retrieve an ingestion job by ID.

        Args:
            job_id: Job ID (ObjectId as string)

        Returns:
            IngestionJob if found, None otherwise
        """
        await self.initialize()

        try:
            doc = await self.collection.find_one({"_id": ObjectId(job_id)})
        except Exception as e:
            logger.warning(f"Invalid job_id format: {job_id}, error: {e}")
            return None

        if not doc:
            return None

        doc["_id"] = str(doc["_id"])
        return IngestionJob(**doc)

    async def update_status(
        self,
        job_id: str,
        stage: IngestionStage,
        progress_pct: int,
        message: str
    ) -> Optional[IngestionJob]:
        """
        Update job progress status.

        Args:
            job_id: Job ID
            stage: Current ingestion stage
            progress_pct: Progress percentage (0-100)
            message: Status message

        Returns:
            Updated IngestionJob if found, None otherwise
        """
        await self.initialize()

        progress_entry = IngestionProgress(
            stage=stage,
            progress_pct=progress_pct,
            message=message
        )

        update_doc: Dict[str, Any] = {
            "$set": {
                "current_stage": stage.value,
                "progress_pct": progress_pct,
                "status": "in_progress" if stage != IngestionStage.FAILED else "failed"
            },
            "$push": {
                "progress_history": progress_entry.model_dump()
            }
        }

        # Set started_at on first progress update
        if stage != IngestionStage.UPLOADING:
            update_doc["$set"]["started_at"] = {"$ifNull": ["$started_at", datetime.utcnow()]}

        try:
            # Use find_one_and_update to get the updated document
            # First, do a simple update
            await self.collection.update_one(
                {"_id": ObjectId(job_id)},
                {
                    "$set": {
                        "current_stage": stage.value,
                        "progress_pct": progress_pct,
                        "status": "in_progress" if stage != IngestionStage.FAILED else "failed"
                    },
                    "$push": {
                        "progress_history": progress_entry.model_dump()
                    }
                }
            )

            # Set started_at if not already set
            await self.collection.update_one(
                {"_id": ObjectId(job_id), "started_at": None},
                {"$set": {"started_at": datetime.utcnow()}}
            )

            logger.debug(f"Updated job {job_id} status: {stage.value} ({progress_pct}%)")
            return await self.get_job(job_id)

        except Exception as e:
            logger.exception(f"Failed to update job status: {job_id}, error: {e}")
            return None

    async def complete_job(
        self,
        job_id: str,
        result: IngestionResult
    ) -> Optional[IngestionJob]:
        """
        Mark a job as complete with final results.

        Args:
            job_id: Job ID
            result: Final ingestion result

        Returns:
            Updated IngestionJob if found, None otherwise
        """
        await self.initialize()

        now = datetime.utcnow()

        # Get current job to calculate duration
        job = await self.get_job(job_id)
        if not job:
            logger.warning(f"Job not found for completion: {job_id}")
            return None

        duration_ms = None
        if job.started_at:
            duration_ms = (now - job.started_at).total_seconds() * 1000

        final_stage = (
            IngestionStage.COMPLETE if result.status == "success"
            else IngestionStage.FAILED
        )

        # Add final progress entry
        progress_entry = IngestionProgress(
            stage=final_stage,
            progress_pct=100 if result.status == "success" else job.progress_pct,
            message="Ingestion complete" if result.status == "success" else "Ingestion failed"
        )

        try:
            await self.collection.update_one(
                {"_id": ObjectId(job_id)},
                {
                    "$set": {
                        "document_id": result.document_id,
                        "status": result.status,
                        "current_stage": final_stage.value,
                        "progress_pct": 100 if result.status == "success" else job.progress_pct,
                        "completed_at": now,
                        "duration_ms": duration_ms,
                        "statistics": result.statistics.model_dump(),
                        "metadata_extracted": result.metadata_extracted,
                        "warnings": result.warnings,
                        "errors": result.errors
                    },
                    "$push": {
                        "progress_history": progress_entry.model_dump()
                    }
                }
            )

            logger.info(
                f"Completed job {job_id}: {result.status}, "
                f"document_id={result.document_id}, "
                f"duration={duration_ms:.0f}ms" if duration_ms else ""
            )

            return await self.get_job(job_id)

        except Exception as e:
            logger.exception(f"Failed to complete job: {job_id}, error: {e}")
            return None

    async def fail_job(
        self,
        job_id: str,
        error_message: str,
        warnings: Optional[List[str]] = None
    ) -> Optional[IngestionJob]:
        """
        Mark a job as failed.

        Args:
            job_id: Job ID
            error_message: Error description
            warnings: Optional list of warnings

        Returns:
            Updated IngestionJob if found, None otherwise
        """
        result = IngestionResult(
            document_id=None,
            status="failed",
            statistics=IngestionStatistics(),
            metadata_extracted={},
            warnings=warnings or [],
            errors=[error_message]
        )
        return await self.complete_job(job_id, result)

    async def list_jobs(
        self,
        filters: Optional[IngestionJobFilter] = None,
        limit: int = 50,
        skip: int = 0
    ) -> List[IngestionJob]:
        """
        List ingestion jobs with optional filtering.

        Args:
            filters: Optional filter criteria
            limit: Maximum jobs to return
            skip: Number of jobs to skip (for pagination)

        Returns:
            List of IngestionJob objects
        """
        await self.initialize()

        query: Dict[str, Any] = {}

        if filters:
            if filters.status:
                query["status"] = filters.status
            if filters.project_id:
                query["project_id"] = filters.project_id
            if filters.filename_contains:
                query["filename"] = {"$regex": filters.filename_contains, "$options": "i"}
            if filters.created_after:
                query["created_at"] = {"$gte": filters.created_after}
            if filters.created_before:
                if "created_at" in query:
                    query["created_at"]["$lte"] = filters.created_before
                else:
                    query["created_at"] = {"$lte": filters.created_before}

        cursor = self.collection.find(query).sort("created_at", -1).skip(skip).limit(limit)

        jobs = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            jobs.append(IngestionJob(**doc))

        return jobs

    async def get_job_count(
        self,
        filters: Optional[IngestionJobFilter] = None
    ) -> int:
        """
        Get count of ingestion jobs matching filters.

        Args:
            filters: Optional filter criteria

        Returns:
            Count of matching jobs
        """
        await self.initialize()

        query: Dict[str, Any] = {}

        if filters:
            if filters.status:
                query["status"] = filters.status
            if filters.project_id:
                query["project_id"] = filters.project_id

        return await self.collection.count_documents(query)

    async def get_aggregate_stats(
        self,
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get aggregate statistics for ingestion jobs.

        Args:
            project_id: Optional project ID to filter by

        Returns:
            Dictionary with aggregate statistics
        """
        await self.initialize()

        match_stage: Dict[str, Any] = {}
        if project_id:
            match_stage["project_id"] = project_id

        pipeline = [
            {"$match": match_stage} if match_stage else {"$match": {}},
            {
                "$group": {
                    "_id": "$status",
                    "count": {"$sum": 1},
                    "total_chunks": {"$sum": "$statistics.chunks_created"},
                    "total_tokens": {"$sum": "$statistics.total_tokens"},
                    "avg_duration_ms": {"$avg": "$duration_ms"}
                }
            }
        ]

        cursor = await self.collection.aggregate(pipeline)
        results = await cursor.to_list(length=100)

        stats = {
            "total_jobs": 0,
            "by_status": {},
            "total_chunks_created": 0,
            "total_tokens_processed": 0,
            "avg_duration_ms": 0.0
        }

        total_duration = 0.0
        duration_count = 0

        for result in results:
            status = result["_id"]
            count = result["count"]
            stats["total_jobs"] += count
            stats["by_status"][status] = count
            stats["total_chunks_created"] += result.get("total_chunks", 0) or 0
            stats["total_tokens_processed"] += result.get("total_tokens", 0) or 0

            if result.get("avg_duration_ms"):
                total_duration += result["avg_duration_ms"] * count
                duration_count += count

        if duration_count > 0:
            stats["avg_duration_ms"] = total_duration / duration_count

        return stats

    async def delete_old_jobs(self, days_old: int = 30) -> int:
        """
        Delete jobs older than specified days.

        Args:
            days_old: Delete jobs older than this many days

        Returns:
            Number of deleted jobs
        """
        await self.initialize()

        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=days_old)

        result = await self.collection.delete_many({"created_at": {"$lt": cutoff}})
        deleted_count = result.deleted_count

        logger.info(f"Deleted {deleted_count} ingestion jobs older than {days_old} days")
        return deleted_count
