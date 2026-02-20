"""Project management endpoints (projects, stages, uploads)."""

import logging
import os
import tempfile
from typing import List

from fastapi import APIRouter, File, UploadFile
from bson import ObjectId

from src.api.models import (
    ProjectCreateRequest,
    ProjectResponse,
    ProjectStageUpdateRequest,
)
from src.api.validators import validate_object_id
from src.api.exceptions import NotFoundError, ValidationError
from src.settings import load_settings
from src.services.project_storage import ProjectStorageService
from src.ingestion.ingest import IngestionConfig, DocumentIngestionPipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(request: ProjectCreateRequest):
    """
    Create a new project.

    Accepts optional tax_office_id, region, and industry fields for
    geographic and industry scoping.
    """
    settings = load_settings()
    svc = ProjectStorageService(settings)
    await svc.initialize()
    try:
        project_id = await svc.create_project(
            name=request.name,
            company_info=request.company_info or {},
            tax_office_id=request.tax_office_id,
            region=request.region,
            industry=request.industry,
        )
        project = await svc.get_project(project_id)
        return ProjectResponse(**project)
    finally:
        await svc.cleanup()


@router.get("", response_model=List[ProjectResponse])
async def list_projects():
    settings = load_settings()
    svc = ProjectStorageService(settings)
    await svc.initialize()
    try:
        projects = await svc.list_projects()
        return [ProjectResponse(**p) for p in projects]
    finally:
        await svc.cleanup()


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str):
    validate_object_id(project_id, "Project")
    settings = load_settings()
    svc = ProjectStorageService(settings)
    await svc.initialize()
    try:
        project = await svc.get_project(project_id)
        return ProjectResponse(**project)
    except ValueError as e:
        if "not found" in str(e).lower():
            raise NotFoundError("Project", project_id)
        raise
    finally:
        await svc.cleanup()


@router.put("/{project_id}/stage", response_model=ProjectResponse)
async def update_project_stage(project_id: str, request: ProjectStageUpdateRequest):
    validate_object_id(project_id, "Project")
    settings = load_settings()
    svc = ProjectStorageService(settings)
    await svc.initialize()
    try:
        force = request.mode == "force"
        event = request.event
        if request.mode == "rollback":
            # Keep history readable
            event = f"rollback:{event}"
            force = True
        project = await svc.set_stage(
            project_id=project_id,
            to_stage=request.to_stage,
            event=event,
            note=request.note,
            by=None,
            force=force,
        )
        return ProjectResponse(**project)
    except ValueError as e:
        raise ValidationError(str(e))
    finally:
        await svc.cleanup()


@router.get("/{project_id}/stage-options")
async def get_project_stage_options(project_id: str):
    """Return allowed next transitions and rollback targets for UI rendering."""
    validate_object_id(project_id, "Project")
    settings = load_settings()
    svc = ProjectStorageService(settings)
    await svc.initialize()
    try:
        return await svc.get_stage_options(project_id)
    finally:
        await svc.cleanup()


@router.post("/{project_id}/uploads")
async def upload_project_document(project_id: str, file: UploadFile = File(...)):
    """
    Upload a document and ingest it into MongoDB, scoped to the project.

    Supported: PDF, DOCX, PPTX (Docling-supported formats).
    """
    validate_object_id(project_id, "Project")
    settings = load_settings()

    # Ensure project exists (avoid ingesting into a non-existent project_id)
    svc = ProjectStorageService(settings)
    await svc.initialize()
    try:
        await svc.get_project(project_id)
    except ValueError as e:
        if "not found" in str(e).lower():
            raise NotFoundError("Project", project_id)
        raise
    finally:
        await svc.cleanup()

    filename = file.filename or "upload"
    ext = os.path.splitext(filename)[1].lower()
    allowed = {".pdf", ".docx", ".pptx"}
    if ext not in allowed:
        raise ValidationError(
            f"Unsupported file type '{ext}'. Supported: PDF, DOCX, PPTX."
        )

    # Save to a temp file so Docling can read it by path.
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = os.path.join(tmpdir, f"upload{ext}")
        content = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(content)

        # Ingest using existing pipeline (no clean)
        pipeline = DocumentIngestionPipeline(
            config=IngestionConfig(),
            documents_folder=tmpdir,
            clean_before_ingest=False,
            dry_run=False,
        )
        await pipeline.initialize()
        try:
            result = await pipeline.ingest_file(
                tmp_path, extra_metadata={"project_id": ObjectId(project_id)}
            )
        finally:
            await pipeline.close()

    return {
        "project_id": project_id,
        "document_id": result.document_id,
        "title": result.title,
        "chunks_created": result.chunks_created,
        "errors": result.errors,
    }


