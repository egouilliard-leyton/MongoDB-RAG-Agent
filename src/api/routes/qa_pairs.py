"""Q&A pair endpoints."""

import logging
from typing import List
from fastapi import APIRouter, HTTPException
from bson import ObjectId

from src.api.models import QAPairUpdateRequest, QAPair, Citation
from src.api.validators import validate_object_id
from src.api.exceptions import NotFoundError
from src.services.qa_storage import QAStorageService
from src.settings import load_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["qa-pairs"])


@router.get("/sessions/{session_id}/qa-pairs", response_model=List[QAPair])
async def get_session_qa_pairs(session_id: str):
    """Get all Q&A pairs for a session."""
    # Validate ObjectId format
    validate_object_id(session_id, "Session")
    
    settings = load_settings()
    qa_storage = QAStorageService(settings)
    await qa_storage.initialize()

    try:
        qa_pairs_raw = await qa_storage.get_session_qa_pairs(session_id)

        # Convert to QAPair models
        qa_pairs = []
        for pair_dict in qa_pairs_raw:
            # Convert citations if they exist
            citations = []
            if pair_dict.get("citations"):
                for cit in pair_dict["citations"]:
                    # Handle both old format (title) and new format (document_title)
                    citation_data = {
                        "citation_number": cit.get("citation_number", 0),
                        "title": cit.get("title") or cit.get("document_title", ""),
                        "source": cit.get("source", ""),
                        "document_id": cit.get("document_id", ""),
                        "document_title": cit.get("document_title") or cit.get("title"),
                        "similarity": cit.get("similarity"),
                        "chunk_id": cit.get("chunk_id"),
                    }
                    citations.append(Citation(**citation_data))
            
            qa_pair = QAPair(
                _id=pair_dict.get("_id"),
                session_id=pair_dict.get("session_id"),
                question=pair_dict.get("question", ""),
                original_answer=pair_dict.get("original_answer"),
                edited_answer=pair_dict.get("edited_answer"),
                final_answer=pair_dict.get("final_answer", pair_dict.get("answer", "")),
                citations=citations,
                qa_pair_id=pair_dict.get("_id"),
                question_index=pair_dict.get("question_index", 0),
                outcome_status=pair_dict.get("outcome_status"),
                created_at=pair_dict.get("created_at"),
                updated_at=pair_dict.get("updated_at"),
            )
            qa_pairs.append(qa_pair)

        return qa_pairs
    except ValueError as e:
        if "not found" in str(e).lower():
            raise NotFoundError("Session", session_id)
        raise
    finally:
        await qa_storage.cleanup()


@router.put("/qa-pairs/{qa_pair_id}", status_code=200)
async def update_qa_pair(qa_pair_id: str, request: QAPairUpdateRequest):
    """Update a Q&A pair answer."""
    # Validate ObjectId format
    validate_object_id(qa_pair_id, "Q&A pair")
    
    settings = load_settings()
    qa_storage = QAStorageService(settings)
    await qa_storage.initialize()

    try:
        await qa_storage.update_answer(
            qa_pair_id=qa_pair_id,
            edited_answer=request.edited_answer
        )
        return {"message": "Q&A pair updated successfully"}
    finally:
        await qa_storage.cleanup()

