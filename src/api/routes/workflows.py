"""Workflow template management endpoints."""

import logging
from typing import List, Optional

from fastapi import APIRouter, Query
from fastapi.responses import Response

from src.models.workflow_models import (
    WorkflowCreateRequest,
    WorkflowDuplicateRequest,
    WorkflowListItem,
    WorkflowResponse,
    WorkflowType,
)
from src.services.workflow_service import WorkflowService
from src.settings import load_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


@router.get("", response_model=List[WorkflowListItem])
async def list_workflows(
    workflow_type: Optional[str] = Query(default=None, description="Filter by workflow type")
):
    """List all workflow templates, optionally filtered by type."""
    settings = load_settings()
    service = WorkflowService(settings)
    await service.initialize()
    try:
        if workflow_type:
            templates = await service.list_by_type(workflow_type)
        else:
            templates = await service.list_templates()
        return [WorkflowListItem(**t) for t in templates]
    finally:
        await service.cleanup()


@router.post("", response_model=WorkflowResponse, status_code=201)
async def create_workflow(request: WorkflowCreateRequest):
    """Create a new workflow template."""
    settings = load_settings()
    service = WorkflowService(settings)
    await service.initialize()
    try:
        data = request.model_dump()
        # Convert stage models to dicts
        data["stages"] = [s.model_dump() for s in request.stages]
        result = await service.create(data)
        return WorkflowResponse(**result)
    finally:
        await service.cleanup()


# IMPORTANT: static routes must be defined BEFORE /{workflow_id} routes
@router.post("/seed-default", response_model=WorkflowResponse)
async def seed_default_workflow():
    """Seed the default workflow template. Idempotent."""
    settings = load_settings()
    service = WorkflowService(settings)
    await service.initialize()
    try:
        result = await service.seed_default()
        return WorkflowResponse(**result)
    finally:
        await service.cleanup()


@router.post("/seed-default-for-type", response_model=WorkflowResponse)
async def seed_default_for_type_route(
    workflow_type: str = Query(..., description="project|qa_session|qa_pair|agentic")
):
    """Seed the default workflow template for a given type. Idempotent."""
    settings = load_settings()
    service = WorkflowService(settings)
    await service.initialize()
    try:
        result = await service.seed_default_for_type(workflow_type)
        return WorkflowResponse(**result)
    finally:
        await service.cleanup()


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(workflow_id: str):
    """Get a workflow template by ID."""
    settings = load_settings()
    service = WorkflowService(settings)
    await service.initialize()
    try:
        result = await service.get(workflow_id)
        return WorkflowResponse(**result)
    finally:
        await service.cleanup()


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(workflow_id: str, request: WorkflowCreateRequest):
    """Update a workflow template (full replacement)."""
    settings = load_settings()
    service = WorkflowService(settings)
    await service.initialize()
    try:
        data = request.model_dump()
        data["stages"] = [s.model_dump() for s in request.stages]
        result = await service.update(workflow_id, data)
        return WorkflowResponse(**result)
    finally:
        await service.cleanup()


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(workflow_id: str):
    """Delete a workflow template."""
    settings = load_settings()
    service = WorkflowService(settings)
    await service.initialize()
    try:
        await service.delete(workflow_id)
        return Response(status_code=204)
    finally:
        await service.cleanup()


@router.post(
    "/{workflow_id}/duplicate", response_model=WorkflowResponse, status_code=201
)
async def duplicate_workflow(
    workflow_id: str, request: WorkflowDuplicateRequest
):
    """Duplicate a workflow template."""
    settings = load_settings()
    service = WorkflowService(settings)
    await service.initialize()
    try:
        result = await service.duplicate(workflow_id, new_name=request.name)
        return WorkflowResponse(**result)
    finally:
        await service.cleanup()
