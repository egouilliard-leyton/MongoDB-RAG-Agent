"""Main MongoDB RAG agent implementation with shared state."""

from pydantic_ai import Agent, RunContext
from pydantic import BaseModel
from typing import Optional, Dict, List
from collections import OrderedDict
import uuid
import logging
import asyncio

from pydantic_ai.ag_ui import StateDeps

from src.providers import get_llm_model
from src.dependencies import AgentDependencies
from src.prompts import MAIN_SYSTEM_PROMPT
from src.tools import semantic_search, hybrid_search, text_search, SearchResult
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
    search_type: Optional[str] = "hybrid"
) -> str:
    """
    Search the knowledge base for relevant information.

    Args:
        ctx: Agent runtime context with state dependencies
        query: Search query text
        match_count: Number of results to return (default: 5)
        search_type: Type of search - "semantic" or "text" or "hybrid" (default: hybrid)

    Returns:
        String containing the retrieved information formatted for the LLM with citation markers [1], [2], etc.
    """
    logger.info(f"search_knowledge_base called: query='{query[:100]}', type={search_type}, match_count={match_count}")
    try:
        # Initialize database connection
        agent_deps = AgentDependencies()
        await agent_deps.initialize()

        # Create a context wrapper for the search tools
        class DepsWrapper:
            def __init__(self, deps):
                self.deps = deps

        deps_ctx = DepsWrapper(agent_deps)

        # Perform the search based on type
        if search_type == "hybrid":
            results = await hybrid_search(
                ctx=deps_ctx,
                query=query,
                match_count=match_count
            )
        elif search_type == "semantic":
            results = await semantic_search(
                ctx=deps_ctx,
                query=query,
                match_count=match_count
            )
        else:
            results = await text_search(
                ctx=deps_ctx,
                query=query,
                match_count=match_count
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
