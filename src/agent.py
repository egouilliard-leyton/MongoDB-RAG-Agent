"""Main MongoDB RAG agent implementation with shared state."""

from pydantic_ai import Agent, RunContext
from pydantic import BaseModel
from typing import Optional, Dict, List
from collections import OrderedDict
import uuid
import logging
import asyncio
import time

from pydantic_ai.ag_ui import StateDeps

from src.providers import get_llm_model
from src.dependencies import AgentDependencies
from src.prompts import MAIN_SYSTEM_PROMPT
from src.tools import semantic_search, hybrid_search, text_search, SearchResult, search_qa_history, extract_questions
from src.reasoning import analyze_question_complexity, merge_search_results, evaluate_results_sufficiency
from src.settings import load_settings

logger = logging.getLogger(__name__)


class RAGState(BaseModel):
    """Shared state for the RAG agent with search history tracking."""
    search_history: List[Dict] = []
    """History of previous searches for iterative refinement."""


# Module-level citation tracker: maps run_id -> list of citation metadata
# This allows the CLI to access citation metadata after tool execution
_citation_tracker: Dict[str, List[Dict[str, str]]] = {}


# Create the RAG agent with AGUI support
rag_agent = Agent(
    get_llm_model(),
    deps_type=StateDeps[RAGState],
    system_prompt=MAIN_SYSTEM_PROMPT
)


@rag_agent.tool
async def search_knowledge_base(
    ctx: RunContext[StateDeps[RAGState]],
    query: str,
    match_count: Optional[int] = 5,
    search_type: Optional[str] = "hybrid",
    document_type: Optional[str] = None,
    author: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    keywords: Optional[List[str]] = None,
    section_type: Optional[str] = None
) -> str:
    """
    Search the knowledge base for relevant information with optional metadata filtering.

    Supports filtering by document type, author, date range, keywords, and section type.
    This is especially useful for Polish tax interpretation documents.

    Args:
        ctx: Agent runtime context with state dependencies
        query: Search query text
        match_count: Number of results to return (default: 5)
        search_type: Type of search - "semantic" or "text" or "hybrid" (default: hybrid)
        document_type: Filter by document type (e.g., "KDIP2", "KDIB1-3")
        author: Filter by author (e.g., "DK", "AZ")
        date_from: Filter by document date from (YYYY-MM-DD format, inclusive)
        date_to: Filter by document date to (YYYY-MM-DD format, inclusive)
        keywords: Filter by keywords (list of strings, matches any)
        section_type: Filter by section type (e.g., "przepis", "zagadnienie", "interpretation", "analysis")

    Returns:
        String containing the retrieved information formatted for the LLM with citation markers [1], [2], etc.
    """
    logger.info(
        f"search_knowledge_base called: query='{query[:100]}', type={search_type}, "
        f"match_count={match_count}, filters={{document_type={document_type}, "
        f"author={author}, date_from={date_from}, date_to={date_to}, "
        f"keywords={keywords}, section_type={section_type}}}"
    )
    try:
        # Initialize database connection
        agent_deps = AgentDependencies()
        await agent_deps.initialize()

        # Create a context wrapper for the search tools
        class DepsWrapper:
            def __init__(self, deps):
                self.deps = deps

        deps_ctx = DepsWrapper(agent_deps)

        # Perform the search based on type with metadata filters
        if search_type == "hybrid":
            results = await hybrid_search(
                ctx=deps_ctx,
                query=query,
                match_count=match_count,
                document_type=document_type,
                author=author,
                date_from=date_from,
                date_to=date_to,
                keywords=keywords,
                section_type=section_type
            )
        elif search_type == "semantic":
            results = await semantic_search(
                ctx=deps_ctx,
                query=query,
                match_count=match_count,
                document_type=document_type,
                author=author,
                date_from=date_from,
                date_to=date_to,
                keywords=keywords,
                section_type=section_type
            )
        else:
            results = await text_search(
                ctx=deps_ctx,
                query=query,
                match_count=match_count,
                document_type=document_type,
                author=author,
                date_from=date_from,
                date_to=date_to,
                keywords=keywords,
                section_type=section_type
            )

        # Clean up
        await agent_deps.cleanup()

        # Format results as a simple string
        if not results:
            return "No relevant information found in the knowledge base."

        # Track unique documents and assign citation numbers
        # Use OrderedDict to preserve order and deduplicate by document_id
        unique_documents = OrderedDict()
        citation_metadata = []
        
        for result in results:
            doc_id = result.document_id
            if doc_id not in unique_documents:
                citation_num = len(unique_documents) + 1
                
                # Extract document metadata for citations
                doc_metadata = result.metadata
                citation_info = {
                    'citation_number': citation_num,
                    'title': result.document_title,
                    'source': result.document_source,
                    'document_id': doc_id
                }
                
                # Add tax interpretation metadata if available
                if doc_metadata.get('id_informacji'):
                    citation_info['id_informacji'] = doc_metadata['id_informacji']
                if doc_metadata.get('sygnatura'):
                    citation_info['sygnatura'] = doc_metadata['sygnatura']
                if doc_metadata.get('document_type'):
                    citation_info['document_type'] = doc_metadata['document_type']
                if doc_metadata.get('document_date'):
                    citation_info['document_date'] = doc_metadata['document_date']
                
                unique_documents[doc_id] = citation_info
                citation_metadata.append(citation_info)

        # Store citation metadata for this tool call
        # Generate a unique call ID for this tool invocation
        call_id = str(uuid.uuid4())
        _citation_tracker[call_id] = citation_metadata

        # Build a formatted response with citation markers
        # Include citation markers in a way that encourages the LLM to use them
        response_parts = [f"Found {len(results)} relevant documents:\n"]

        for result in results:
            doc_id = result.document_id
            citation_num = unique_documents[doc_id]['citation_number']
            response_parts.append(
                f"\n--- Document [{citation_num}]: {result.document_title} "
                f"(relevance: {result.similarity:.2f}) ---"
            )
            # Include citation marker inline with content
            response_parts.append(f"{result.content} [{citation_num}]")

        # Append call_id as a hidden marker that CLI can extract
        # Format: <CITATION_TRACKER_ID:uuid>
        # This will be removed from what the LLM sees, but we extract it from tool result
        response_parts.append(f"\n<CITATION_TRACKER_ID:{call_id}>")
        
        logger.info(f"search_knowledge_base completed: found {len(results)} results, {len(unique_documents)} unique documents")
        return "\n".join(response_parts)

    except Exception as e:
        logger.error(f"Error in search_knowledge_base: {e}", exc_info=True)
        return f"Error searching knowledge base: {str(e)}"


def get_citation_metadata(call_id: str) -> List[Dict[str, str]]:
    """
    Get citation metadata for a given call ID.
    
    Args:
        call_id: The call ID to get citations for
        
    Returns:
        List of citation metadata dictionaries
    """
    return _citation_tracker.get(call_id, [])


def clear_citation_metadata(call_id: str) -> None:
    """
    Clear citation metadata for a given call ID.
    
    Args:
        call_id: The call ID to clear citations for
    """
    if call_id in _citation_tracker:
        del _citation_tracker[call_id]


@rag_agent.tool
async def decompose_question(
    ctx: RunContext[StateDeps[RAGState]],
    question: str
) -> str:
    """
    Analyze a complex question and break it down into sub-questions for better search coverage.
    
    Use this tool when a question asks about multiple topics, requires comparisons,
    or has multiple aspects that would benefit from separate searches.
    
    Args:
        ctx: Agent runtime context with state dependencies
        question: The complex question to decompose
        
    Returns:
        JSON-formatted string with sub-questions and reasoning
    """
    logger.info(f"decompose_question called: question='{question[:100]}'")
    try:
        settings = load_settings()
        
        # Check if decomposition is enabled
        if not settings.enable_question_decomposition:
            return f'{{"is_complex": false, "sub_questions": ["{question}"], "reasoning": "Decomposition disabled"}}'
        
        # Analyze question complexity
        analysis = await analyze_question_complexity(question)
        
        # Update state with decomposition info
        if ctx.deps.state:
            if not hasattr(ctx.deps.state, 'search_history'):
                ctx.deps.state.search_history = []
            ctx.deps.state.search_history.append({
                'type': 'decomposition',
                'original_question': question,
                'sub_questions': analysis.sub_questions,
                'is_complex': analysis.is_complex
            })
        
        # Format response
        import json
        result = {
            "is_complex": analysis.is_complex,
            "sub_questions": analysis.sub_questions,
            "reasoning": analysis.reasoning
        }
        
        if analysis.is_complex and len(analysis.sub_questions) > 1:
            return f"""Question decomposition complete:

Complexity: Complex (multiple aspects detected)
Reasoning: {analysis.reasoning}

Sub-questions identified ({len(analysis.sub_questions)}):
{chr(10).join(f"{i+1}. {q}" for i, q in enumerate(analysis.sub_questions))}

Recommendation: Use multi_search_knowledge_base with these sub-questions for comprehensive coverage."""
        else:
            return f"""Question analysis complete:

Complexity: Simple (single topic)
Reasoning: {analysis.reasoning}

Recommendation: Use search_knowledge_base directly with the original question."""
        
        logger.info(f"decompose_question completed: is_complex={analysis.is_complex}, sub_questions={len(analysis.sub_questions)}")
            
    except Exception as e:
        logger.error(f"Error in decompose_question: {e}", exc_info=True)
        return f"Error decomposing question: {str(e)}"


@rag_agent.tool
async def multi_search_knowledge_base(
    ctx: RunContext[StateDeps[RAGState]],
    queries: List[str],
    match_count_per_query: Optional[int] = 5,
    search_type: Optional[str] = "hybrid"
) -> str:
    """
    Execute multiple searches in parallel for different sub-questions and combine results.
    
    Use this tool when you have decomposed a complex question into sub-questions,
    or when you need to search multiple related topics simultaneously.
    
    Args:
        ctx: Agent runtime context with state dependencies
        queries: List of search queries to execute in parallel
        match_count_per_query: Number of results per query (default: 5)
        search_type: Type of search - "semantic" or "text" or "hybrid" (default: hybrid)
        
    Returns:
        String containing combined retrieved information with citation markers
    """
    logger.info(f"multi_search_knowledge_base called: {len(queries)} queries, type={search_type}, match_count={match_count_per_query}")
    try:
        if not queries or len(queries) == 0:
            return "Error: No queries provided for multi-search."
        
        # Initialize database connection
        agent_deps = AgentDependencies()
        await agent_deps.initialize()
        
        # Create a context wrapper for the search tools
        class DepsWrapper:
            def __init__(self, deps):
                self.deps = deps
        
        deps_ctx = DepsWrapper(agent_deps)
        
        # Execute all searches in parallel
        search_tasks = []
        for query in queries:
            if search_type == "hybrid":
                task = hybrid_search(deps_ctx, query, match_count_per_query)
            elif search_type == "semantic":
                task = semantic_search(deps_ctx, query, match_count_per_query)
            else:
                task = text_search(deps_ctx, query, match_count_per_query)
            search_tasks.append(task)
        
        # Wait for all searches to complete
        all_results_lists = await asyncio.gather(*search_tasks, return_exceptions=True)
        
        # Filter out exceptions and convert to lists
        valid_results_lists = []
        for i, result in enumerate(all_results_lists):
            if isinstance(result, Exception):
                logger.warning(f"Search {i+1} failed: {result}")
                valid_results_lists.append([])
            else:
                valid_results_lists.append(result)
        
        # Clean up
        await agent_deps.cleanup()
        
        # Merge results from all queries
        merged_results = merge_search_results(valid_results_lists)
        
        if not merged_results:
            return "No relevant information found across all sub-queries."
        
        # Track unique documents and assign citation numbers
        unique_documents = OrderedDict()
        citation_metadata = []
        
        for result in merged_results:
            doc_id = result.document_id
            if doc_id not in unique_documents:
                citation_num = len(unique_documents) + 1
                unique_documents[doc_id] = {
                    'citation_number': citation_num,
                    'title': result.document_title,
                    'source': result.document_source,
                    'document_id': doc_id
                }
                citation_metadata.append({
                    'citation_number': citation_num,
                    'title': result.document_title,
                    'source': result.document_source,
                    'document_id': doc_id
                })
        
        # Store citation metadata
        call_id = str(uuid.uuid4())
        _citation_tracker[call_id] = citation_metadata
        
        # Update state
        if ctx.deps.state:
            if not hasattr(ctx.deps.state, 'search_history'):
                ctx.deps.state.search_history = []
            ctx.deps.state.search_history.append({
                'type': 'multi_search',
                'queries': queries,
                'results_count': len(merged_results),
                'unique_documents': len(unique_documents)
            })
        
        # Build formatted response
        response_parts = [
            f"Multi-search completed: {len(queries)} queries → {len(merged_results)} total results ({len(unique_documents)} unique documents)\n"
        ]
        
        # Group results by query for clarity
        query_to_results = {}
        for i, query in enumerate(queries):
            query_to_results[query] = valid_results_lists[i]
        
        response_parts.append("\nResults by query:")
        for query, results in query_to_results.items():
            response_parts.append(f"\n--- Query: {query} ({len(results)} results) ---")
            for result in results[:3]:  # Show top 3 per query
                doc_id = result.document_id
                citation_num = unique_documents[doc_id]['citation_number']
                response_parts.append(f"{result.content[:200]}... [{citation_num}]")
        
        response_parts.append("\n\n--- All Unique Documents (deduplicated) ---")
        for result in merged_results[:10]:  # Show top 10 overall
            doc_id = result.document_id
            citation_num = unique_documents[doc_id]['citation_number']
            response_parts.append(
                f"\n--- Document [{citation_num}]: {result.document_title} "
                f"(relevance: {result.similarity:.2f}) ---"
            )
            response_parts.append(f"{result.content} [{citation_num}]")
        
        response_parts.append(f"\n<CITATION_TRACKER_ID:{call_id}>")
        
        logger.info(f"multi_search_knowledge_base completed: {len(merged_results)} merged results, {len(unique_documents)} unique documents")
        return "\n".join(response_parts)
        
    except Exception as e:
        logger.error(f"Error in multi_search_knowledge_base: {e}", exc_info=True)
        return f"Error in multi-search: {str(e)}"


@rag_agent.tool
async def refine_search(
    ctx: RunContext[StateDeps[RAGState]],
    original_query: str,
    previous_results_summary: str,
    refinement_goal: str
) -> str:
    """
    Refine a search query based on previous results and a specific goal.
    
    Use this tool when initial search results are insufficient, too broad, too narrow,
    or don't fully address the user's question. This enables iterative refinement.
    
    Args:
        ctx: Agent runtime context with state dependencies
        original_query: The original search query that was used
        previous_results_summary: Summary of what was found in previous search
        refinement_goal: What you're trying to achieve with the refined search
                        (e.g., "find more specific technical details", "get broader context")
        
    Returns:
        String containing refined search results with citation markers
    """
    logger.info(f"refine_search called: original='{original_query[:100]}', goal='{refinement_goal[:100]}'")
    try:
        settings = load_settings()
        
        # Check if refinement is enabled
        if not settings.enable_iterative_refinement:
            return "Iterative refinement is disabled. Use search_knowledge_base instead."
        
        # Check iteration limit
        if ctx.deps.state:
            if not hasattr(ctx.deps.state, 'search_history'):
                ctx.deps.state.search_history = []
            
            # Count previous searches
            search_count = sum(1 for h in ctx.deps.state.search_history 
                             if h.get('type') in ['search', 'multi_search', 'refine'])
            
            if search_count >= settings.max_search_iterations:
                return f"Maximum search iterations ({settings.max_search_iterations}) reached. Cannot refine further."
        
        # Generate refined query using LLM
        refinement_prompt = f"""Original query: "{original_query}"

Previous results summary:
{previous_results_summary}

Refinement goal: {refinement_goal}

Generate a refined search query that will better achieve the refinement goal.
Return ONLY the refined query text, nothing else."""
        
        # Use a simple LLM call to generate refined query
        try:
            from src.providers import get_llm_model
            from pydantic_ai.models.openai import OpenAIModel
            llm = get_llm_model()
            # Create a simple agent for query refinement
            refinement_agent = Agent(llm, system_prompt="You are a query refinement assistant. Generate improved search queries. Return only the refined query text.")
            refined_result = await refinement_agent.run(refinement_prompt)
            refined_query = str(refined_result.data).strip()
            
            # Remove quotes if present
            if refined_query.startswith('"') and refined_query.endswith('"'):
                refined_query = refined_query[1:-1]
            if refined_query.startswith("'") and refined_query.endswith("'"):
                refined_query = refined_query[1:-1]
            
            # Clean up any markdown formatting
            refined_query = refined_query.replace('```', '').strip()
            
            # If refinement failed, use original with modification
            if not refined_query or len(refined_query) < 5:
                refined_query = f"{original_query} {refinement_goal}"
        except Exception as e:
            logger.warning(f"Error generating refined query: {e}, using fallback")
            # Fallback: append refinement goal to original query
            refined_query = f"{original_query} {refinement_goal}"
        
        # Initialize database connection
        agent_deps = AgentDependencies()
        await agent_deps.initialize()
        
        # Create a context wrapper
        class DepsWrapper:
            def __init__(self, deps):
                self.deps = deps
        
        deps_ctx = DepsWrapper(agent_deps)
        
        # Perform refined search (use hybrid by default)
        results = await hybrid_search(
            ctx=deps_ctx,
            query=refined_query,
            match_count=settings.default_match_count
        )
        
        # Clean up
        await agent_deps.cleanup()
        
        if not results:
            return f"Refined search for '{refined_query}' returned no results. Try a different refinement approach."
        
        # Track citations
        unique_documents = OrderedDict()
        citation_metadata = []
        
        for result in results:
            doc_id = result.document_id
            if doc_id not in unique_documents:
                citation_num = len(unique_documents) + 1
                unique_documents[doc_id] = {
                    'citation_number': citation_num,
                    'title': result.document_title,
                    'source': result.document_source,
                    'document_id': doc_id
                }
                citation_metadata.append({
                    'citation_number': citation_num,
                    'title': result.document_title,
                    'source': result.document_source,
                    'document_id': doc_id
                })
        
        # Store citation metadata
        call_id = str(uuid.uuid4())
        _citation_tracker[call_id] = citation_metadata
        
        # Update state
        if ctx.deps.state:
            if not hasattr(ctx.deps.state, 'search_history'):
                ctx.deps.state.search_history = []
            ctx.deps.state.search_history.append({
                'type': 'refine',
                'original_query': original_query,
                'refined_query': refined_query,
                'refinement_goal': refinement_goal,
                'results_count': len(results)
            })
        
        # Build response
        response_parts = [
            f"Refined search completed:\n",
            f"Original query: {original_query}\n",
            f"Refined query: {refined_query}\n",
            f"Goal: {refinement_goal}\n",
            f"Found {len(results)} results:\n"
        ]
        
        for result in results:
            doc_id = result.document_id
            citation_num = unique_documents[doc_id]['citation_number']
            response_parts.append(
                f"\n--- Document [{citation_num}]: {result.document_title} "
                f"(relevance: {result.similarity:.2f}) ---"
            )
            response_parts.append(f"{result.content} [{citation_num}]")
        
        response_parts.append(f"\n<CITATION_TRACKER_ID:{call_id}>")
        
        logger.info(f"refine_search completed: refined_query='{refined_query[:100]}', found {len(results)} results")
        return "\n".join(response_parts)
        
    except Exception as e:
        logger.error(f"Error in refine_search: {e}", exc_info=True)
        return f"Error refining search: {str(e)}"


async def process_question_batch_standalone(
    questions: List[str],
    session_id: Optional[str] = None,
    user_role: Optional[str] = "junior",
    include_history: bool = True
) -> str:
    """
    Standalone function to process multiple questions (for FastAPI use).
    
    For each question:
    1. Search document database (existing RAG)
    2. Search Q&A history (if enabled)
    3. Generate answer with citations
    4. Save Q&A pair (if senior user)
    
    Args:
        questions: List of questions to process
        session_id: Optional session ID for saving Q&A pairs
        user_role: User role ("junior" or "senior")
        include_history: Whether to search Q&A history
        
    Returns:
        JSON string with question-answer pairs
    """
    import json
    from src.services.qa_storage import QAStorageService
    from src.settings import load_settings
    
    start_time = time.time()
    logger.info(
        f"process_question_batch_standalone called: {len(questions)} questions, "
        f"session_id={session_id}, user_role={user_role}, include_history={include_history}",
        extra={
            'question_count': len(questions),
            'session_id': session_id,
            'user_role': user_role,
            'include_history': include_history
        }
    )
    
    try:
        settings = load_settings()
        qa_storage = QAStorageService(settings)
        await qa_storage.initialize()
        
        # Validate document existence before processing
        agent_deps = AgentDependencies()
        await agent_deps.initialize()
        
        try:
            doc_count = await agent_deps.db[settings.mongodb_collection_documents].count_documents({})
            chunk_count = await agent_deps.db[settings.mongodb_collection_chunks].count_documents({})
            
            logger.info(f"Document validation: {doc_count} documents, {chunk_count} chunks")
            
            if doc_count == 0:
                error_msg = "No documents found in database. Please run document ingestion first."
                logger.error(error_msg)
                await agent_deps.cleanup()
                await qa_storage.cleanup()
                return json.dumps({
                    "error": error_msg,
                    "questions_processed": 0,
                    "qa_pairs": [],
                    "recommendation": "Run: uv run python -m src.ingestion.ingest -d ./documents"
                })
            
            if chunk_count == 0:
                error_msg = "No chunks found in database. Please run document ingestion first."
                logger.error(error_msg)
                await agent_deps.cleanup()
                await qa_storage.cleanup()
                return json.dumps({
                    "error": error_msg,
                    "questions_processed": 0,
                    "qa_pairs": [],
                    "recommendation": "Run: uv run python -m src.ingestion.ingest -d ./documents"
                })
            
            # Check if chunks have embeddings (sample check)
            sample_chunk = await agent_deps.db[settings.mongodb_collection_chunks].find_one({})
            if sample_chunk and not sample_chunk.get("embedding"):
                error_msg = "Chunks found but embeddings are missing. Please re-run document ingestion."
                logger.error(error_msg)
                await agent_deps.cleanup()
                await qa_storage.cleanup()
                return json.dumps({
                    "error": error_msg,
                    "questions_processed": 0,
                    "qa_pairs": [],
                    "recommendation": "Run: uv run python -m src.ingestion.ingest -d ./documents"
                })
            
            # Check for vector index (try to list indexes)
            try:
                indexes = []
                async for idx in agent_deps.db[settings.mongodb_collection_chunks].list_indexes():
                    indexes.append(idx)
                
                vector_index_name = settings.mongodb_vector_index
                index_names = [idx.get("name", "") for idx in indexes]
                
                if vector_index_name not in index_names:
                    # Check if any vector index exists
                    has_vector_index = any(
                        idx.get("type") == "vectorSearch" 
                        for idx in indexes
                    )
                    if not has_vector_index:
                        logger.warning(
                            f"Vector index '{vector_index_name}' not found. "
                            "Vector search may fail. Create index in Atlas UI."
                        )
            except Exception as idx_error:
                logger.warning(f"Could not verify vector index: {idx_error}")
            
        finally:
            await agent_deps.cleanup()
        
        results = []
        
        # Check if this is a follow-up session and fetch parent session context
        follow_up_context = ""
        round_number = 1
        if session_id:
            try:
                session = await qa_storage.get_session(session_id)
                parent_session_id = session.get("metadata", {}).get("parent_session_id")
                round_number = session.get("metadata", {}).get("round_number", 1)
                
                if parent_session_id:
                    # Fetch previous round's Q&A pairs
                    from src.prompts import FOLLOW_UP_CONTEXT_PROMPT
                    
                    previous_qa_pairs = await qa_storage.get_parent_session_qa_pairs(session_id)
                    
                    if previous_qa_pairs:
                        # Format previous Q&A pairs for prompt
                        previous_formatted_parts = []
                        for i, qa_pair in enumerate(previous_qa_pairs[:5], 1):  # Limit to first 5
                            question_text = qa_pair.get("question", "Unknown question")
                            answer_text = qa_pair.get("final_answer") or qa_pair.get("original_answer", "No answer")
                            outcome = qa_pair.get("outcome_status", "pending")
                            
                            previous_formatted_parts.append(f"\n### Previous Q&A #{i} [{outcome}]")
                            previous_formatted_parts.append(f"**Question:** {question_text}")
                            previous_formatted_parts.append(f"**Previous Answer:** {answer_text[:300]}...")
                            if qa_pair.get("citations"):
                                cit_count = len(qa_pair["citations"])
                                previous_formatted_parts.append(f"**Citations:** {cit_count} source(s)")
                        
                        previous_formatted = "\n".join(previous_formatted_parts)
                        
                        # Build follow-up context using template
                        follow_up_context = FOLLOW_UP_CONTEXT_PROMPT.format(
                            round_number=round_number,
                            previous_qa_pairs=previous_formatted
                        )
                        
                        logger.info(
                            f"Follow-up session detected (Round {round_number}): "
                            f"Including context from {len(previous_qa_pairs)} previous Q&A pairs"
                        )
            except Exception as e:
                logger.warning(f"Failed to fetch follow-up context: {e}")
        
        for idx, question in enumerate(questions):
            question_start_time = time.time()
            logger.info(
                f"Processing question {idx + 1}/{len(questions)}: {question[:100]}...",
                extra={'question_index': idx, 'question': question[:200]}
            )
            
            # 1. Search document database
            logger.debug(f"Initializing AgentDependencies for question {idx + 1}", extra={'question_index': idx})
            agent_deps = AgentDependencies()
            await agent_deps.initialize()
            
            class DepsWrapper:
                def __init__(self, deps):
                    self.deps = deps
            
            deps_ctx = DepsWrapper(agent_deps)
            
            # Use hybrid search for document retrieval
            search_start_time = time.time()
            logger.info(
                f"Searching documents for question {idx + 1}: {question[:100]}...",
                extra={'question_index': idx, 'match_count': 5}
            )
            try:
                doc_results = await hybrid_search(
                    ctx=deps_ctx,
                    query=question,
                    match_count=5
                )
                search_time = time.time() - search_start_time
                logger.info(
                    f"Document search completed: {len(doc_results)} results in {search_time:.2f}s",
                    extra={
                        'question_index': idx,
                        'result_count': len(doc_results),
                        'search_time_ms': round(search_time * 1000, 2)
                    }
                )
                if doc_results:
                    top_similarities = [r.similarity for r in doc_results[:3]]
                    logger.info(
                        f"Top result similarities: {top_similarities}",
                        extra={
                            'question_index': idx,
                            'top_similarities': top_similarities,
                            'top_result_title': doc_results[0].document_title[:100]
                        }
                    )
                else:
                    logger.warning(
                        f"No document results found for question {idx + 1}",
                        extra={'question_index': idx, 'question': question[:200]}
                    )
            except Exception as search_error:
                search_time = time.time() - search_start_time
                logger.error(
                    f"Document search failed for question {idx + 1}: {search_error}",
                    extra={
                        'question_index': idx,
                        'question': question[:200],
                        'search_time_ms': round(search_time * 1000, 2),
                        'error': str(search_error),
                        'error_type': type(search_error).__name__
                    },
                    exc_info=True
                )
                doc_results = []
            
            await agent_deps.cleanup()
            
            # 2. Search Q&A history if enabled
            qa_history_results = []
            if include_history:
                qa_history_start_time = time.time()
                logger.debug(
                    f"Searching Q&A history for question {idx + 1}",
                    extra={'question_index': idx, 'match_count': 3, 'outcome_status': 'successful'}
                )
                try:
                    agent_deps = AgentDependencies()
                    await agent_deps.initialize()
                    deps_ctx = DepsWrapper(agent_deps)
                    
                    qa_history_results = await search_qa_history(
                        ctx=deps_ctx,
                        query=question,
                        match_count=3,
                        outcome_status="successful",
                        user_role=user_role
                    )
                    
                    qa_history_time = time.time() - qa_history_start_time
                    logger.info(
                        f"Q&A history search completed: {len(qa_history_results)} results in {qa_history_time:.2f}s",
                        extra={
                            'question_index': idx,
                            'result_count': len(qa_history_results),
                            'qa_history_time_ms': round(qa_history_time * 1000, 2)
                        }
                    )
                    if qa_history_results:
                        qa_similarities = [h.get('similarity', 0.0) for h in qa_history_results[:3]]
                        logger.debug(
                            f"Q&A history similarities: {qa_similarities}",
                            extra={'question_index': idx, 'similarities': qa_similarities}
                        )
                    
                    await agent_deps.cleanup()
                except Exception as e:
                    qa_history_time = time.time() - qa_history_start_time
                    logger.warning(
                        f"Q&A history search failed for question {idx + 1}: {e}",
                        extra={
                            'question_index': idx,
                            'qa_history_time_ms': round(qa_history_time * 1000, 2),
                            'error': str(e),
                            'error_type': type(e).__name__
                        },
                        exc_info=True
                    )
            else:
                logger.debug(f"Q&A history search skipped (include_history=False)", extra={'question_index': idx})
            
            # 3. Generate answer using LLM
            # Build context from document results and Q&A history
            from src.prompts import QA_HISTORY_PROMPT
            
            context_parts = []
            
            if doc_results:
                context_parts.append("## Document Search Results:")
                for i, result in enumerate(doc_results[:3], 1):  # Top 3 results
                    context_parts.append(f"\n[{i}] {result.document_title}")
                    context_parts.append(f"{result.content[:300]}...")
                    context_parts.append(f"(Relevance: {result.similarity:.2f})")
            
            # Format Q&A history using QA_HISTORY_PROMPT template
            qa_history_formatted = ""
            if qa_history_results:
                qa_history_parts = []
                for i, hist in enumerate(qa_history_results[:3], 1):  # Top 3 historical Q&A
                    similarity = hist.get('similarity', 0.0)
                    qa_history_parts.append(f"\n### Historical Q&A #{i} (similarity: {similarity:.2f})")
                    qa_history_parts.append(f"**Question:** {hist['question']}")
                    qa_history_parts.append(f"**Answer:** {hist['final_answer'][:400]}...")
                    if hist.get('citations'):
                        cit_count = len(hist['citations'])
                        qa_history_parts.append(f"**Citations:** {cit_count} source(s)")
                    if hist.get('session_name'):
                        qa_history_parts.append(f"**Session:** {hist['session_name']}")
                
                qa_history_formatted = "\n".join(qa_history_parts)
            
            # Build document context
            doc_context = "\n".join(context_parts) if context_parts else "No relevant documents found in the knowledge base."
            
            # Build Q&A history context using template
            qa_history_context = ""
            if qa_history_formatted:
                qa_history_context = QA_HISTORY_PROMPT.format(qa_history=qa_history_formatted)
            
            # Use the agent to generate answer - create state deps for agent
            # StateDeps automatically handles AgentDependencies creation
            state = RAGState()
            state_deps = StateDeps[RAGState](state=state)
            
            # Build comprehensive answer prompt
            # Structure: Question → Follow-up Context → Document Results → Q&A History → Instructions
            answer_prompt_parts = [
                f"Question: {question}",
                ""
            ]
            
            # Include follow-up context FIRST if available
            if follow_up_context:
                answer_prompt_parts.append(follow_up_context)
                answer_prompt_parts.append("")
            
            # Then document context
            answer_prompt_parts.append(doc_context)
            
            # Then Q&A history context
            if qa_history_context:
                answer_prompt_parts.append("")
                answer_prompt_parts.append(qa_history_context)
            
            # Final instructions
            answer_prompt_parts.append("")
            if follow_up_context:
                answer_prompt_parts.append(
                    "Generate a comprehensive answer that addresses the current question, "
                    "learns from the previous round's shortcomings, and incorporates information "
                    "from the knowledge base and successful historical Q&A. Include citation markers [1], [2], etc. when referencing documents."
                )
            else:
                answer_prompt_parts.append(
                    "Generate a comprehensive answer based on the context above. "
                    "Include citation markers [1], [2], etc. when referencing documents."
                )
            
            answer_prompt = "\n".join(answer_prompt_parts)
            prompt_length = len(answer_prompt)
            
            # Use the agent's run method to generate answer
            llm_start_time = time.time()
            logger.info(
                f"Generating answer using LLM for question {idx + 1} (prompt length: {prompt_length} chars)",
                extra={
                    'question_index': idx,
                    'prompt_length': prompt_length,
                    'doc_results_count': len(doc_results),
                    'qa_history_count': len(qa_history_results),
                    'has_follow_up_context': bool(follow_up_context)
                }
            )
            try:
                answer_result = await rag_agent.run(answer_prompt, deps=state_deps)
                # AgentRunResult has 'output' attribute, not 'data'
                answer_text = str(answer_result.output) if hasattr(answer_result, 'output') else str(answer_result)
                llm_time = time.time() - llm_start_time
                logger.info(
                    f"Answer generated successfully for question {idx + 1}: {len(answer_text)} chars in {llm_time:.2f}s",
                    extra={
                        'question_index': idx,
                        'answer_length': len(answer_text),
                        'llm_time_ms': round(llm_time * 1000, 2)
                    }
                )
                if not answer_text or len(answer_text.strip()) == 0:
                    logger.warning(
                        f"Generated answer is empty for question {idx + 1}",
                        extra={'question_index': idx, 'question': question[:200]}
                    )
                    answer_text = "Unable to generate answer. Please try rephrasing your question."
            except Exception as llm_error:
                llm_time = time.time() - llm_start_time
                logger.error(
                    f"LLM API call failed for question {idx + 1}: {llm_error}",
                    extra={
                        'question_index': idx,
                        'question': question[:200],
                        'llm_time_ms': round(llm_time * 1000, 2),
                        'error': str(llm_error),
                        'error_type': type(llm_error).__name__,
                        'prompt_length': prompt_length
                    },
                    exc_info=True
                )
                answer_text = f"Error generating answer: {str(llm_error)}"
            
            # Cleanup is handled automatically by StateDeps
            
            # Extract citations from document results
            citations = []
            unique_docs = {}
            citation_num = 1
            for result in doc_results:
                doc_id = result.document_id
                if doc_id not in unique_docs:
                    citations.append({
                        "citation_number": citation_num,
                        "title": result.document_title,
                        "source": result.document_source,
                        "document_id": doc_id,
                        "similarity": result.similarity
                    })
                    unique_docs[doc_id] = citation_num
                    citation_num += 1
            
            # 4. Save Q&A pair if senior user
            qa_pair_id = None
            qa_pair_data = None
            if session_id and user_role == "senior":
                save_start_time = time.time()
                logger.debug(
                    f"Saving Q&A pair for question {idx + 1} (senior user)",
                    extra={'question_index': idx, 'session_id': session_id, 'citations_count': len(citations)}
                )
                try:
                    qa_pair_id = await qa_storage.save_qa_pair(
                        session_id=session_id,
                        question=question,
                        answer=answer_text,
                        citations=citations,
                        question_index=idx,
                        user_role=user_role
                    )
                    save_time = time.time() - save_start_time
                    logger.info(
                        f"Q&A pair saved successfully for question {idx + 1}: {qa_pair_id}",
                        extra={
                            'question_index': idx,
                            'qa_pair_id': qa_pair_id,
                            'session_id': session_id,
                            'save_time_ms': round(save_time * 1000, 2)
                        }
                    )
                    # Fetch the saved pair to get all fields including _id, timestamps, etc.
                    if qa_pair_id:
                        try:
                            qa_pairs_list = await qa_storage.get_session_qa_pairs(session_id)
                            qa_pair_data = next(
                                (p for p in qa_pairs_list if p.get("_id") == qa_pair_id),
                                None
                            )
                            if qa_pair_data:
                                logger.debug(
                                    f"Fetched saved Q&A pair data for question {idx + 1}",
                                    extra={'question_index': idx, 'qa_pair_id': qa_pair_id}
                                )
                        except Exception as e:
                            logger.warning(
                                f"Failed to fetch saved Q&A pair for question {idx + 1}: {e}",
                                extra={
                                    'question_index': idx,
                                    'qa_pair_id': qa_pair_id,
                                    'error': str(e)
                                },
                                exc_info=True
                            )
                except Exception as e:
                    save_time = time.time() - save_start_time
                    logger.error(
                        f"Failed to save Q&A pair for question {idx + 1}: {e}",
                        extra={
                            'question_index': idx,
                            'session_id': session_id,
                            'save_time_ms': round(save_time * 1000, 2),
                            'error': str(e),
                            'error_type': type(e).__name__
                        },
                        exc_info=True
                    )
            else:
                logger.debug(
                    f"Skipping Q&A pair save for question {idx + 1} (user_role={user_role}, session_id={session_id})",
                    extra={'question_index': idx, 'user_role': user_role, 'has_session': bool(session_id)}
                )
            
            # Build result with all available fields
            result_dict = {
                "question": question,
                "answer": answer_text,
                "final_answer": answer_text,
                "citations": citations,
                "qa_pair_id": qa_pair_id,
                "question_index": idx
            }
            
            # Add fields from saved pair if available
            if qa_pair_data:
                created_at = qa_pair_data.get("created_at")
                updated_at = qa_pair_data.get("updated_at")
                result_dict.update({
                    "_id": qa_pair_data.get("_id"),
                    "session_id": str(qa_pair_data.get("session_id")),
                    "original_answer": qa_pair_data.get("original_answer"),
                    "edited_answer": qa_pair_data.get("edited_answer"),
                    "final_answer": qa_pair_data.get("final_answer", answer_text),
                    "outcome_status": qa_pair_data.get("outcome_status"),
                    "created_at": created_at.isoformat() if created_at else None,
                    "updated_at": updated_at.isoformat() if updated_at else None,
                })
            
            results.append(result_dict)
            question_time = time.time() - question_start_time
            logger.info(
                f"Question {idx + 1}/{len(questions)} completed in {question_time:.2f}s: "
                f"{len(citations)} citations, answer length: {len(answer_text)} chars",
                extra={
                    'question_index': idx,
                    'question_time_ms': round(question_time * 1000, 2),
                    'citations_count': len(citations),
                    'answer_length': len(answer_text),
                    'qa_pair_saved': qa_pair_id is not None
                }
            )
        
        await qa_storage.cleanup()
        
        # Return structured JSON response
        total_time = time.time() - start_time
        response = {
            "questions_processed": len(questions),
            "qa_pairs": results
        }
        
        logger.info(
            f"process_question_batch_standalone completed: {len(results)} Q&A pairs processed in {total_time:.2f}s",
            extra={
                'questions_processed': len(questions),
                'qa_pairs_count': len(results),
                'total_time_ms': round(total_time * 1000, 2)
            }
        )
        return json.dumps(response, indent=2)
        
    except Exception as e:
        total_time = time.time() - start_time
        logger.error(
            f"Error in process_question_batch_standalone: {e}",
            extra={
                'question_count': len(questions),
                'session_id': session_id,
                'total_time_ms': round(total_time * 1000, 2),
                'error': str(e),
                'error_type': type(e).__name__
            },
            exc_info=True
        )
        return json.dumps({
            "error": str(e),
            "questions_processed": 0,
            "qa_pairs": []
        })


@rag_agent.tool
async def process_question_batch(
    ctx: RunContext[StateDeps[RAGState]],
    questions: List[str],
    session_id: Optional[str] = None,
    user_role: Optional[str] = "junior",
    include_history: bool = True
) -> str:
    """
    Process multiple questions and generate answers with citations.
    
    For each question:
    1. Search document database (existing RAG)
    2. Search Q&A history (if enabled)
    3. Generate answer with citations
    4. Save Q&A pair (if senior user)
    
    Args:
        ctx: Agent runtime context with state dependencies
        questions: List of questions to process
        session_id: Optional session ID for saving Q&A pairs
        user_role: User role ("junior" or "senior")
        include_history: Whether to search Q&A history
        
    Returns:
        JSON string with question-answer pairs
    """
    import json
    from src.services.qa_storage import QAStorageService
    from src.settings import load_settings
    
    """
    Process multiple questions and generate answers with citations (agent tool version).
    
    This is a wrapper that calls the standalone function.
    """
    return await process_question_batch_standalone(
        questions=questions,
        session_id=session_id,
        user_role=user_role,
        include_history=include_history
    )
