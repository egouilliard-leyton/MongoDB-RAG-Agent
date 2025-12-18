"""Export endpoints for Q&A sessions."""

import logging
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from bson import ObjectId

from src.api.validators import validate_object_id
from src.api.exceptions import NotFoundError
from src.services.export_service import ExportService
from src.services.qa_storage import QAStorageService
from src.settings import load_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["export"])


@router.post("/{session_id}/export")
async def export_session(
    session_id: str,
    format: str = Query(default="markdown", regex="^(markdown|pdf|docx)$", description="Export format: markdown, pdf, or docx")
):
    """
    Export a Q&A session to the specified format.
    
    Args:
        session_id: Session ID to export
        format: Export format (markdown, pdf, or docx)
    
    Returns:
        Response with exported document
    
    Raises:
        HTTPException: If session not found or export fails
    """
    # Validate ObjectId format
    validate_object_id(session_id, "Session")
    
    settings = load_settings()
    export_service = ExportService(settings)
    
    try:
        # Export session
        file_bytes, mime_type, filename = await export_service.export_session(session_id, format)
        
        # Track export timestamp (Task 3.7)
        qa_storage = QAStorageService(settings)
        await qa_storage.initialize()
        try:
            from datetime import datetime
            await qa_storage.db[settings.mongodb_collection_qa_sessions].update_one(
                {"_id": ObjectId(session_id)},
                {"$set": {"exported_at": datetime.utcnow()}}
            )
        except Exception as e:
            logger.warning(f"Failed to track export timestamp for session {session_id}: {e}")
        finally:
            await qa_storage.cleanup()
        
        # Return response with file content
        return Response(
            content=file_bytes,
            media_type=mime_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except ValueError as e:
        if "not found" in str(e).lower() or "no Q&A pairs" in str(e).lower():
            raise NotFoundError("Session", session_id)
        raise

