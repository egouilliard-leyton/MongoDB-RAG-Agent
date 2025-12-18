"""Main MongoDB RAG agent implementation with shared state."""

from pydantic_ai import Agent, RunContext
from pydantic import BaseModel
from typing import Optional, Dict, List
from collections import OrderedDict
import uuid

from pydantic_ai.ag_ui import StateDeps

from src.providers import get_llm_model
from src.dependencies import AgentDependencies
from src.prompts import MAIN_SYSTEM_PROMPT
from src.tools import semantic_search, hybrid_search, text_search, SearchResult


class RAGState(BaseModel):
    """Minimal shared state for the RAG agent."""
    pass


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
        
        return "\n".join(response_parts)

    except Exception as e:
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
