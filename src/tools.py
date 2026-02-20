"""Search tools for MongoDB RAG Agent."""

import asyncio
import logging
import time
from typing import Optional, List, Dict, Any
from pydantic_ai import RunContext
from pydantic import BaseModel, Field
from pymongo.errors import OperationFailure
from bson import ObjectId

from src.dependencies import AgentDependencies
from src.settings import load_settings

logger = logging.getLogger(__name__)


def build_metadata_filter(
    project_id: Optional[str] = None,
    document_type: Optional[str] = None,
    author: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    keywords: Optional[List[str]] = None,
    section_type: Optional[str] = None,
    industry: Optional[str] = None,
    tax_office_id: Optional[int] = None,
    region: Optional[str] = None
) -> Dict[str, Any]:
    """
    Build MongoDB filter query from metadata parameters.

    Args:
        project_id: Filter by project ID (ObjectId as string)
        document_type: Filter by document type (e.g., "KDIP2", "KDIB1-3")
        author: Filter by author
        date_from: Filter by document date (from, inclusive)
        date_to: Filter by document date (to, inclusive)
        keywords: Filter by keywords (any match)
        section_type: Filter by section type (e.g., "przepis", "zagadnienie")
        industry: Filter by industry classification (e.g., "IT", "Construction")
        tax_office_id: Filter by tax office ID (kodjednostki)
        region: Filter by region/voivodeship (e.g., "mazowieckie", "śląskie")

    Returns:
        MongoDB filter dictionary
    """
    filter_query = {}

    if project_id:
        try:
            filter_query["metadata.project_id"] = ObjectId(project_id)
        except Exception:
            # If invalid id, filter to impossible value to avoid leakage across projects
            filter_query["metadata.project_id"] = ObjectId()

    if document_type:
        filter_query["metadata.document_type"] = document_type

    if author:
        filter_query["metadata.author"] = author

    if date_from or date_to:
        date_filter = {}
        if date_from:
            date_filter["$gte"] = date_from
        if date_to:
            date_filter["$lte"] = date_to
        filter_query["metadata.document_date"] = date_filter

    if keywords:
        # Match any keyword in the array
        filter_query["metadata.slowa_kluczowe"] = {"$in": keywords}

    if section_type:
        filter_query["metadata.section_type"] = section_type

    if industry:
        filter_query["metadata.industry"] = industry

    if tax_office_id is not None:
        filter_query["metadata.tax_office_id"] = tax_office_id

    if region:
        filter_query["metadata.region"] = region

    return filter_query


class SearchResult(BaseModel):
    """Model for search results."""

    chunk_id: str = Field(..., description="MongoDB ObjectId of chunk as string")
    document_id: str = Field(..., description="Parent document ObjectId as string")
    content: str = Field(..., description="Chunk text content")
    similarity: float = Field(..., description="Relevance score (0-1)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Chunk metadata")
    document_title: str = Field(..., description="Title from document lookup")
    document_source: str = Field(..., description="Source from document lookup")


def _truncate_for_log(value: Any, max_len: int = 120) -> str:
    """Best-effort string truncation for safe, compact logs."""
    try:
        s = str(value)
    except Exception:
        s = "<unprintable>"
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def _summarize_search_results_for_log(
    results: List[SearchResult],
    max_items: int = 3,
) -> List[Dict[str, Any]]:
    """
    Build a compact, copy-friendly summary of search results for INFO logs.

    Goal: allow quick verification of which MongoDB docs were retrieved without
    dumping full chunk content into logs.
    """
    summary: List[Dict[str, Any]] = []
    for r in (results or [])[: max(0, max_items)]:
        summary.append(
            {
                "document_id": _truncate_for_log(r.document_id, 48),
                "chunk_id": _truncate_for_log(r.chunk_id, 48),
                "title": _truncate_for_log(r.document_title, 120),
                "source": _truncate_for_log(r.document_source, 120),
                "similarity": round(float(r.similarity), 4) if r.similarity is not None else None,
            }
        )
    return summary


async def semantic_search(
    ctx: RunContext[AgentDependencies],
    query: str,
    match_count: Optional[int] = None,
    project_id: Optional[str] = None,
    document_type: Optional[str] = None,
    author: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    keywords: Optional[List[str]] = None,
    section_type: Optional[str] = None,
    industry: Optional[str] = None,
    tax_office_id: Optional[int] = None,
    region: Optional[str] = None
) -> List[SearchResult]:
    """
    Perform pure semantic search using MongoDB vector similarity with optional metadata filtering.

    Args:
        ctx: Agent runtime context with dependencies
        query: Search query text
        match_count: Number of results to return (default: 10)
        project_id: Filter by project ID (ObjectId as string)
        document_type: Filter by document type (e.g., "KDIP2", "KDIB1-3")
        author: Filter by author
        date_from: Filter by document date (from, inclusive)
        date_to: Filter by document date (to, inclusive)
        keywords: Filter by keywords (any match)
        section_type: Filter by section type (e.g., "przepis", "zagadnienie")
        industry: Filter by industry classification (e.g., "IT", "Construction")
        tax_office_id: Filter by tax office ID (kodjednostki)
        region: Filter by region/voivodeship (e.g., "mazowieckie", "śląskie")

    Returns:
        List of search results ordered by similarity

    Raises:
        OperationFailure: If MongoDB operation fails (e.g., missing index)
    """
    try:
        deps = ctx.deps

        # Use default if not specified
        if match_count is None:
            match_count = deps.settings.default_match_count

        # Validate match count
        match_count = min(match_count, deps.settings.max_match_count)

        # Generate embedding for query (already returns list[float])
        query_embedding = await deps.get_embedding(query)

        # Build metadata filter
        metadata_filter = build_metadata_filter(
            project_id=project_id,
            document_type=document_type,
            author=author,
            date_from=date_from,
            date_to=date_to,
            keywords=keywords,
            section_type=section_type,
            industry=industry,
            tax_office_id=tax_office_id,
            region=region
        )

        # Build MongoDB aggregation pipeline
        pipeline = []

        # Add $match stage before $vectorSearch if filters are specified
        # Note: $vectorSearch must be the first stage, so we filter after
        # For vector search, we'll filter in a $match stage after $vectorSearch
        pipeline.append({
            "$vectorSearch": {
                "index": deps.settings.mongodb_vector_index,
                "queryVector": query_embedding,
                "path": "embedding",
                "numCandidates": 100,  # Search space (10x limit is good default)
                "limit": match_count * 2 if metadata_filter else match_count  # Over-fetch if filtering
            }
        })

        # Add $match stage after vector search to apply metadata filters
        if metadata_filter:
            pipeline.append({"$match": metadata_filter})
        
        pipeline.append({
            "$lookup": {
                "from": deps.settings.mongodb_collection_documents,
                "localField": "document_id",
                "foreignField": "_id",
                "as": "document_info"
            }
        })
        pipeline.append({
            "$unwind": "$document_info"
        })
        pipeline.append({
            "$project": {
                "chunk_id": "$_id",
                "document_id": 1,
                "content": 1,
                "similarity": {"$meta": "vectorSearchScore"},
                "metadata": 1,
                "document_title": "$document_info.title",
                "document_source": "$document_info.source"
            }
        })

        # Execute aggregation
        collection = deps.db[deps.settings.mongodb_collection_chunks]
        cursor = await collection.aggregate(pipeline)
        results = [doc async for doc in cursor][:match_count]

        # Convert to SearchResult objects (ObjectId → str conversion)
        search_results = [
            SearchResult(
                chunk_id=str(doc['chunk_id']),
                document_id=str(doc['document_id']),
                content=doc['content'],
                similarity=doc['similarity'],
                metadata=doc.get('metadata', {}),
                document_title=doc['document_title'],
                document_source=doc['document_source']
            )
            for doc in results
        ]

        logger.info(
            f"semantic_search_completed: query='{query[:100]}', results={len(search_results)}, match_count={match_count}",
            extra={
                "query": query[:200],
                "result_count": len(search_results),
                "match_count": match_count,
                "project_id": project_id,
                "top_results": _summarize_search_results_for_log(search_results, max_items=3),
            },
        )

        return search_results

    except OperationFailure as e:
        error_code = e.code if hasattr(e, 'code') else None
        logger.error(
            f"semantic_search_failed: query={query}, error={str(e)}, code={error_code}"
        )
        # Return empty list on error (graceful degradation)
        return []
    except Exception as e:
        logger.exception(f"semantic_search_error: query={query}, error={str(e)}")
        return []


async def text_search(
    ctx: RunContext[AgentDependencies],
    query: str,
    match_count: Optional[int] = None,
    project_id: Optional[str] = None,
    document_type: Optional[str] = None,
    author: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    keywords: Optional[List[str]] = None,
    section_type: Optional[str] = None,
    industry: Optional[str] = None,
    tax_office_id: Optional[int] = None,
    region: Optional[str] = None
) -> List[SearchResult]:
    """
    Perform full-text search using MongoDB Atlas Search with optional metadata filtering.

    Uses $search operator for keyword matching, fuzzy matching, and phrase matching.
    Works on all Atlas tiers including M0 (free tier).

    Args:
        ctx: Agent runtime context with dependencies
        query: Search query text
        match_count: Number of results to return (default: 10)
        project_id: Filter by project ID (ObjectId as string)
        document_type: Filter by document type (e.g., "KDIP2", "KDIB1-3")
        author: Filter by author
        date_from: Filter by document date (from, inclusive)
        date_to: Filter by document date (to, inclusive)
        keywords: Filter by keywords (any match)
        section_type: Filter by section type (e.g., "przepis", "zagadnienie")
        industry: Filter by industry classification (e.g., "IT", "Construction")
        tax_office_id: Filter by tax office ID (kodjednostki)
        region: Filter by region/voivodeship (e.g., "mazowieckie", "śląskie")

    Returns:
        List of search results ordered by text relevance

    Raises:
        OperationFailure: If MongoDB operation fails (e.g., missing index)
    """
    try:
        deps = ctx.deps

        # Use default if not specified
        if match_count is None:
            match_count = deps.settings.default_match_count

        # Validate match count
        match_count = min(match_count, deps.settings.max_match_count)

        # Build metadata filter
        metadata_filter = build_metadata_filter(
            project_id=project_id,
            document_type=document_type,
            author=author,
            date_from=date_from,
            date_to=date_to,
            keywords=keywords,
            section_type=section_type,
            industry=industry,
            tax_office_id=tax_office_id,
            region=region
        )

        # Build MongoDB Atlas Search aggregation pipeline
        pipeline = [
            {
                "$search": {
                    "index": deps.settings.mongodb_text_index,
                    "text": {
                        "query": query,
                        "path": "content",
                        "fuzzy": {
                            "maxEdits": 2,
                            "prefixLength": 3
                        }
                    }
                }
            },
        ]

        # Add $match stage after $search to apply metadata filters
        if metadata_filter:
            pipeline.append({"$match": metadata_filter})

        pipeline.append({
            "$limit": match_count * 2  # Over-fetch for better RRF results
        })
        pipeline.append({
            "$lookup": {
                "from": deps.settings.mongodb_collection_documents,
                "localField": "document_id",
                "foreignField": "_id",
                "as": "document_info"
            }
        })
        pipeline.append({
            "$unwind": "$document_info"
        })
        pipeline.append({
            "$project": {
                "chunk_id": "$_id",
                "document_id": 1,
                "content": 1,
                "similarity": {"$meta": "searchScore"},  # Text relevance score
                "metadata": 1,
                "document_title": "$document_info.title",
                "document_source": "$document_info.source"
            }
        })

        # Execute aggregation
        collection = deps.db[deps.settings.mongodb_collection_chunks]
        cursor = await collection.aggregate(pipeline)
        results = [doc async for doc in cursor][:match_count * 2]

        # Convert to SearchResult objects (ObjectId → str conversion)
        search_results = [
            SearchResult(
                chunk_id=str(doc['chunk_id']),
                document_id=str(doc['document_id']),
                content=doc['content'],
                similarity=doc['similarity'],
                metadata=doc.get('metadata', {}),
                document_title=doc['document_title'],
                document_source=doc['document_source']
            )
            for doc in results
        ]

        logger.info(
            f"text_search_completed: query='{query[:100]}', results={len(search_results)}, match_count={match_count}",
            extra={
                "query": query[:200],
                "result_count": len(search_results),
                "match_count": match_count,
                "project_id": project_id,
                "top_results": _summarize_search_results_for_log(search_results, max_items=3),
            },
        )

        return search_results

    except OperationFailure as e:
        error_code = e.code if hasattr(e, 'code') else None
        logger.error(
            f"text_search_failed: query={query}, error={str(e)}, code={error_code}"
        )
        # Return empty list on error (graceful degradation)
        return []
    except Exception as e:
        logger.exception(f"text_search_error: query={query}, error={str(e)}")
        return []


def reciprocal_rank_fusion(
    search_results_list: List[List[SearchResult]],
    k: int = 60
) -> List[SearchResult]:
    """
    Merge multiple ranked lists using Reciprocal Rank Fusion.

    RRF is a simple yet effective algorithm for combining results from different
    search methods. It works by scoring each document based on its rank position
    in each result list.

    Args:
        search_results_list: List of ranked result lists from different searches
        k: RRF constant (default: 60, standard in literature)

    Returns:
        Unified list of results sorted by combined RRF score

    Algorithm:
        For each document d appearing in result lists:
            RRF_score(d) = Σ(1 / (k + rank_i(d)))
        Where rank_i(d) is the position of document d in result list i.

    References:
        - Cormack et al. (2009): "Reciprocal Rank Fusion outperforms the best system"
        - Standard k=60 performs well across various datasets
    """
    # Build score dictionary by chunk_id
    rrf_scores: Dict[str, float] = {}
    chunk_map: Dict[str, SearchResult] = {}

    # Process each search result list
    for results in search_results_list:
        for rank, result in enumerate(results):
            chunk_id = result.chunk_id

            # Calculate RRF contribution: 1 / (k + rank)
            rrf_score = 1.0 / (k + rank)

            # Accumulate score (automatic deduplication)
            if chunk_id in rrf_scores:
                rrf_scores[chunk_id] += rrf_score
            else:
                rrf_scores[chunk_id] = rrf_score
                chunk_map[chunk_id] = result

    # Sort by combined RRF score (descending)
    sorted_chunks = sorted(
        rrf_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )

    # Build final result list with updated similarity scores
    merged_results = []
    for chunk_id, rrf_score in sorted_chunks:
        result = chunk_map[chunk_id]
        # Create new result with updated similarity (RRF score)
        merged_result = SearchResult(
            chunk_id=result.chunk_id,
            document_id=result.document_id,
            content=result.content,
            similarity=rrf_score,  # Combined RRF score
            metadata=result.metadata,
            document_title=result.document_title,
            document_source=result.document_source
        )
        merged_results.append(merged_result)

    logger.info(f"RRF merged {len(search_results_list)} result lists into {len(merged_results)} unique results")

    return merged_results


async def hybrid_search(
    ctx: RunContext[AgentDependencies],
    query: str,
    match_count: Optional[int] = None,
    text_weight: Optional[float] = None,
    project_id: Optional[str] = None,
    document_type: Optional[str] = None,
    author: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    keywords: Optional[List[str]] = None,
    section_type: Optional[str] = None,
    industry: Optional[str] = None,
    tax_office_id: Optional[int] = None,
    region: Optional[str] = None
) -> List[SearchResult]:
    """
    Perform hybrid search combining semantic and keyword matching with optional metadata filtering.

    Uses manual Reciprocal Rank Fusion (RRF) to merge vector and text search results.
    Works on all Atlas tiers including M0 (free tier) - no M10+ required!

    Args:
        ctx: Agent runtime context with dependencies
        query: Search query text
        match_count: Number of results to return (default: 10)
        text_weight: Weight for text matching (0-1, not used with RRF)
        project_id: Filter by project ID (ObjectId as string)
        document_type: Filter by document type (e.g., "KDIP2", "KDIB1-3")
        author: Filter by author
        date_from: Filter by document date (from, inclusive)
        date_to: Filter by document date (to, inclusive)
        keywords: Filter by keywords (any match)
        section_type: Filter by section type (e.g., "przepis", "zagadnienie")
        industry: Filter by industry classification (e.g., "IT", "Construction")
        tax_office_id: Filter by tax office ID (kodjednostki)
        region: Filter by region/voivodeship (e.g., "mazowieckie", "śląskie")

    Returns:
        List of search results sorted by combined RRF score

    Algorithm:
        1. Run semantic search (vector similarity)
        2. Run text search (keyword/fuzzy matching)
        3. Merge results using Reciprocal Rank Fusion
        4. Return top N results by combined score
    """
    try:
        deps = ctx.deps

        # Use defaults if not specified
        if match_count is None:
            match_count = deps.settings.default_match_count

        # Validate match count
        match_count = min(match_count, deps.settings.max_match_count)

        # Over-fetch for better RRF results (2x requested count)
        fetch_count = match_count * 2
        search_start_time = time.time()

        logger.info(
            f"hybrid_search starting: query='{query[:100]}', match_count={match_count}, fetch_count={fetch_count}",
            extra={
                'query': query[:200],
                'match_count': match_count,
                'fetch_count': fetch_count,
                'project_id': project_id,
                'filters': {
                    'document_type': document_type,
                    'author': author,
                    'date_from': date_from,
                    'date_to': date_to,
                    'keywords': keywords,
                    'section_type': section_type,
                    'industry': industry,
                    'tax_office_id': tax_office_id,
                    'region': region
                }
            }
        )

        # Run both searches concurrently for performance with metadata filters
        semantic_start = time.time()
        text_start = time.time()
        semantic_results, text_results = await asyncio.gather(
            semantic_search(
                ctx, query, fetch_count,
                project_id=project_id,
                document_type=document_type,
                author=author,
                date_from=date_from,
                date_to=date_to,
                keywords=keywords,
                section_type=section_type,
                industry=industry,
                tax_office_id=tax_office_id,
                region=region
            ),
            text_search(
                ctx, query, fetch_count,
                project_id=project_id,
                document_type=document_type,
                author=author,
                date_from=date_from,
                date_to=date_to,
                keywords=keywords,
                section_type=section_type,
                industry=industry,
                tax_office_id=tax_office_id,
                region=region
            ),
            return_exceptions=True  # Don't fail if one search errors
        )

        # Handle errors gracefully
        semantic_time = time.time() - semantic_start
        text_time = time.time() - text_start
        
        if isinstance(semantic_results, Exception):
            logger.warning(
                f"Semantic search failed: {semantic_results}, using text results only",
                extra={
                    'query': query[:200],
                    'semantic_time_ms': round(semantic_time * 1000, 2),
                    'error': str(semantic_results),
                    'error_type': type(semantic_results).__name__
                },
                exc_info=True
            )
            semantic_results = []
        else:
            logger.debug(
                f"Semantic search completed: {len(semantic_results)} results in {semantic_time:.2f}s",
                extra={
                    'query': query[:200],
                    'result_count': len(semantic_results),
                    'semantic_time_ms': round(semantic_time * 1000, 2)
                }
            )
            
        if isinstance(text_results, Exception):
            logger.warning(
                f"Text search failed: {text_results}, using semantic results only",
                extra={
                    'query': query[:200],
                    'text_time_ms': round(text_time * 1000, 2),
                    'error': str(text_results),
                    'error_type': type(text_results).__name__
                },
                exc_info=True
            )
            text_results = []
        else:
            logger.debug(
                f"Text search completed: {len(text_results)} results in {text_time:.2f}s",
                extra={
                    'query': query[:200],
                    'result_count': len(text_results),
                    'text_time_ms': round(text_time * 1000, 2)
                }
            )

        # If both failed, return empty
        if not semantic_results and not text_results:
            total_time = time.time() - search_start_time
            logger.error(
                "Both semantic and text search failed",
                extra={
                    'query': query[:200],
                    'total_time_ms': round(total_time * 1000, 2),
                    'semantic_time_ms': round(semantic_time * 1000, 2),
                    'text_time_ms': round(text_time * 1000, 2)
                }
            )
            return []

        # Merge results using Reciprocal Rank Fusion
        rrf_start = time.time()
        merged_results = reciprocal_rank_fusion(
            [semantic_results, text_results],
            k=60  # Standard RRF constant
        )
        rrf_time = time.time() - rrf_start

        # Return top N results
        final_results = merged_results[:match_count]
        total_time = time.time() - search_start_time

        logger.info(
            f"hybrid_search_completed: query='{query[:100]}', "
            f"semantic={len(semantic_results)}, text={len(text_results)}, "
            f"merged={len(merged_results)}, returned={len(final_results)} in {total_time:.2f}s",
            extra={
                'query': query[:200],
                'semantic_count': len(semantic_results),
                'text_count': len(text_results),
                'merged_count': len(merged_results),
                'returned_count': len(final_results),
                'project_id': project_id,
                'total_time_ms': round(total_time * 1000, 2),
                'rrf_time_ms': round(rrf_time * 1000, 2),
                'top_similarities': [r.similarity for r in final_results[:3]] if final_results else [],
                'top_results': _summarize_search_results_for_log(final_results, max_items=3),
            }
        )

        return final_results

    except Exception as e:
        total_time = time.time() - search_start_time if 'search_start_time' in locals() else 0
        logger.exception(
            f"hybrid_search_error: query={query[:100]}, error={str(e)}",
            extra={
                'query': query[:200],
                'total_time_ms': round(total_time * 1000, 2),
                'error': str(e),
                'error_type': type(e).__name__
            }
        )
        # Graceful degradation: try semantic-only as last resort
        try:
            logger.info(f"Falling back to semantic search only for query: {query[:100]}")
            return await semantic_search(ctx, query, match_count)
        except Exception as fallback_error:
            logger.error(
                f"Fallback semantic search also failed: {fallback_error}",
                extra={'query': query[:200], 'error': str(fallback_error)},
                exc_info=True
            )
            return []


async def extract_questions(user_input: str) -> List[str]:
    """
    Extract individual questions from user input using LLM.

    Handles:
    - Numbered lists (1. Question 1, 2. Question 2)
    - Bullet points (- Question, • Question)
    - Multiple sentences ending with ?
    - Single question

    Args:
        user_input: User input text that may contain multiple questions

    Returns:
        List of question strings
    """
    from src.providers import get_llm_model
    from pydantic_ai import Agent
    from pydantic import BaseModel
    from typing import List as TypingList

    try:
        # Create a simple agent for question extraction
        class QuestionList(BaseModel):
            questions: TypingList[str]

        extraction_prompt = f"""Extract all individual questions from the following user input.
The input may contain:
- Numbered lists (1. Question, 2. Question)
- Bullet points (- Question, • Question)
- Multiple sentences ending with ?
- A single question

Return ONLY a JSON array of question strings, one per question.
Clean each question (remove numbering, bullets, extra whitespace).

Input:
{user_input}

Return a JSON object with a "questions" array field containing all extracted questions."""

        llm = get_llm_model()
        agent = Agent(llm, system_prompt="You are a question extraction assistant. Extract questions and return them as a JSON array.")
        
        result = await agent.run(extraction_prompt, response_type=QuestionList)
        
        questions = result.data.questions if result.data else []
        
        # Clean questions
        cleaned_questions = []
        for q in questions:
            # Remove numbering patterns (1., 2., etc.)
            import re
            q = re.sub(r'^\d+[\.\)]\s*', '', q.strip())
            # Remove bullet points
            q = re.sub(r'^[-•*]\s*', '', q.strip())
            # Remove extra whitespace
            q = ' '.join(q.split())
            if q and q.endswith('?'):
                cleaned_questions.append(q)
            elif q:
                # Add ? if missing
                cleaned_questions.append(q + '?')
        
        logger.info(f"Extracted {len(cleaned_questions)} questions from input")
        return cleaned_questions if cleaned_questions else [user_input]

    except Exception as e:
        logger.exception(f"Error extracting questions: {e}")
        # Fallback: return input as single question
        return [user_input]


def build_qa_history_filter(
    outcome_status: Optional[str] = None,
    user_role: Optional[str] = None
) -> Dict[str, Any]:
    """
    Build MongoDB filter query for Q&A history search.

    Args:
        outcome_status: Filter by outcome ("successful", "unsuccessful", None for all)
        user_role: Filter by user role ("junior", "senior", None for all)

    Returns:
        Dictionary with filter conditions

    Raises:
        ValueError: If invalid parameters provided
    """
    filter_query = {}
    
    # Validate outcome_status
    if outcome_status is not None:
        outcome_status_lower = outcome_status.lower().strip()
        if outcome_status_lower not in ("successful", "unsuccessful"):
            raise ValueError(
                f"Invalid outcome_status: {outcome_status}. "
                f"Must be 'successful', 'unsuccessful', or None"
            )
        filter_query["outcome_status"] = outcome_status_lower
    
    # Validate user_role
    if user_role is not None:
        user_role_lower = user_role.lower().strip()
        if user_role_lower not in ("junior", "senior"):
            raise ValueError(
                f"Invalid user_role: {user_role}. "
                f"Must be 'junior', 'senior', or None"
            )
        filter_query["user_role"] = user_role_lower
    
    return filter_query


async def search_qa_history(
    ctx: RunContext[AgentDependencies],
    query: str,
    match_count: Optional[int] = 5,
    outcome_status: Optional[str] = "successful",
    user_role: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Search historical Q&A pairs using vector similarity.

    Args:
        ctx: Agent runtime context with dependencies
        query: Search query
        match_count: Number of results to return
        outcome_status: Filter by outcome ("successful", "unsuccessful", None for all)
        user_role: Filter by user role ("junior", "senior", None for all)

    Returns:
        List of Q&A pairs with similarity scores and session context
    """
    search_start_time = time.time()
    try:
        deps = ctx.deps

        logger.info(
            f"search_qa_history starting: query='{query[:100]}', match_count={match_count}, "
            f"outcome_status={outcome_status}, user_role={user_role}",
            extra={
                'query': query[:200],
                'match_count': match_count,
                'outcome_status': outcome_status,
                'user_role': user_role
            }
        )

        # Use default if not specified
        if match_count is None:
            match_count = deps.settings.default_match_count

        # Validate match count
        match_count = min(match_count, deps.settings.max_match_count)

        # Validate and build filter query
        try:
            filter_query = build_qa_history_filter(
                outcome_status=outcome_status,
                user_role=user_role
            )
            logger.debug(
                f"Q&A history filter built: {filter_query}",
                extra={'filter_query': filter_query}
            )
        except ValueError as e:
            logger.warning(
                f"Invalid Q&A history filter parameters: {e}",
                extra={
                    'query': query[:200],
                    'outcome_status': outcome_status,
                    'user_role': user_role,
                    'error': str(e)
                }
            )
            return []

        # Generate embedding for query
        embedding_start = time.time()
        query_embedding = await deps.get_embedding(query)
        embedding_time = time.time() - embedding_start
        logger.debug(
            f"Query embedding generated in {embedding_time:.2f}s",
            extra={'embedding_time_ms': round(embedding_time * 1000, 2)}
        )

        # Build MongoDB aggregation pipeline
        pipeline = []

        # Vector search stage
        pipeline.append({
            "$vectorSearch": {
                "index": deps.settings.mongodb_vector_index,
                "queryVector": query_embedding,
                "path": "question_embedding",
                "numCandidates": 100,
                "limit": match_count * 2 if filter_query else match_count
            }
        })

        # Add $match stage after vector search to apply filters
        # Note: outcome_status filter applies to qa_pairs collection
        qa_pair_filter = {}
        if "outcome_status" in filter_query:
            qa_pair_filter["outcome_status"] = filter_query["outcome_status"]

        # Policy: only GOOD-rated Q&A pairs can be used as exemplars.
        # This intentionally excludes rating_good missing/null/false.
        qa_pair_filter["rating_good"] = True
        
        if qa_pair_filter:
            pipeline.append({"$match": qa_pair_filter})

        # Lookup session information
        pipeline.append({
            "$lookup": {
                "from": deps.settings.mongodb_collection_qa_sessions,
                "localField": "session_id",
                "foreignField": "_id",
                "as": "session_info"
            }
        })
        pipeline.append({
            "$unwind": "$session_info"
        })

        # Filter by user_role if provided (applies to session)
        if "user_role" in filter_query:
            pipeline.append({
                "$match": {"session_info.user_role": filter_query["user_role"]}
            })

        # Project fields
        pipeline.append({
            "$project": {
                "_id": 1,
                "session_id": 1,
                "question": 1,
                "original_answer": 1,
                "edited_answer": 1,
                "final_answer": 1,
                "citations": 1,
                "question_index": 1,
                "outcome_status": 1,
                "similarity": {"$meta": "vectorSearchScore"},
                "session_name": "$session_info.session_name",
                "session_user_role": "$session_info.user_role",
                "session_company_info": "$session_info.metadata.company_info",
                "created_at": 1
            }
        })

        # Execute aggregation
        db_start = time.time()
        collection = deps.db[deps.settings.mongodb_collection_qa_pairs]
        cursor = await collection.aggregate(pipeline)
        results = [doc async for doc in cursor][:match_count]
        db_time = time.time() - db_start

        # Convert ObjectIds to strings
        for result in results:
            result["_id"] = str(result["_id"])
            result["session_id"] = str(result["session_id"])

        total_time = time.time() - search_start_time
        top_similarities = [r.get('similarity', 0.0) for r in results[:3]] if results else []
        
        logger.info(
            f"search_qa_history completed: query='{query[:100]}', "
            f"results={len(results)}, match_count={match_count}, "
            f"outcome_status={outcome_status}, user_role={user_role} in {total_time:.2f}s",
            extra={
                'query': query[:200],
                'result_count': len(results),
                'match_count': match_count,
                'outcome_status': outcome_status,
                'user_role': user_role,
                'total_time_ms': round(total_time * 1000, 2),
                'embedding_time_ms': round(embedding_time * 1000, 2),
                'db_time_ms': round(db_time * 1000, 2),
                'top_similarities': top_similarities
            }
        )

        return results

    except OperationFailure as e:
        total_time = time.time() - search_start_time if 'search_start_time' in locals() else 0
        error_code = e.code if hasattr(e, 'code') else None
        logger.error(
            f"search_qa_history failed (OperationFailure): query='{query[:100]}', "
            f"error={str(e)}, code={error_code}",
            extra={
                'query': query[:200],
                'error': str(e),
                'error_code': error_code,
                'error_type': 'OperationFailure',
                'total_time_ms': round(total_time * 1000, 2)
            },
            exc_info=True
        )
        return []
    except Exception as e:
        total_time = time.time() - search_start_time if 'search_start_time' in locals() else 0
        logger.exception(
            f"search_qa_history error: query='{query[:100]}', error={str(e)}",
            extra={
                'query': query[:200],
                'error': str(e),
                'error_type': type(e).__name__,
                'total_time_ms': round(total_time * 1000, 2)
            }
        )
        return []
