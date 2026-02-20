"""Standalone document upload and management endpoints."""

import logging
import os
import tempfile
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, File, UploadFile, Query
from bson import ObjectId
from pymongo import AsyncMongoClient
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

from src.api.validators import validate_object_id
from src.api.exceptions import NotFoundError, ValidationError
from src.settings import load_settings
from src.ingestion.ingest import IngestionConfig, DocumentIngestionPipeline
from src.services.ingestion_tracker import (
    IngestionTracker,
    IngestionJobCreate,
    IngestionStage,
    IngestionJob,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])


# =============================================================================
# Response Models
# =============================================================================


class DocumentMetadata(BaseModel):
    """Document metadata response model."""
    model_config = ConfigDict(populate_by_name=True)

    file_path: Optional[str] = None
    file_size: Optional[int] = None
    word_count: Optional[int] = None
    line_count: Optional[int] = None
    section_count: Optional[int] = None
    document_type: Optional[str] = None
    document_date: Optional[str] = None
    id_informacji: Optional[str] = None
    sygnatura: Optional[str] = None
    interpretation_stance: Optional[str] = None
    outcome_status: Optional[str] = None
    ingestion_date: Optional[str] = None


class DocumentResponse(BaseModel):
    """Response model for a single document."""
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id", serialization_alias="_id")
    title: str
    source: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    project_id: Optional[str] = None
    created_at: datetime
    chunk_count: int = 0


class DocumentListResponse(BaseModel):
    """Response model for paginated document list."""
    documents: List[DocumentResponse]
    total: int
    limit: int
    skip: int
    has_more: bool


class DocumentUploadResponse(BaseModel):
    """Response model for document upload."""
    document_id: Optional[str] = None
    job_id: str
    title: str
    filename: str
    status: str
    chunks_created: int = 0
    total_tokens: int = 0
    metadata_extracted: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    processing_time_ms: float = 0.0


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/upload", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    project_id: Optional[str] = Query(
        None, description="Optional project ID to scope the document"
    ),
):
    """
    Upload a document for ingestion without requiring a project context.

    This endpoint allows standalone document uploads. Documents can optionally
    be associated with a project by providing a project_id.

    Supported formats: PDF, DOCX, PPTX (Docling-supported formats).

    Returns detailed ingestion results including:
    - Chunks created
    - Total tokens
    - Extracted metadata
    - Any warnings or errors
    """
    settings = load_settings()

    # Validate project_id format if provided
    if project_id:
        validate_object_id(project_id, "Project")

    filename = file.filename or "upload"
    ext = os.path.splitext(filename)[1].lower()
    allowed = {".pdf", ".docx", ".pptx", ".doc", ".xlsx", ".xls", ".html", ".htm", ".md", ".txt"}
    if ext not in allowed:
        raise ValidationError(
            f"Unsupported file type '{ext}'. Supported: PDF, DOCX, PPTX, DOC, XLSX, XLS, HTML, MD, TXT."
        )

    # Read file content and get size
    content = await file.read()
    file_size = len(content)
    content_type = file.content_type

    # Initialize ingestion tracker to create a job
    tracker = IngestionTracker(settings)
    await tracker.initialize()

    try:
        # Create ingestion job
        job_create = IngestionJobCreate(
            filename=filename,
            file_size_bytes=file_size,
            content_type=content_type,
            project_id=project_id,
        )
        job = await tracker.create_job(job_create)
        job_id = job.id

        logger.info(f"Created ingestion job {job_id} for file: {filename}")

        # Save to a temp file so Docling can read it by path
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = os.path.join(tmpdir, f"upload{ext}")
            with open(tmp_path, "wb") as f:
                f.write(content)

            # Build extra metadata
            extra_metadata: Dict[str, Any] = {}
            if project_id:
                extra_metadata["project_id"] = ObjectId(project_id)

            # Create progress callback to update job status
            async def progress_callback(
                stage: IngestionStage, pct: int, message: str
            ) -> None:
                await tracker.update_status(job_id, stage, pct, message)

            # Initialize and run ingestion pipeline with tracking
            pipeline = DocumentIngestionPipeline(
                config=IngestionConfig(),
                documents_folder=tmpdir,
                clean_before_ingest=False,
                dry_run=False,
            )
            await pipeline.initialize()

            try:
                result = await pipeline.ingest_file_with_tracking(
                    tmp_path,
                    extra_metadata=extra_metadata if extra_metadata else None,
                    progress_callback=progress_callback,
                )
            finally:
                await pipeline.close()

        # Complete the job with results
        tracker_result = result.to_tracker_result()
        await tracker.complete_job(job_id, tracker_result)

        logger.info(
            f"Document ingestion complete: {result.title}, "
            f"status={result.status}, chunks={result.statistics.chunks_created}"
        )

        return DocumentUploadResponse(
            document_id=result.document_id,
            job_id=job_id,
            title=result.title,
            filename=filename,
            status=result.status,
            chunks_created=result.statistics.chunks_created,
            total_tokens=result.statistics.total_tokens,
            metadata_extracted=result.metadata_extracted,
            warnings=result.warnings,
            errors=result.errors,
            processing_time_ms=result.statistics.processing_time_ms,
        )

    except Exception as e:
        # Mark job as failed
        logger.exception(f"Document upload failed for {filename}: {e}")
        await tracker.fail_job(job_id, str(e))
        raise

    finally:
        await tracker.cleanup()


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    limit: int = Query(50, ge=1, le=100, description="Maximum documents to return"),
    skip: int = Query(0, ge=0, description="Number of documents to skip"),
    search: Optional[str] = Query(None, description="Search in title"),
):
    """
    List all documents with optional filtering and pagination.

    Can filter by:
    - project_id: Only show documents from a specific project (or None for standalone)
    - search: Search term for document title
    """
    settings = load_settings()

    # Validate project_id if provided
    if project_id:
        validate_object_id(project_id, "Project")

    mongo_client = AsyncMongoClient(
        settings.mongodb_uri, serverSelectionTimeoutMS=5000
    )
    db = mongo_client[settings.mongodb_database]
    documents_collection = db[settings.mongodb_collection_documents]
    chunks_collection = db[settings.mongodb_collection_chunks]

    try:
        # Build query
        query: Dict[str, Any] = {}
        if project_id:
            query["metadata.project_id"] = ObjectId(project_id)
        elif project_id == "":
            # Explicitly filter for documents with no project
            query["metadata.project_id"] = {"$exists": False}

        if search:
            query["title"] = {"$regex": search, "$options": "i"}

        # Get total count
        total = await documents_collection.count_documents(query)

        # Fetch documents with pagination
        cursor = (
            documents_collection.find(query)
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )

        documents = []
        async for doc in cursor:
            doc_id = str(doc["_id"])

            # Get chunk count for this document
            chunk_count = await chunks_collection.count_documents(
                {"document_id": doc["_id"]}
            )

            # Extract project_id from metadata if present
            metadata = doc.get("metadata", {})
            doc_project_id = None
            if "project_id" in metadata and metadata["project_id"]:
                doc_project_id = str(metadata["project_id"])
            
            # Convert ObjectId values in metadata to strings for JSON serialization
            serializable_metadata = {}
            for key, value in metadata.items():
                if isinstance(value, ObjectId):
                    serializable_metadata[key] = str(value)
                elif isinstance(value, dict):
                    # Recursively convert ObjectIds in nested dicts
                    serializable_metadata[key] = {
                        k: str(v) if isinstance(v, ObjectId) else v
                        for k, v in value.items()
                    }
                else:
                    serializable_metadata[key] = value

            documents.append(
                DocumentResponse(
                    _id=doc_id,
                    title=doc.get("title", "Untitled"),
                    source=doc.get("source", ""),
                    metadata=serializable_metadata,
                    project_id=doc_project_id,
                    created_at=doc.get("created_at", datetime.utcnow()),
                    chunk_count=chunk_count,
                )
            )

        has_more = skip + len(documents) < total

        return DocumentListResponse(
            documents=documents,
            total=total,
            limit=limit,
            skip=skip,
            has_more=has_more,
        )

    finally:
        await mongo_client.close()


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str):
    """
    Get a single document by ID.

    Returns document details including metadata and chunk count.
    """
    validate_object_id(document_id, "Document")

    settings = load_settings()

    mongo_client = AsyncMongoClient(
        settings.mongodb_uri, serverSelectionTimeoutMS=5000
    )
    db = mongo_client[settings.mongodb_database]
    documents_collection = db[settings.mongodb_collection_documents]
    chunks_collection = db[settings.mongodb_collection_chunks]

    try:
        doc = await documents_collection.find_one({"_id": ObjectId(document_id)})

        if not doc:
            raise NotFoundError("Document", document_id)

        # Get chunk count
        chunk_count = await chunks_collection.count_documents(
            {"document_id": doc["_id"]}
        )

        # Extract project_id from metadata if present
        metadata = doc.get("metadata", {})
        doc_project_id = None
        if "project_id" in metadata and metadata["project_id"]:
            doc_project_id = str(metadata["project_id"])
        
        # Convert ObjectId values in metadata to strings for JSON serialization
        serializable_metadata = {}
        for key, value in metadata.items():
            if isinstance(value, ObjectId):
                serializable_metadata[key] = str(value)
            elif isinstance(value, dict):
                # Recursively convert ObjectIds in nested dicts
                serializable_metadata[key] = {
                    k: str(v) if isinstance(v, ObjectId) else v
                    for k, v in value.items()
                }
            else:
                serializable_metadata[key] = value

        return DocumentResponse(
            _id=str(doc["_id"]),
            title=doc.get("title", "Untitled"),
            source=doc.get("source", ""),
            metadata=serializable_metadata,
            project_id=doc_project_id,
            created_at=doc.get("created_at", datetime.utcnow()),
            chunk_count=chunk_count,
        )

    finally:
        await mongo_client.close()


@router.delete("/{document_id}", status_code=204)
async def delete_document(document_id: str):
    """
    Delete a document and all its associated chunks.

    This permanently removes the document and all its chunks from the database.
    """
    validate_object_id(document_id, "Document")

    settings = load_settings()

    mongo_client = AsyncMongoClient(
        settings.mongodb_uri, serverSelectionTimeoutMS=5000
    )
    db = mongo_client[settings.mongodb_database]
    documents_collection = db[settings.mongodb_collection_documents]
    chunks_collection = db[settings.mongodb_collection_chunks]

    try:
        # Check if document exists
        doc = await documents_collection.find_one({"_id": ObjectId(document_id)})
        if not doc:
            raise NotFoundError("Document", document_id)

        # Delete chunks first
        chunks_result = await chunks_collection.delete_many(
            {"document_id": ObjectId(document_id)}
        )
        logger.info(f"Deleted {chunks_result.deleted_count} chunks for document {document_id}")

        # Delete document
        await documents_collection.delete_one({"_id": ObjectId(document_id)})
        logger.info(f"Deleted document {document_id}")

        return None

    finally:
        await mongo_client.close()
