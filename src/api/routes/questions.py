"""Question processing endpoints."""

import logging
import json
import time
from fastapi import APIRouter, HTTPException
from bson import ObjectId

from src.api.models import QuestionProcessRequest, QuestionProcessResponse, QAPair, Citation
from src.api.validators import validate_object_id, validate_user_role
from src.api.exceptions import NotFoundError, ValidationError, ServiceUnavailableError
from src.api.middleware import request_id_var
from src.services.qa_storage import QAStorageService
from src.settings import load_settings
from src.agent import process_question_batch_standalone
from src.dependencies import AgentDependencies

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["questions"])


@router.post("/{session_id}/questions", response_model=QuestionProcessResponse)
async def process_questions(session_id: str, request: QuestionProcessRequest):
    """Process questions and generate answers."""
    request_id = request_id_var.get() or 'unknown'
    start_time = time.time()
    
    logger.info(
        f"process_questions endpoint called: session_id={session_id}, "
        f"question_count={len(request.questions)}, user_role={request.user_role}, "
        f"include_history={request.include_history}",
        extra={
            'request_id': request_id,
            'session_id': session_id,
            'question_count': len(request.questions),
            'user_role': request.user_role,
            'include_history': request.include_history
        }
    )
    
    # Validate ObjectId format
    try:
        validate_object_id(session_id, "Session")
        logger.debug(f"Session ID validation passed: {session_id}", extra={'request_id': request_id})
    except Exception as e:
        logger.error(f"Session ID validation failed: {e}", extra={'request_id': request_id})
        raise
    
    # Validate user_role
    try:
        user_role = validate_user_role(request.user_role)
        logger.debug(f"User role validation passed: {user_role}", extra={'request_id': request_id})
    except Exception as e:
        logger.error(f"User role validation failed: {e}", extra={'request_id': request_id})
        raise
    
    # Verify session exists and user_role matches
    settings = load_settings()
    qa_storage = QAStorageService(settings)
    await qa_storage.initialize()
    
    try:
        logger.debug(f"Fetching session: {session_id}", extra={'request_id': request_id})
        session = await qa_storage.get_session(session_id)
        session_user_role = session.get("user_role", "junior")
        logger.info(
            f"Session retrieved: session_id={session_id}, session_user_role={session_user_role}",
            extra={'request_id': request_id, 'session_id': session_id}
        )
        
        # Verify user_role matches session's user_role
        if user_role != session_user_role:
            error_msg = f"User role mismatch: request has '{user_role}' but session has '{session_user_role}'"
            logger.warning(error_msg, extra={'request_id': request_id, 'session_id': session_id})
            raise ValidationError(error_msg)
        
        # Override session_id from request with path parameter
        request.session_id = session_id

        # Validate document existence before processing
        logger.debug("Initializing AgentDependencies for document validation", extra={'request_id': request_id})
        agent_deps = AgentDependencies()
        await agent_deps.initialize()
        
        try:
            doc_count = await agent_deps.db[settings.mongodb_collection_documents].count_documents({})
            chunk_count = await agent_deps.db[settings.mongodb_collection_chunks].count_documents({})
            
            logger.info(
                f"Pre-processing validation: {doc_count} documents, {chunk_count} chunks",
                extra={
                    'request_id': request_id,
                    'doc_count': doc_count,
                    'chunk_count': chunk_count
                }
            )
            
            if doc_count == 0:
                raise ServiceUnavailableError(
                    "No documents found in database. Please run document ingestion first.",
                    detail="Run: uv run python -m src.ingestion.ingest -d ./documents"
                )
            
            if chunk_count == 0:
                raise ServiceUnavailableError(
                    "No chunks found in database. Please run document ingestion first.",
                    detail="Run: uv run python -m src.ingestion.ingest -d ./documents"
                )
            
            # Check if chunks have embeddings (sample check)
            sample_chunk = await agent_deps.db[settings.mongodb_collection_chunks].find_one({})
            if sample_chunk and not sample_chunk.get("embedding"):
                raise ServiceUnavailableError(
                    "Chunks found but embeddings are missing. Please re-run document ingestion.",
                    detail="Run: uv run python -m src.ingestion.ingest -d ./documents"
                )
            
            # Check for vector index
            try:
                indexes = []
                async for idx in agent_deps.db[settings.mongodb_collection_chunks].list_indexes():
                    indexes.append(idx)
                
                vector_index_name = settings.mongodb_vector_index
                index_names = [idx.get("name", "") for idx in indexes]
                has_vector_index = any(idx.get("type") == "vectorSearch" for idx in indexes)
                
                if vector_index_name not in index_names and not has_vector_index:
                    logger.warning(
                        f"Vector index '{vector_index_name}' not found. "
                        "Vector search may fail. Create index in Atlas UI."
                    )
                    # Don't fail here, just warn - the search will fail gracefully
            except Exception as idx_error:
                logger.warning(f"Could not verify vector index: {idx_error}")
        finally:
            await agent_deps.cleanup()

        # Call the standalone function
        processing_start = time.time()
        logger.info(
            f"Calling process_question_batch_standalone: {len(request.questions)} questions",
            extra={'request_id': request_id, 'question_count': len(request.questions)}
        )
        
        try:
            result_str = await process_question_batch_standalone(
                questions=request.questions,
                session_id=request.session_id,
                user_role=user_role,
                include_history=request.include_history
            )
            processing_time = time.time() - processing_start
            logger.info(
                f"process_question_batch_standalone completed in {processing_time:.2f}s",
                extra={
                    'request_id': request_id,
                    'processing_time_ms': round(processing_time * 1000, 2)
                }
            )
        except Exception as e:
            processing_time = time.time() - processing_start
            logger.error(
                f"process_question_batch_standalone failed after {processing_time:.2f}s: {e}",
                extra={
                    'request_id': request_id,
                    'processing_time_ms': round(processing_time * 1000, 2),
                    'error': str(e),
                    'error_type': type(e).__name__
                },
                exc_info=True
            )
            raise

        # Parse result
        logger.debug("Parsing processing result", extra={'request_id': request_id})
        try:
            result_data = json.loads(result_str)
            logger.debug(
                f"Result parsed: questions_processed={result_data.get('questions_processed', 0)}, "
                f"qa_pairs_count={len(result_data.get('qa_pairs', []))}",
                extra={'request_id': request_id}
            )
        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse processing result: {e}, result_str length={len(result_str)}",
                extra={'request_id': request_id, 'result_preview': result_str[:500]},
                exc_info=True
            )
            raise
        
        # Check if processing returned an error
        if result_data.get("error"):
            error_msg = result_data.get("error", "Unknown error")
            recommendation = result_data.get("recommendation", "")
            detail = f"{error_msg}. {recommendation}" if recommendation else error_msg
            logger.error(
                f"Processing returned error: {error_msg}",
                extra={
                    'request_id': request_id,
                    'error': error_msg,
                    'recommendation': recommendation
                }
            )
            raise ServiceUnavailableError(
                "Question processing failed",
                detail=detail
            )

        # Convert to response model
        logger.debug(
            f"Converting {len(result_data.get('qa_pairs', []))} Q&A pairs to response model",
            extra={'request_id': request_id}
        )
        qa_pairs = []
        for idx, pair_data in enumerate(result_data.get("qa_pairs", [])):
            # Convert citations
            citations = []
            for cit in pair_data.get("citations", []):
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
            
            # Get answer value (could be 'answer' or 'final_answer')
            answer_value = pair_data.get("final_answer") or pair_data.get("answer", "")
            
            # Parse datetime strings if present
            created_at = None
            updated_at = None
            if pair_data.get("created_at"):
                try:
                    from datetime import datetime
                    created_at = datetime.fromisoformat(pair_data["created_at"].replace('Z', '+00:00'))
                except:
                    pass
            if pair_data.get("updated_at"):
                try:
                    from datetime import datetime
                    updated_at = datetime.fromisoformat(pair_data["updated_at"].replace('Z', '+00:00'))
                except:
                    pass
            
            try:
                qa_pairs.append(QAPair(
                    _id=pair_data.get("_id") or pair_data.get("qa_pair_id"),  # Use _id if available, fallback to qa_pair_id
                    session_id=pair_data.get("session_id") or session_id,
                    question=pair_data["question"],
                    original_answer=pair_data.get("original_answer") or answer_value,
                    edited_answer=pair_data.get("edited_answer"),
                    final_answer=answer_value,
                    rating_good=pair_data.get("rating_good"),
                    rated_at=pair_data.get("rated_at"),
                    rated_by=pair_data.get("rated_by"),
                    was_edited=bool(pair_data.get("was_edited", False)),
                    edited_at=pair_data.get("edited_at"),
                    review=pair_data.get("review"),
                    citations=citations,
                    qa_pair_id=pair_data.get("_id") or pair_data.get("qa_pair_id"),
                    question_index=pair_data.get("question_index", 0),
                    outcome_status=pair_data.get("outcome_status"),
                    created_at=created_at,
                    updated_at=updated_at,
                ))
            except Exception as e:
                logger.error(
                    f"Failed to convert Q&A pair {idx}: {e}",
                    extra={'request_id': request_id, 'pair_index': idx, 'pair_data': pair_data},
                    exc_info=True
                )
                raise

        total_time = time.time() - start_time
        logger.info(
            f"process_questions completed successfully: {len(qa_pairs)} Q&A pairs in {total_time:.2f}s",
            extra={
                'request_id': request_id,
                'session_id': session_id,
                'qa_pairs_count': len(qa_pairs),
                'total_time_ms': round(total_time * 1000, 2)
            }
        )
        
        return QuestionProcessResponse(
            questions_processed=result_data.get("questions_processed", 0),
            qa_pairs=qa_pairs
        )
    except ValueError as e:
        total_time = time.time() - start_time
        if "not found" in str(e).lower():
            logger.warning(
                f"Session not found: {session_id}",
                extra={'request_id': request_id, 'session_id': session_id, 'total_time_ms': round(total_time * 1000, 2)}
            )
            raise NotFoundError("Session", session_id)
        logger.error(
            f"ValueError in process_questions: {e}",
            extra={'request_id': request_id, 'session_id': session_id, 'error': str(e)},
            exc_info=True
        )
        raise
    except json.JSONDecodeError as e:
        total_time = time.time() - start_time
        logger.exception(
            f"Error parsing question processing result: {e}",
            extra={
                'request_id': request_id,
                'session_id': session_id,
                'total_time_ms': round(total_time * 1000, 2),
                'error': str(e)
            }
        )
        raise ValidationError("Failed to parse processing result", detail=str(e))
    except Exception as e:
        total_time = time.time() - start_time
        logger.exception(
            f"Unexpected error in process_questions: {e}",
            extra={
                'request_id': request_id,
                'session_id': session_id,
                'total_time_ms': round(total_time * 1000, 2),
                'error_type': type(e).__name__,
                'error': str(e)
            }
        )
        raise
    finally:
        await qa_storage.cleanup()

