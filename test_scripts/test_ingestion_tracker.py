"""Unit tests for IngestionTracker service and related models."""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, Optional

from src.services.ingestion_tracker import (
    IngestionTracker,
    IngestionStage,
    IngestionStatistics,
    IngestionProgress,
    IngestionResult,
    IngestionJob,
    IngestionJobCreate,
    IngestionJobFilter,
)


# =============================================================================
# Model Tests
# =============================================================================


class TestIngestionStatistics:
    """Tests for IngestionStatistics model."""

    def test_default_values(self):
        """Test default statistics values."""
        stats = IngestionStatistics()
        assert stats.chunks_created == 0
        assert stats.total_tokens == 0
        assert stats.avg_chunk_tokens == 0.0
        assert stats.sections_found == 0
        assert stats.sections_expected == 0
        assert stats.file_size_bytes == 0
        assert stats.processing_time_ms == 0.0

    def test_custom_values(self):
        """Test statistics with custom values."""
        stats = IngestionStatistics(
            chunks_created=10,
            total_tokens=5000,
            avg_chunk_tokens=500.0,
            sections_found=5,
            sections_expected=7,
            file_size_bytes=50000,
            processing_time_ms=1500.5
        )
        assert stats.chunks_created == 10
        assert stats.total_tokens == 5000
        assert stats.avg_chunk_tokens == 500.0
        assert stats.sections_found == 5
        assert stats.sections_expected == 7
        assert stats.file_size_bytes == 50000
        assert stats.processing_time_ms == 1500.5

    def test_model_dump(self):
        """Test model serialization."""
        stats = IngestionStatistics(chunks_created=5, total_tokens=1000)
        dump = stats.model_dump()
        assert isinstance(dump, dict)
        assert dump["chunks_created"] == 5
        assert dump["total_tokens"] == 1000


class TestIngestionProgress:
    """Tests for IngestionProgress model."""

    def test_progress_creation(self):
        """Test creating progress update."""
        progress = IngestionProgress(
            stage=IngestionStage.CONVERTING,
            progress_pct=25,
            message="Converting document to markdown"
        )
        assert progress.stage == IngestionStage.CONVERTING
        assert progress.progress_pct == 25
        assert progress.message == "Converting document to markdown"
        assert isinstance(progress.timestamp, datetime)

    def test_progress_pct_validation(self):
        """Test progress percentage validation."""
        # Valid progress
        progress = IngestionProgress(
            stage=IngestionStage.EMBEDDING,
            progress_pct=50,
            message="Generating embeddings"
        )
        assert progress.progress_pct == 50

        # Test boundary values
        progress_zero = IngestionProgress(
            stage=IngestionStage.UPLOADING,
            progress_pct=0,
            message="Starting"
        )
        assert progress_zero.progress_pct == 0

        progress_full = IngestionProgress(
            stage=IngestionStage.COMPLETE,
            progress_pct=100,
            message="Complete"
        )
        assert progress_full.progress_pct == 100


class TestIngestionResult:
    """Tests for IngestionResult model."""

    def test_success_result(self):
        """Test successful ingestion result."""
        result = IngestionResult(
            document_id="abc123",
            status="success",
            statistics=IngestionStatistics(chunks_created=10, total_tokens=5000),
            metadata_extracted={"title": "Test Document"},
            warnings=[],
            errors=[]
        )
        assert result.document_id == "abc123"
        assert result.status == "success"
        assert result.statistics.chunks_created == 10
        assert result.metadata_extracted["title"] == "Test Document"
        assert len(result.warnings) == 0
        assert len(result.errors) == 0

    def test_partial_result(self):
        """Test partial ingestion result with warnings."""
        result = IngestionResult(
            document_id="abc123",
            status="partial",
            statistics=IngestionStatistics(chunks_created=5),
            metadata_extracted={},
            warnings=["Section 'Przepis' not found"],
            errors=[]
        )
        assert result.status == "partial"
        assert len(result.warnings) == 1
        assert "Przepis" in result.warnings[0]

    def test_failed_result(self):
        """Test failed ingestion result."""
        result = IngestionResult(
            document_id=None,
            status="failed",
            statistics=IngestionStatistics(),
            metadata_extracted={},
            warnings=[],
            errors=["Document conversion failed"]
        )
        assert result.document_id is None
        assert result.status == "failed"
        assert len(result.errors) == 1


class TestIngestionJob:
    """Tests for IngestionJob model."""

    def test_job_creation(self):
        """Test creating ingestion job."""
        job = IngestionJob(
            _id="60f1c0d9e2a1b0001c2d3e4f",
            filename="test.pdf",
            file_size_bytes=50000,
            content_type="application/pdf"
        )
        assert job.id == "60f1c0d9e2a1b0001c2d3e4f"
        assert job.filename == "test.pdf"
        assert job.file_size_bytes == 50000
        assert job.content_type == "application/pdf"
        assert job.status == "pending"
        assert job.current_stage == IngestionStage.UPLOADING
        assert job.progress_pct == 0

    def test_job_with_all_fields(self):
        """Test job with all fields populated."""
        now = datetime.utcnow()
        job = IngestionJob(
            _id="60f1c0d9e2a1b0001c2d3e4f",
            document_id="doc123",
            project_id="proj456",
            filename="test.pdf",
            file_size_bytes=50000,
            content_type="application/pdf",
            status="success",
            current_stage=IngestionStage.COMPLETE,
            progress_pct=100,
            created_at=now,
            started_at=now,
            completed_at=now,
            duration_ms=5000.0,
            statistics=IngestionStatistics(chunks_created=10),
            metadata_extracted={"title": "Test"},
            warnings=["Warning 1"],
            errors=[]
        )
        assert job.document_id == "doc123"
        assert job.project_id == "proj456"
        assert job.status == "success"
        assert job.duration_ms == 5000.0
        assert job.statistics.chunks_created == 10

    def test_job_alias_serialization(self):
        """Test that _id alias works correctly."""
        job = IngestionJob(
            _id="test_id",
            filename="test.pdf"
        )
        dump = job.model_dump(by_alias=True)
        assert "_id" in dump
        assert dump["_id"] == "test_id"


class TestIngestionJobCreate:
    """Tests for IngestionJobCreate model."""

    def test_minimal_create(self):
        """Test minimal job creation request."""
        create = IngestionJobCreate(filename="test.pdf")
        assert create.filename == "test.pdf"
        assert create.file_size_bytes == 0
        assert create.content_type is None
        assert create.project_id is None

    def test_full_create(self):
        """Test full job creation request."""
        create = IngestionJobCreate(
            filename="test.pdf",
            file_size_bytes=50000,
            content_type="application/pdf",
            project_id="proj123"
        )
        assert create.filename == "test.pdf"
        assert create.file_size_bytes == 50000
        assert create.content_type == "application/pdf"
        assert create.project_id == "proj123"


class TestIngestionJobFilter:
    """Tests for IngestionJobFilter model."""

    def test_empty_filter(self):
        """Test empty filter."""
        filter = IngestionJobFilter()
        assert filter.status is None
        assert filter.project_id is None
        assert filter.filename_contains is None
        assert filter.created_after is None
        assert filter.created_before is None

    def test_status_filter(self):
        """Test status filter."""
        filter = IngestionJobFilter(status="success")
        assert filter.status == "success"

    def test_date_range_filter(self):
        """Test date range filter."""
        now = datetime.utcnow()
        yesterday = now - timedelta(days=1)
        filter = IngestionJobFilter(
            created_after=yesterday,
            created_before=now
        )
        assert filter.created_after == yesterday
        assert filter.created_before == now


# =============================================================================
# Service Tests (with mocked MongoDB)
# =============================================================================


class TestIngestionTrackerService:
    """Tests for IngestionTracker service with mocked MongoDB."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = MagicMock()
        settings.mongodb_uri = "mongodb://localhost:27017"
        settings.mongodb_database = "test_db"
        return settings

    @pytest.fixture
    def mock_collection(self):
        """Create mock MongoDB collection."""
        collection = AsyncMock()
        return collection

    @pytest.fixture
    def tracker_with_mocks(self, mock_settings, mock_collection):
        """Create tracker with mocked dependencies."""
        tracker = IngestionTracker(mock_settings)
        tracker._initialized = True
        tracker.db = MagicMock()
        tracker.db.__getitem__ = MagicMock(return_value=mock_collection)
        return tracker, mock_collection

    @pytest.mark.asyncio
    async def test_create_job(self, tracker_with_mocks):
        """Test job creation."""
        tracker, mock_collection = tracker_with_mocks

        # Mock insert_one result
        mock_result = MagicMock()
        mock_result.inserted_id = "60f1c0d9e2a1b0001c2d3e4f"
        mock_collection.insert_one = AsyncMock(return_value=mock_result)

        job_create = IngestionJobCreate(
            filename="test.pdf",
            file_size_bytes=50000,
            content_type="application/pdf",
            project_id="proj123"
        )

        job = await tracker.create_job(job_create)

        assert job.id == "60f1c0d9e2a1b0001c2d3e4f"
        assert job.filename == "test.pdf"
        assert job.status == "pending"
        mock_collection.insert_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_job_found(self, tracker_with_mocks):
        """Test getting existing job."""
        tracker, mock_collection = tracker_with_mocks

        mock_doc = {
            "_id": "60f1c0d9e2a1b0001c2d3e4f",
            "document_id": None,
            "project_id": "proj123",
            "filename": "test.pdf",
            "file_size_bytes": 50000,
            "content_type": "application/pdf",
            "status": "pending",
            "current_stage": "uploading",
            "progress_pct": 0,
            "created_at": datetime.utcnow(),
            "started_at": None,
            "completed_at": None,
            "duration_ms": None,
            "statistics": {"chunks_created": 0, "total_tokens": 0, "avg_chunk_tokens": 0.0, "sections_found": 0, "sections_expected": 0, "file_size_bytes": 0, "processing_time_ms": 0.0},
            "metadata_extracted": {},
            "warnings": [],
            "errors": [],
            "progress_history": []
        }
        mock_collection.find_one = AsyncMock(return_value=mock_doc)

        job = await tracker.get_job("60f1c0d9e2a1b0001c2d3e4f")

        assert job is not None
        assert job.id == "60f1c0d9e2a1b0001c2d3e4f"
        assert job.filename == "test.pdf"

    @pytest.mark.asyncio
    async def test_get_job_not_found(self, tracker_with_mocks):
        """Test getting non-existent job."""
        tracker, mock_collection = tracker_with_mocks
        mock_collection.find_one = AsyncMock(return_value=None)

        job = await tracker.get_job("60f1c0d9e2a1b0001c2d3e4f")

        assert job is None

    @pytest.mark.asyncio
    async def test_get_job_invalid_id(self, tracker_with_mocks):
        """Test getting job with invalid ID."""
        tracker, mock_collection = tracker_with_mocks
        mock_collection.find_one = AsyncMock(side_effect=Exception("Invalid ObjectId"))

        job = await tracker.get_job("invalid_id")

        assert job is None

    @pytest.mark.asyncio
    async def test_update_status(self, tracker_with_mocks):
        """Test updating job status."""
        tracker, mock_collection = tracker_with_mocks

        mock_collection.update_one = AsyncMock()

        mock_doc = {
            "_id": "60f1c0d9e2a1b0001c2d3e4f",
            "document_id": None,
            "project_id": None,
            "filename": "test.pdf",
            "file_size_bytes": 50000,
            "content_type": "application/pdf",
            "status": "in_progress",
            "current_stage": "converting",
            "progress_pct": 25,
            "created_at": datetime.utcnow(),
            "started_at": datetime.utcnow(),
            "completed_at": None,
            "duration_ms": None,
            "statistics": {"chunks_created": 0, "total_tokens": 0, "avg_chunk_tokens": 0.0, "sections_found": 0, "sections_expected": 0, "file_size_bytes": 0, "processing_time_ms": 0.0},
            "metadata_extracted": {},
            "warnings": [],
            "errors": [],
            "progress_history": []
        }
        mock_collection.find_one = AsyncMock(return_value=mock_doc)

        job = await tracker.update_status(
            "60f1c0d9e2a1b0001c2d3e4f",
            IngestionStage.CONVERTING,
            25,
            "Converting document"
        )

        assert job is not None
        assert mock_collection.update_one.call_count == 2  # Status update + started_at

    @pytest.mark.asyncio
    async def test_complete_job_success(self, tracker_with_mocks):
        """Test completing job successfully."""
        tracker, mock_collection = tracker_with_mocks

        # Mock get_job to return existing job
        started_at = datetime.utcnow() - timedelta(seconds=5)
        mock_doc_before = {
            "_id": "60f1c0d9e2a1b0001c2d3e4f",
            "document_id": None,
            "project_id": None,
            "filename": "test.pdf",
            "file_size_bytes": 50000,
            "content_type": "application/pdf",
            "status": "in_progress",
            "current_stage": "storing",
            "progress_pct": 90,
            "created_at": started_at - timedelta(seconds=1),
            "started_at": started_at,
            "completed_at": None,
            "duration_ms": None,
            "statistics": {"chunks_created": 0, "total_tokens": 0, "avg_chunk_tokens": 0.0, "sections_found": 0, "sections_expected": 0, "file_size_bytes": 0, "processing_time_ms": 0.0},
            "metadata_extracted": {},
            "warnings": [],
            "errors": [],
            "progress_history": []
        }

        mock_doc_after = {
            **mock_doc_before,
            "document_id": "doc123",
            "status": "success",
            "current_stage": "complete",
            "progress_pct": 100,
            "completed_at": datetime.utcnow(),
            "duration_ms": 5000.0,
            "statistics": {"chunks_created": 10, "total_tokens": 5000, "avg_chunk_tokens": 500.0, "sections_found": 5, "sections_expected": 7, "file_size_bytes": 50000, "processing_time_ms": 5000.0},
        }

        # Return mock_doc_before for first call, mock_doc_after for second
        mock_collection.find_one = AsyncMock(side_effect=[mock_doc_before, mock_doc_after])
        mock_collection.update_one = AsyncMock()

        result = IngestionResult(
            document_id="doc123",
            status="success",
            statistics=IngestionStatistics(
                chunks_created=10,
                total_tokens=5000,
                avg_chunk_tokens=500.0,
                sections_found=5,
                sections_expected=7,
                file_size_bytes=50000,
                processing_time_ms=5000.0
            ),
            metadata_extracted={"title": "Test Document"},
            warnings=[],
            errors=[]
        )

        job = await tracker.complete_job("60f1c0d9e2a1b0001c2d3e4f", result)

        assert job is not None
        mock_collection.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_fail_job(self, tracker_with_mocks):
        """Test failing a job."""
        tracker, mock_collection = tracker_with_mocks

        # Mock the complete_job path
        started_at = datetime.utcnow() - timedelta(seconds=2)
        mock_doc = {
            "_id": "60f1c0d9e2a1b0001c2d3e4f",
            "document_id": None,
            "project_id": None,
            "filename": "test.pdf",
            "file_size_bytes": 50000,
            "content_type": "application/pdf",
            "status": "in_progress",
            "current_stage": "converting",
            "progress_pct": 25,
            "created_at": started_at,
            "started_at": started_at,
            "completed_at": None,
            "duration_ms": None,
            "statistics": {"chunks_created": 0, "total_tokens": 0, "avg_chunk_tokens": 0.0, "sections_found": 0, "sections_expected": 0, "file_size_bytes": 0, "processing_time_ms": 0.0},
            "metadata_extracted": {},
            "warnings": [],
            "errors": [],
            "progress_history": []
        }

        mock_doc_failed = {
            **mock_doc,
            "status": "failed",
            "current_stage": "failed",
            "errors": ["Conversion failed"]
        }

        mock_collection.find_one = AsyncMock(side_effect=[mock_doc, mock_doc_failed])
        mock_collection.update_one = AsyncMock()

        job = await tracker.fail_job(
            "60f1c0d9e2a1b0001c2d3e4f",
            "Conversion failed",
            warnings=["Some warning"]
        )

        assert job is not None
        mock_collection.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_jobs_no_filter(self, tracker_with_mocks):
        """Test listing jobs without filters."""
        tracker, mock_collection = tracker_with_mocks

        mock_docs = [
            {
                "_id": "job1",
                "document_id": None,
                "project_id": None,
                "filename": "test1.pdf",
                "file_size_bytes": 50000,
                "content_type": "application/pdf",
                "status": "success",
                "current_stage": "complete",
                "progress_pct": 100,
                "created_at": datetime.utcnow(),
                "started_at": datetime.utcnow(),
                "completed_at": datetime.utcnow(),
                "duration_ms": 5000.0,
                "statistics": {"chunks_created": 10, "total_tokens": 5000, "avg_chunk_tokens": 500.0, "sections_found": 5, "sections_expected": 7, "file_size_bytes": 50000, "processing_time_ms": 5000.0},
                "metadata_extracted": {},
                "warnings": [],
                "errors": [],
                "progress_history": []
            },
            {
                "_id": "job2",
                "document_id": None,
                "project_id": None,
                "filename": "test2.pdf",
                "file_size_bytes": 30000,
                "content_type": "application/pdf",
                "status": "pending",
                "current_stage": "uploading",
                "progress_pct": 0,
                "created_at": datetime.utcnow(),
                "started_at": None,
                "completed_at": None,
                "duration_ms": None,
                "statistics": {"chunks_created": 0, "total_tokens": 0, "avg_chunk_tokens": 0.0, "sections_found": 0, "sections_expected": 0, "file_size_bytes": 0, "processing_time_ms": 0.0},
                "metadata_extracted": {},
                "warnings": [],
                "errors": [],
                "progress_history": []
            }
        ]

        # Mock the cursor's async iteration
        async def mock_async_iter():
            for doc in mock_docs:
                yield doc

        mock_cursor = MagicMock()
        mock_cursor.sort = MagicMock(return_value=mock_cursor)
        mock_cursor.skip = MagicMock(return_value=mock_cursor)
        mock_cursor.limit = MagicMock(return_value=mock_cursor)
        mock_cursor.__aiter__ = lambda self: mock_async_iter()

        mock_collection.find = MagicMock(return_value=mock_cursor)

        jobs = await tracker.list_jobs()

        assert len(jobs) == 2
        assert jobs[0].filename == "test1.pdf"
        assert jobs[1].filename == "test2.pdf"

    @pytest.mark.asyncio
    async def test_list_jobs_with_filter(self, tracker_with_mocks):
        """Test listing jobs with status filter."""
        tracker, mock_collection = tracker_with_mocks

        mock_docs = [
            {
                "_id": "job1",
                "document_id": None,
                "project_id": None,
                "filename": "test1.pdf",
                "file_size_bytes": 50000,
                "content_type": "application/pdf",
                "status": "success",
                "current_stage": "complete",
                "progress_pct": 100,
                "created_at": datetime.utcnow(),
                "started_at": datetime.utcnow(),
                "completed_at": datetime.utcnow(),
                "duration_ms": 5000.0,
                "statistics": {"chunks_created": 10, "total_tokens": 5000, "avg_chunk_tokens": 500.0, "sections_found": 5, "sections_expected": 7, "file_size_bytes": 50000, "processing_time_ms": 5000.0},
                "metadata_extracted": {},
                "warnings": [],
                "errors": [],
                "progress_history": []
            }
        ]

        async def mock_async_iter():
            for doc in mock_docs:
                yield doc

        mock_cursor = MagicMock()
        mock_cursor.sort = MagicMock(return_value=mock_cursor)
        mock_cursor.skip = MagicMock(return_value=mock_cursor)
        mock_cursor.limit = MagicMock(return_value=mock_cursor)
        mock_cursor.__aiter__ = lambda self: mock_async_iter()

        mock_collection.find = MagicMock(return_value=mock_cursor)

        filter = IngestionJobFilter(status="success")
        jobs = await tracker.list_jobs(filters=filter)

        assert len(jobs) == 1
        assert jobs[0].status == "success"
        # Verify the filter was applied
        call_args = mock_collection.find.call_args[0][0]
        assert call_args.get("status") == "success"

    @pytest.mark.asyncio
    async def test_get_job_count(self, tracker_with_mocks):
        """Test getting job count."""
        tracker, mock_collection = tracker_with_mocks
        mock_collection.count_documents = AsyncMock(return_value=42)

        count = await tracker.get_job_count()

        assert count == 42
        mock_collection.count_documents.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_aggregate_stats(self, tracker_with_mocks):
        """Test getting aggregate statistics."""
        tracker, mock_collection = tracker_with_mocks

        mock_results = [
            {
                "_id": "success",
                "count": 10,
                "total_chunks": 100,
                "total_tokens": 50000,
                "avg_duration_ms": 5000.0
            },
            {
                "_id": "failed",
                "count": 2,
                "total_chunks": 0,
                "total_tokens": 0,
                "avg_duration_ms": 1000.0
            }
        ]

        mock_cursor = AsyncMock()
        mock_cursor.to_list = AsyncMock(return_value=mock_results)
        mock_collection.aggregate = MagicMock(return_value=mock_cursor)

        stats = await tracker.get_aggregate_stats()

        assert stats["total_jobs"] == 12
        assert stats["by_status"]["success"] == 10
        assert stats["by_status"]["failed"] == 2
        assert stats["total_chunks_created"] == 100
        assert stats["total_tokens_processed"] == 50000

    @pytest.mark.asyncio
    async def test_delete_old_jobs(self, tracker_with_mocks):
        """Test deleting old jobs."""
        tracker, mock_collection = tracker_with_mocks

        mock_result = MagicMock()
        mock_result.deleted_count = 5
        mock_collection.delete_many = AsyncMock(return_value=mock_result)

        deleted = await tracker.delete_old_jobs(days_old=30)

        assert deleted == 5
        mock_collection.delete_many.assert_called_once()


# =============================================================================
# Stage Enum Tests
# =============================================================================


class TestIngestionStage:
    """Tests for IngestionStage enum."""

    def test_all_stages_defined(self):
        """Test all expected stages are defined."""
        expected_stages = [
            "uploading",
            "converting",
            "extracting_metadata",
            "chunking",
            "embedding",
            "storing",
            "verifying",
            "complete",
            "failed"
        ]
        actual_stages = [s.value for s in IngestionStage]
        assert set(expected_stages) == set(actual_stages)

    def test_stage_values(self):
        """Test stage string values."""
        assert IngestionStage.UPLOADING.value == "uploading"
        assert IngestionStage.CONVERTING.value == "converting"
        assert IngestionStage.EXTRACTING_METADATA.value == "extracting_metadata"
        assert IngestionStage.CHUNKING.value == "chunking"
        assert IngestionStage.EMBEDDING.value == "embedding"
        assert IngestionStage.STORING.value == "storing"
        assert IngestionStage.VERIFYING.value == "verifying"
        assert IngestionStage.COMPLETE.value == "complete"
        assert IngestionStage.FAILED.value == "failed"

    def test_stage_from_string(self):
        """Test creating stage from string."""
        assert IngestionStage("uploading") == IngestionStage.UPLOADING
        assert IngestionStage("complete") == IngestionStage.COMPLETE


# =============================================================================
# Run tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
