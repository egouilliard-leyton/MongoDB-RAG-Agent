"""Integration tests for document ingestion workflow.

These tests require a running MongoDB instance and may modify the database.
Set environment variable MONGODB_URI to configure the connection.
"""

import asyncio
import os
import pytest
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Check for required environment
MONGODB_URI = os.environ.get("MONGODB_URI", "")
SKIP_INTEGRATION = not MONGODB_URI

# Conditionally import based on availability
if not SKIP_INTEGRATION:
    try:
        from src.settings import Settings
        from src.services.ingestion_tracker import (
            IngestionTracker,
            IngestionStage,
            IngestionStatistics,
            IngestionResult,
            IngestionJobCreate,
            IngestionJobFilter,
        )
        IMPORTS_AVAILABLE = True
    except ImportError:
        IMPORTS_AVAILABLE = False
        SKIP_INTEGRATION = True
else:
    IMPORTS_AVAILABLE = False


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
def settings():
    """Create test settings."""
    if SKIP_INTEGRATION:
        pytest.skip("MongoDB URI not configured or imports unavailable")
    return Settings()


@pytest.fixture
async def tracker(settings):
    """Create and initialize ingestion tracker."""
    tracker = IngestionTracker(settings)
    await tracker.initialize()
    yield tracker
    await tracker.cleanup()


@pytest.fixture
def sample_pdf_content():
    """Create sample PDF-like content for testing."""
    return b"%PDF-1.4 Sample PDF content for testing"


@pytest.fixture
def sample_file(sample_pdf_content):
    """Create a temporary test file."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(sample_pdf_content)
        temp_path = f.name
    yield temp_path
    # Cleanup
    try:
        os.unlink(temp_path)
    except Exception:
        pass


# =============================================================================
# Integration Tests - Ingestion Tracker
# =============================================================================


@pytest.mark.skipif(SKIP_INTEGRATION, reason="MongoDB not configured")
@pytest.mark.integration
class TestIngestionTrackerIntegration:
    """Integration tests for IngestionTracker with real MongoDB."""

    @pytest.mark.asyncio
    async def test_full_job_lifecycle(self, tracker):
        """Test complete job lifecycle: create -> update -> complete."""
        # Create job
        job_create = IngestionJobCreate(
            filename="test_integration.pdf",
            file_size_bytes=50000,
            content_type="application/pdf"
        )
        job = await tracker.create_job(job_create)
        assert job is not None
        assert job.status == "pending"
        assert job.filename == "test_integration.pdf"

        # Update progress through stages
        stages = [
            (IngestionStage.CONVERTING, 20, "Converting..."),
            (IngestionStage.EXTRACTING_METADATA, 35, "Extracting metadata..."),
            (IngestionStage.CHUNKING, 50, "Chunking..."),
            (IngestionStage.EMBEDDING, 70, "Generating embeddings..."),
            (IngestionStage.STORING, 90, "Storing..."),
        ]

        for stage, pct, msg in stages:
            updated = await tracker.update_status(job.id, stage, pct, msg)
            assert updated is not None
            assert updated.current_stage == stage
            assert updated.progress_pct == pct
            assert updated.status == "in_progress"

        # Complete the job
        result = IngestionResult(
            document_id="test_doc_123",
            status="success",
            statistics=IngestionStatistics(
                chunks_created=10,
                total_tokens=5000,
                avg_chunk_tokens=500.0,
                sections_found=5,
                sections_expected=5,
                file_size_bytes=50000,
                processing_time_ms=2500.0
            ),
            metadata_extracted={"title": "Test Document", "author": "Test"},
            warnings=[],
            errors=[]
        )
        completed = await tracker.complete_job(job.id, result)
        assert completed is not None
        assert completed.status == "success"
        assert completed.current_stage == IngestionStage.COMPLETE
        assert completed.progress_pct == 100
        assert completed.document_id == "test_doc_123"
        assert completed.statistics.chunks_created == 10
        assert completed.duration_ms is not None
        assert completed.duration_ms > 0

        # Cleanup: delete the test job
        await tracker.collection.delete_one({"_id": ObjectId(job.id)})

    @pytest.mark.asyncio
    async def test_failed_job(self, tracker):
        """Test job failure handling."""
        # Create job
        job_create = IngestionJobCreate(filename="test_fail.pdf")
        job = await tracker.create_job(job_create)

        # Update to converting stage
        await tracker.update_status(
            job.id,
            IngestionStage.CONVERTING,
            25,
            "Converting..."
        )

        # Fail the job
        failed = await tracker.fail_job(
            job.id,
            "Document conversion failed: invalid format",
            warnings=["File appears corrupted"]
        )

        assert failed is not None
        assert failed.status == "failed"
        assert failed.current_stage == IngestionStage.FAILED
        assert len(failed.errors) == 1
        assert "conversion failed" in failed.errors[0].lower()
        assert len(failed.warnings) == 1

        # Cleanup
        await tracker.collection.delete_one({"_id": ObjectId(job.id)})

    @pytest.mark.asyncio
    async def test_list_and_filter_jobs(self, tracker):
        """Test listing and filtering jobs."""
        # Create multiple test jobs
        test_jobs = []
        for i, status in enumerate(["success", "failed", "success"]):
            job_create = IngestionJobCreate(filename=f"filter_test_{i}.pdf")
            job = await tracker.create_job(job_create)

            if status == "success":
                result = IngestionResult(
                    document_id=f"doc_{i}",
                    status="success",
                    statistics=IngestionStatistics(chunks_created=i + 1),
                    metadata_extracted={},
                    warnings=[],
                    errors=[]
                )
                await tracker.complete_job(job.id, result)
            else:
                await tracker.fail_job(job.id, "Test failure")

            test_jobs.append(job)

        try:
            # Test listing all
            all_jobs = await tracker.list_jobs(limit=100)
            assert len(all_jobs) >= 3

            # Test filtering by status
            success_filter = IngestionJobFilter(status="success")
            success_jobs = await tracker.list_jobs(filters=success_filter)
            assert all(j.status == "success" for j in success_jobs)

            failed_filter = IngestionJobFilter(status="failed")
            failed_jobs = await tracker.list_jobs(filters=failed_filter)
            assert all(j.status == "failed" for j in failed_jobs)

            # Test filename filter
            filename_filter = IngestionJobFilter(filename_contains="filter_test")
            filtered = await tracker.list_jobs(filters=filename_filter)
            assert len(filtered) >= 3

        finally:
            # Cleanup
            for job in test_jobs:
                await tracker.collection.delete_one({"_id": ObjectId(job.id)})

    @pytest.mark.asyncio
    async def test_aggregate_stats(self, tracker):
        """Test aggregate statistics calculation."""
        # Create test jobs with different statuses
        test_jobs = []

        # Create successful job
        job1 = await tracker.create_job(IngestionJobCreate(filename="stats_test_1.pdf"))
        await tracker.complete_job(job1.id, IngestionResult(
            document_id="doc1",
            status="success",
            statistics=IngestionStatistics(chunks_created=10, total_tokens=1000),
            metadata_extracted={},
            warnings=[],
            errors=[]
        ))
        test_jobs.append(job1)

        # Create another successful job
        job2 = await tracker.create_job(IngestionJobCreate(filename="stats_test_2.pdf"))
        await tracker.complete_job(job2.id, IngestionResult(
            document_id="doc2",
            status="success",
            statistics=IngestionStatistics(chunks_created=20, total_tokens=2000),
            metadata_extracted={},
            warnings=[],
            errors=[]
        ))
        test_jobs.append(job2)

        # Create failed job
        job3 = await tracker.create_job(IngestionJobCreate(filename="stats_test_3.pdf"))
        await tracker.fail_job(job3.id, "Test failure")
        test_jobs.append(job3)

        try:
            stats = await tracker.get_aggregate_stats()

            assert stats["total_jobs"] >= 3
            assert "success" in stats["by_status"]
            assert "failed" in stats["by_status"]
            assert stats["total_chunks_created"] >= 30  # 10 + 20
            assert stats["total_tokens_processed"] >= 3000  # 1000 + 2000

        finally:
            # Cleanup
            for job in test_jobs:
                await tracker.collection.delete_one({"_id": ObjectId(job.id)})

    @pytest.mark.asyncio
    async def test_job_count(self, tracker):
        """Test job counting with filters."""
        # Create test jobs
        job1 = await tracker.create_job(IngestionJobCreate(filename="count_test_1.pdf"))
        await tracker.complete_job(job1.id, IngestionResult(
            document_id="doc1",
            status="success",
            statistics=IngestionStatistics(),
            metadata_extracted={},
            warnings=[],
            errors=[]
        ))

        job2 = await tracker.create_job(IngestionJobCreate(filename="count_test_2.pdf"))
        # Leave as pending

        try:
            # Count all
            total = await tracker.get_job_count()
            assert total >= 2

            # Count by status
            success_count = await tracker.get_job_count(
                filters=IngestionJobFilter(status="success")
            )
            assert success_count >= 1

            pending_count = await tracker.get_job_count(
                filters=IngestionJobFilter(status="pending")
            )
            assert pending_count >= 1

        finally:
            # Cleanup
            await tracker.collection.delete_one({"_id": ObjectId(job1.id)})
            await tracker.collection.delete_one({"_id": ObjectId(job2.id)})


# =============================================================================
# SSE Streaming Tests
# =============================================================================


@pytest.mark.skipif(SKIP_INTEGRATION, reason="MongoDB not configured")
@pytest.mark.integration
class TestSSEIntegration:
    """Integration tests for SSE streaming functionality."""

    @pytest.mark.asyncio
    async def test_sse_progress_format(self, tracker):
        """Test that job status is properly formatted for SSE."""
        # Create a job
        job = await tracker.create_job(
            IngestionJobCreate(filename="sse_test.pdf")
        )

        try:
            # Update status
            await tracker.update_status(
                job.id,
                IngestionStage.CONVERTING,
                25,
                "Converting document..."
            )

            # Get job and verify it can be serialized for SSE
            updated = await tracker.get_job(job.id)
            assert updated is not None

            # Verify model_dump_json works (used in SSE)
            from pydantic import BaseModel
            json_data = updated.model_dump_json()
            assert isinstance(json_data, str)
            assert "converting" in json_data
            assert "25" in json_data

        finally:
            await tracker.collection.delete_one({"_id": ObjectId(job.id)})

    @pytest.mark.asyncio
    async def test_progress_history_accumulation(self, tracker):
        """Test that progress history accumulates correctly."""
        job = await tracker.create_job(
            IngestionJobCreate(filename="history_test.pdf")
        )

        try:
            # Go through multiple stages
            stages = [
                (IngestionStage.CONVERTING, 20),
                (IngestionStage.EXTRACTING_METADATA, 35),
                (IngestionStage.CHUNKING, 50),
            ]

            for stage, pct in stages:
                await tracker.update_status(job.id, stage, pct, f"Stage: {stage.value}")
                await asyncio.sleep(0.01)  # Small delay to ensure ordering

            # Verify progress history
            final = await tracker.get_job(job.id)
            assert len(final.progress_history) == len(stages)

            # Verify order
            for i, (stage, pct) in enumerate(stages):
                assert final.progress_history[i].stage == stage
                assert final.progress_history[i].progress_pct == pct

        finally:
            await tracker.collection.delete_one({"_id": ObjectId(job.id)})


# =============================================================================
# Document Persistence Tests
# =============================================================================


@pytest.mark.skipif(SKIP_INTEGRATION, reason="MongoDB not configured")
@pytest.mark.integration
class TestIngestionPersistence:
    """Tests for ingestion data persistence."""

    @pytest.mark.asyncio
    async def test_metadata_persistence(self, tracker):
        """Test that extracted metadata is persisted correctly."""
        job = await tracker.create_job(
            IngestionJobCreate(filename="metadata_test.pdf")
        )

        try:
            # Complete with metadata
            complex_metadata = {
                "title": "Test Document",
                "author": "Test Author",
                "date": "2024-01-15",
                "keywords": ["test", "document", "ingestion"],
                "nested": {
                    "field1": "value1",
                    "field2": 123
                }
            }

            result = IngestionResult(
                document_id="meta_doc_1",
                status="success",
                statistics=IngestionStatistics(chunks_created=5),
                metadata_extracted=complex_metadata,
                warnings=["Minor warning"],
                errors=[]
            )

            await tracker.complete_job(job.id, result)

            # Retrieve and verify
            saved = await tracker.get_job(job.id)
            assert saved.metadata_extracted["title"] == "Test Document"
            assert saved.metadata_extracted["keywords"] == ["test", "document", "ingestion"]
            assert saved.metadata_extracted["nested"]["field1"] == "value1"
            assert saved.warnings == ["Minor warning"]

        finally:
            await tracker.collection.delete_one({"_id": ObjectId(job.id)})

    @pytest.mark.asyncio
    async def test_statistics_persistence(self, tracker):
        """Test that statistics are persisted correctly."""
        job = await tracker.create_job(
            IngestionJobCreate(
                filename="stats_persist_test.pdf",
                file_size_bytes=100000
            )
        )

        try:
            stats = IngestionStatistics(
                chunks_created=25,
                total_tokens=12500,
                avg_chunk_tokens=500.0,
                sections_found=7,
                sections_expected=8,
                file_size_bytes=100000,
                processing_time_ms=3500.5
            )

            result = IngestionResult(
                document_id="stats_doc_1",
                status="success",
                statistics=stats,
                metadata_extracted={},
                warnings=[],
                errors=[]
            )

            await tracker.complete_job(job.id, result)

            # Retrieve and verify
            saved = await tracker.get_job(job.id)
            assert saved.statistics.chunks_created == 25
            assert saved.statistics.total_tokens == 12500
            assert saved.statistics.avg_chunk_tokens == 500.0
            assert saved.statistics.sections_found == 7
            assert saved.statistics.sections_expected == 8
            assert saved.statistics.processing_time_ms == 3500.5

        finally:
            await tracker.collection.delete_one({"_id": ObjectId(job.id)})


# =============================================================================
# Helper for ObjectId (import at runtime)
# =============================================================================

if IMPORTS_AVAILABLE:
    from bson import ObjectId


# =============================================================================
# Run tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
