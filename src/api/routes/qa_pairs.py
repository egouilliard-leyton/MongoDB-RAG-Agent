"""Q&A pair endpoints."""

import logging
from typing import List
from fastapi import APIRouter

from src.api.models import (
    QAPairUpdateRequest,
    QAPairRatingUpdateRequest,
    QAPairOutcomeUpdateRequest,
    QAPair,
    Citation,
)
from src.api.validators import validate_object_id
from src.api.exceptions import NotFoundError
from src.services.qa_storage import QAStorageService
from src.services.exemplar_service import ExemplarService
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
                _id=pair_dict.get("_id") or pair_dict.get("qa_pair_id"),
                session_id=pair_dict.get("session_id"),
                question=pair_dict.get("question", ""),
                original_answer=pair_dict.get("original_answer"),
                edited_answer=pair_dict.get("edited_answer"),
                final_answer=pair_dict.get("final_answer", pair_dict.get("answer", "")),
                rating_good=pair_dict.get("rating_good"),
                rated_at=pair_dict.get("rated_at"),
                rated_by=pair_dict.get("rated_by"),
                was_edited=bool(pair_dict.get("was_edited", False)),
                edited_at=pair_dict.get("edited_at"),
                review=pair_dict.get("review"),
                citations=citations,
                qa_pair_id=pair_dict.get("qa_pair_id") or pair_dict.get("_id"),
                question_index=pair_dict.get("question_index", 0),
                outcome_status=pair_dict.get("outcome_status"),
                is_exemplar=bool(pair_dict.get("is_exemplar", False)),
                promoted_to_exemplar_at=pair_dict.get("promoted_to_exemplar_at"),
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


@router.put("/qa-pairs/{qa_pair_id}/rating", status_code=200)
async def update_qa_pair_rating(qa_pair_id: str, request: QAPairRatingUpdateRequest):
    """
    Update consultant rating for a Q&A pair.

    When a Q&A pair is rated as good (rating_good=True), the system will
    automatically check if it meets exemplar criteria and promote it if eligible.
    Exemplar criteria: good rating + good verdict + confidence >= 0.8 + citations >= 2.
    """
    validate_object_id(qa_pair_id, "Q&A pair")

    settings = load_settings()
    qa_storage = QAStorageService(settings)
    exemplar_service = ExemplarService(settings)
    await qa_storage.initialize()
    await exemplar_service.initialize()

    promoted_to_exemplar = False
    try:
        await qa_storage.update_rating(
            qa_pair_id=qa_pair_id,
            rating_good=request.rating_good
        )

        # Auto-promotion trigger: check and promote to exemplar if rating is good
        if request.rating_good is True:
            promoted_to_exemplar = await exemplar_service.check_and_promote_if_eligible(
                qa_pair_id
            )

        return {
            "message": "Q&A pair rating updated successfully",
            "promoted_to_exemplar": promoted_to_exemplar
        }
    except ValueError as e:
        if "not found" in str(e).lower():
            raise NotFoundError("Q&A pair", qa_pair_id)
        raise
    finally:
        await qa_storage.cleanup()
        await exemplar_service.cleanup()


@router.put("/qa-pairs/{qa_pair_id}/outcome", status_code=200)
async def update_qa_pair_outcome(qa_pair_id: str, request: QAPairOutcomeUpdateRequest):
    """
    Update outcome status for a Q&A pair.

    Args:
        qa_pair_id: Q&A pair ID (MongoDB ObjectId as string)
        request: Request body with outcome_status ('successful', 'partial', or 'negative')

    Returns:
        Success message
    """
    validate_object_id(qa_pair_id, "Q&A pair")

    settings = load_settings()
    qa_storage = QAStorageService(settings)
    await qa_storage.initialize()

    try:
        await qa_storage.set_outcome(
            qa_pair_id=qa_pair_id,
            outcome_status=request.outcome_status
        )
        return {"message": "Q&A pair outcome updated successfully"}
    except ValueError as e:
        if "not found" in str(e).lower():
            raise NotFoundError("Q&A pair", qa_pair_id)
        raise
    finally:
        await qa_storage.cleanup()

