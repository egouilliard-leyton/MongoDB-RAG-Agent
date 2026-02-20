"""Session management endpoints."""

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from bson import ObjectId

from src.api.models import (
    SessionCreateRequest,
    SessionResponse,
    FollowUpSessionRequest,
    OutcomeUpdateRequest
)
from src.api.validators import validate_object_id
from src.api.exceptions import NotFoundError
from src.services.qa_storage import QAStorageService
from src.services.company_extractor import CompanyExtractor
from src.settings import load_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(request: SessionCreateRequest):
    """Create a new Q&A session."""
    settings = load_settings()
    qa_storage = QAStorageService(settings)
    await qa_storage.initialize()

    try:
        # Validate project_id if provided
        if request.project_id:
            validate_object_id(request.project_id, "Project")

        # Extract company info if provided
        company_info = None
        if request.company_info:
            # If company_info is provided as string, try to extract structured info
            try:
                extractor = CompanyExtractor()
                company_info = await extractor.extract_company_info(request.company_info)
                # Remove None values
                company_info = {k: v for k, v in company_info.items() if v is not None}
            except Exception as e:
                logger.warning(f"Failed to extract company info from string: {e}")
                # Fallback: store as context if extraction fails
                company_info = {"context": request.company_info}
        elif request.name:
            # Try to extract company info from session name
            try:
                extractor = CompanyExtractor()
                company_info = await extractor.extract_company_info(request.name)
                # Remove None values
                company_info = {k: v for k, v in company_info.items() if v is not None}
            except Exception as e:
                logger.warning(f"Failed to extract company info: {e}")

        session_id = await qa_storage.create_session(
            name=request.name,
            user_role=request.user_role,
            company_info=company_info,
            project_id=request.project_id,
            tax_office_id=request.tax_office_id,
            region=request.region,
        )

        session = await qa_storage.get_session(session_id)
        return SessionResponse(**session)
    finally:
        await qa_storage.cleanup()


@router.get("", response_model=List[SessionResponse])
async def list_sessions(
    limit: int = Query(default=100, ge=1, le=1000),
    skip: int = Query(default=0, ge=0)
):
    """List Q&A sessions."""
    settings = load_settings()
    qa_storage = QAStorageService(settings)
    await qa_storage.initialize()

    try:
        sessions = await qa_storage.list_sessions(limit=limit, skip=skip)
        return [SessionResponse(**session) for session in sessions]
    finally:
        await qa_storage.cleanup()


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """Get a session by ID."""
    # Validate ObjectId format
    validate_object_id(session_id, "Session")
    
    settings = load_settings()
    qa_storage = QAStorageService(settings)
    await qa_storage.initialize()

    try:
        session = await qa_storage.get_session(session_id)
        return SessionResponse(**session)
    except ValueError as e:
        if "not found" in str(e).lower():
            raise NotFoundError("Session", session_id)
        raise
    finally:
        await qa_storage.cleanup()


@router.put("/{session_id}/outcome", status_code=200)
async def mark_session_outcome(session_id: str, request: OutcomeUpdateRequest):
    """Mark session outcome status."""
    # Validate ObjectId format
    validate_object_id(session_id, "Session")
    
    settings = load_settings()
    qa_storage = QAStorageService(settings)
    await qa_storage.initialize()

    try:
        await qa_storage.mark_session_outcome(
            session_id=session_id,
            outcome=request.outcome,
            determined_by=request.determined_by
        )
        return {"message": "Outcome updated successfully"}
    finally:
        await qa_storage.cleanup()


@router.post("/{session_id}/follow-up", response_model=SessionResponse, status_code=201)
async def create_follow_up_session(session_id: str, request: FollowUpSessionRequest):
    """Create a follow-up session."""
    # Validate ObjectId format
    validate_object_id(session_id, "Session")
    
    settings = load_settings()
    qa_storage = QAStorageService(settings)
    await qa_storage.initialize()

    try:
        # Get parent session to determine user_role
        parent_session = await qa_storage.get_session(session_id)
        user_role = parent_session.get("user_role", "junior")

        new_session_id = await qa_storage.create_follow_up_session(
            parent_session_id=session_id,
            new_questions=request.new_questions,
            user_role=user_role
        )

        new_session = await qa_storage.get_session(new_session_id)
        return SessionResponse(**new_session)
    except ValueError as e:
        if "not found" in str(e).lower():
            raise NotFoundError("Session", session_id)
        raise
    finally:
        await qa_storage.cleanup()

