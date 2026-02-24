"""Settings management API endpoints."""

import logging
from typing import List

from fastapi import APIRouter, HTTPException, Query

from src.models.settings_models import (
    SettingsResponse,
    SettingsUpdateRequest,
    SettingsVersion,
    ParameterSuggestion,
    PromptTestRequest,
    PromptTestResponse,
)
from src.services.settings_service import SettingsService
from src.settings import load_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _doc_to_response(doc: dict) -> SettingsResponse:
    """Convert a MongoDB settings document to a SettingsResponse."""
    return SettingsResponse(
        id=str(doc.get("_id", "")),
        version=doc["version"],
        main_system_prompt=doc["main_system_prompt"],
        follow_up_context_prompt=doc["follow_up_context_prompt"],
        qa_history_prompt=doc["qa_history_prompt"],
        stage_defaults=doc.get("stage_defaults", {}),
        default_match_count=doc["default_match_count"],
        max_match_count=doc["max_match_count"],
        enable_question_decomposition=doc["enable_question_decomposition"],
        enable_iterative_refinement=doc["enable_iterative_refinement"],
        enable_qa_history_search=doc["enable_qa_history_search"],
        rrf_k_constant=doc["rrf_k_constant"],
        qa_history_match_count=doc["qa_history_match_count"],
        llm_model=doc["llm_model"],
        llm_base_url=doc["llm_base_url"],
        embedding_model=doc["embedding_model"],
        show_full_citations=doc["show_full_citations"],
        updated_at=doc["updated_at"],
    )


@router.get("", response_model=SettingsResponse)
async def get_settings():
    """Get the current active settings."""
    settings = load_settings()
    svc = SettingsService(settings)
    await svc.initialize()
    try:
        doc = await svc.get_current()
        return _doc_to_response(doc)
    finally:
        await svc.cleanup()


@router.put("", response_model=SettingsResponse)
async def update_settings(request: SettingsUpdateRequest):
    """Update settings (partial). Archives current version."""
    settings = load_settings()
    svc = SettingsService(settings)
    await svc.initialize()
    try:
        changes = request.model_dump(exclude_none=True)
        # Serialize nested Pydantic models to dicts for MongoDB
        if "stage_defaults" in changes:
            sd = changes["stage_defaults"]
            if hasattr(sd, "model_dump"):
                changes["stage_defaults"] = sd.model_dump()
        doc = await svc.update(changes)
        return _doc_to_response(doc)
    finally:
        await svc.cleanup()


@router.get("/history", response_model=List[SettingsVersion])
async def get_settings_history(
    limit: int = Query(default=20, ge=1, le=100),
):
    """Get settings version history."""
    settings = load_settings()
    svc = SettingsService(settings)
    await svc.initialize()
    try:
        versions = await svc.get_history(limit=limit)
        return [SettingsVersion(**v) for v in versions]
    finally:
        await svc.cleanup()


@router.post("/restore/{version}", response_model=SettingsResponse)
async def restore_settings(version: int):
    """Restore a historical settings version."""
    settings = load_settings()
    svc = SettingsService(settings)
    await svc.initialize()
    try:
        doc = await svc.restore(version)
        return _doc_to_response(doc)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    finally:
        await svc.cleanup()


@router.post("/prompt-test", response_model=PromptTestResponse)
async def test_prompt(request: PromptTestRequest):
    """Test a system prompt against a sample question."""
    settings = load_settings()
    svc = SettingsService(settings)
    await svc.initialize()
    try:
        result = await svc.test_prompt(request.prompt, request.test_question)
        return PromptTestResponse(**result)
    finally:
        await svc.cleanup()


@router.get("/suggestions", response_model=List[ParameterSuggestion])
async def get_suggestions():
    """Get AI-generated parameter tuning suggestions."""
    settings = load_settings()
    svc = SettingsService(settings)
    await svc.initialize()
    try:
        suggestions = await svc.get_suggestions()
        return [ParameterSuggestion(**s) for s in suggestions]
    finally:
        await svc.cleanup()


@router.post("/suggestions/{suggestion_id}/apply", response_model=SettingsResponse)
async def apply_suggestion(suggestion_id: str):
    """Apply a parameter suggestion."""
    settings = load_settings()
    svc = SettingsService(settings)
    await svc.initialize()
    try:
        doc = await svc.apply_suggestion(suggestion_id)
        return _doc_to_response(doc)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    finally:
        await svc.cleanup()
