#!/usr/bin/env python3
"""Streamlit web interface for MongoDB RAG Agent."""

import asyncio
import re
import os
import sys
from typing import List, Dict, Set, Optional
from pathlib import Path
from urllib.parse import quote

# Add project root to Python path for Streamlit
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st  # pyright: ignore[reportMissingImports]
from pydantic_ai import Agent
from pydantic_ai.messages import PartDeltaEvent, PartStartEvent, TextPartDelta
from pydantic_ai.ag_ui import StateDeps
from dotenv import load_dotenv

# Import our agent and dependencies
from src.agent import rag_agent, RAGState, get_citation_metadata, clear_citation_metadata
from src.settings import load_settings

# Load environment variables
load_dotenv(override=True)

# Page configuration
st.set_page_config(
    page_title="MongoDB RAG Agent",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)


def extract_citation_numbers(text: str) -> Set[int]:
    """
    Extract citation numbers from response text.
    Looks for patterns like [1], [2], etc.
    
    Args:
        text: Response text to search
        
    Returns:
        Set of citation numbers found in the text
    """
    pattern = r'(?<![Ss]ource:\s)(?<![Dd]ocument\s)\[(\d{1,3})\]'
    matches = re.findall(pattern, text)
    citation_numbers = {int(match) for match in matches}
    return citation_numbers


def extract_citation_tracker_ids(text: str) -> List[str]:
    """
    Extract citation tracker IDs from tool result text.
    Looks for pattern: <CITATION_TRACKER_ID:uuid>
    
    Args:
        text: Tool result text
        
    Returns:
        List of citation tracker IDs found
    """
    pattern = r'<CITATION_TRACKER_ID:([a-f0-9-]+)>'
    matches = re.findall(pattern, text)
    return matches


def format_citations(
    citations: List[Dict[str, str]],
    citation_numbers: Set[int],
    show_full: bool,
    documents_folder: str = "documents"
) -> List[Dict[str, str]]:
    """
    Format citations for display.
    
    Args:
        citations: List of citation metadata dictionaries
        citation_numbers: Set of citation numbers referenced in response
        show_full: Whether to show full citations (True) or simple (False)
        documents_folder: Path to documents folder
        
    Returns:
        List of dictionaries with 'text' and 'view_url' keys
    """
    if not citations or not citation_numbers:
        return []
    
    # Filter citations to only those referenced
    referenced_citations = [
        cit for cit in citations 
        if cit['citation_number'] in citation_numbers
    ]
    
    # Sort by citation number
    referenced_citations.sort(key=lambda x: x['citation_number'])
    
    formatted = []
    for cit in referenced_citations:
        citation_num = cit['citation_number']
        title = cit['title']
        source = cit['source']
        
        # Create Streamlit page URL for viewing document
        # URL encode the source path
        encoded_source = quote(source)
        view_url = f"/view_document?file={encoded_source}"
        
        if show_full:
            citation_text = f"[{citation_num}] {title} - Source: {source}"
        else:
            citation_text = f"[{citation_num}] {title}"
        
        formatted.append({
            'text': citation_text,
            'view_url': view_url,
            'source': source
        })
    
    return formatted


def initialize_session_state():
    """Initialize session state variables."""
    if "message_history" not in st.session_state:
        st.session_state.message_history = []
    
    if "rag_state" not in st.session_state:
        st.session_state.rag_state = RAGState()
    
    if "deps" not in st.session_state:
        st.session_state.deps = StateDeps[RAGState](state=st.session_state.rag_state)
    
    if "initialized" not in st.session_state:
        st.session_state.initialized = True


async def stream_agent_response(
    user_input: str,
    deps: StateDeps[RAGState],
    message_history: List
) -> tuple[str, List, List[Dict[str, str]], List[Dict]]:
    """
    Stream agent interaction and collect response with citations and tool calls.

    Args:
        user_input: The user's input text
        deps: StateDeps with RAG state
        message_history: List of ModelRequest/ModelResponse objects for conversation context
    
    Returns:
        Tuple of (response_text, new_messages, citations, tool_calls)
    """
    response_text = ""
    all_citations: List[Dict[str, str]] = []
    tool_calls: List[Dict] = []
    
    try:
        async with rag_agent.iter(
            user_input,
            deps=deps,
            message_history=message_history
        ) as run:
            
            async for node in run:
                # Handle user prompt node
                if Agent.is_user_prompt_node(node):
                    pass
                
                # Handle model request node - stream the response
                elif Agent.is_model_request_node(node):
                    async with node.stream(run.ctx) as request_stream:
                        async for event in request_stream:
                            if isinstance(event, PartStartEvent) and event.part.part_kind == 'text':
                                initial_text = event.part.content
                                if initial_text:
                                    response_text += initial_text
                            
                            elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                                delta_text = event.delta.content_delta
                                if delta_text:
                                    response_text += delta_text
                
                # Handle tool calls
                elif Agent.is_call_tools_node(node):
                    tool_call_info = {
                        "tool_name": "Unknown",
                        "args": {},
                        "status": "calling"
                    }
                    
                    async with node.stream(run.ctx) as tool_stream:
                        tool_result_text = ""
                        async for event in tool_stream:
                            event_type = type(event).__name__
                            
                            if event_type == "FunctionToolCallEvent":
                                if hasattr(event, 'part'):
                                    part = event.part
                                    
                                    if hasattr(part, 'tool_name'):
                                        tool_call_info["tool_name"] = part.tool_name
                                    elif hasattr(part, 'function_name'):
                                        tool_call_info["tool_name"] = part.function_name
                                    elif hasattr(part, 'name'):
                                        tool_call_info["tool_name"] = part.name
                                    
                                    if hasattr(part, 'args'):
                                        tool_call_info["args"] = part.args
                                    elif hasattr(part, 'arguments'):
                                        tool_call_info["args"] = part.arguments
                            
                            elif event_type == "FunctionToolResultEvent":
                                tool_call_info["status"] = "completed"
                                if hasattr(event, 'result'):
                                    tool_result_text = str(event.result)
                                    
                                    # Extract citation tracker IDs
                                    tracker_ids = extract_citation_tracker_ids(tool_result_text)
                                    for tracker_id in tracker_ids:
                                        citations = get_citation_metadata(tracker_id)
                                        all_citations.extend(citations)
                                        clear_citation_metadata(tracker_id)
                    
                    tool_calls.append(tool_call_info)
                
                # Handle end node
                elif Agent.is_end_node(node):
                    pass
        
        # Get new messages from this run
        new_messages = run.result.new_messages()
        
        # Get final output
        final_output = run.result.output if hasattr(run.result, 'output') else str(run.result)
        response = response_text.strip() or final_output
        
        return (response, new_messages, all_citations, tool_calls)
    
    except Exception as e:
        st.error(f"Error: {e}")
        import traceback
        st.exception(e)
        return ("", [], [], [])


async def async_stream_generator(user_input: str, deps: StateDeps[RAGState], message_history: List):
    """Async generator for streaming response text."""
    response_text = ""
    
    async with rag_agent.iter(
        user_input,
        deps=deps,
        message_history=message_history
    ) as run:
        
        async for node in run:
            if Agent.is_model_request_node(node):
                async with node.stream(run.ctx) as request_stream:
                    async for event in request_stream:
                        if isinstance(event, PartStartEvent) and event.part.part_kind == 'text':
                            initial_text = event.part.content
                            if initial_text:
                                yield initial_text
                                response_text += initial_text
                        
                        elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                            delta_text = event.delta.content_delta
                            if delta_text:
                                yield delta_text
                                response_text += delta_text


def display_welcome():
    """Display welcome message."""
    settings = load_settings()
    
    st.markdown("""
    <div style='background-color: #1E3A8A; padding: 20px; border-radius: 10px; margin-bottom: 20px;'>
        <h1 style='color: white; margin: 0;'>🔍 MongoDB RAG Agent</h1>
        <p style='color: #93C5FD; margin: 5px 0 0 0;'>Intelligent knowledge base search with MongoDB Atlas Vector Search</p>
        <p style='color: #BFDBFE; margin: 5px 0 0 0; font-size: 0.9em;'>LLM: {}</p>
    </div>
    """.format(settings.llm_model), unsafe_allow_html=True)


def display_sidebar():
    """Display sidebar with system information."""
    with st.sidebar:
        st.title("⚙️ System Info")
        
        try:
            settings = load_settings()
            st.markdown("### Configuration")
            st.text(f"LLM Provider: {settings.llm_provider}")
            st.text(f"LLM Model: {settings.llm_model}")
            st.text(f"Embedding Model: {settings.embedding_model}")
            st.text(f"Default Match Count: {settings.default_match_count}")
            st.text(f"Default Text Weight: {settings.default_text_weight}")
            
            st.markdown("---")
            
            if st.button("🗑️ Clear Chat", use_container_width=True):
                st.session_state.message_history = []
                st.rerun()
            
            st.markdown("---")
            st.markdown("### About")
            st.caption("MongoDB RAG Agent provides intelligent document search using hybrid vector and text search.")
            
        except Exception as e:
            st.error(f"Error loading settings: {e}")


def main():
    """Main Streamlit application."""
    # Initialize session state
    initialize_session_state()
    
    # Display welcome message (only once)
    if not st.session_state.message_history:
        display_welcome()
    
    # Display sidebar
    display_sidebar()
    
    # Main chat interface
    st.title("💬 Chat")
    
    # Display chat history
    for message in st.session_state.message_history:
        # Handle different message types from Pydantic AI
        if hasattr(message, 'role'):
            role = message.role
            if hasattr(message, 'content'):
                content = message.content
            else:
                content = str(message)
        elif hasattr(message, 'parts'):
            # Handle ModelRequest/ModelResponse objects
            role = 'assistant' if hasattr(message, 'response') else 'user'
            content = str(message)
        else:
            role = 'user'
            content = str(message)
        
        if role == 'user' or role == 'human':
            with st.chat_message("user"):
                st.write(content)
        else:
            with st.chat_message("assistant"):
                st.write(content)
    
    # Chat input
    if prompt := st.chat_input("Ask a question about your documents..."):
        # Display user message immediately
        with st.chat_message("user"):
            st.write(prompt)
        
        # Display assistant response
        with st.chat_message("assistant"):
            # Create placeholders for streaming response, tool calls, and citations
            response_placeholder = st.empty()
            tool_calls_placeholder = st.container()
            citations_placeholder = st.container()
            
            # Stream the response
            try:
                # Run async function to get full response and metadata
                response_text, new_messages, citations, tool_calls = asyncio.run(
                    stream_agent_response(
                        prompt,
                        st.session_state.deps,
                        st.session_state.message_history
                    )
                )
                
                # Display tool calls if any
                if tool_calls:
                    with tool_calls_placeholder:
                        for tool_call in tool_calls:
                            with st.expander(f"🔧 Tool: {tool_call['tool_name']}", expanded=False):
                                if tool_call['status'] == 'completed':
                                    st.success("✓ Completed")
                                else:
                                    st.info("⏳ Processing...")
                                
                                if tool_call['args']:
                                    st.json(tool_call['args'])
                
                # Display response text
                response_placeholder.write(response_text)
                
                # Extract citation numbers from response
                citation_numbers = extract_citation_numbers(response_text)
                
                # Display citations if any
                if citations and citation_numbers:
                    settings = load_settings()
                    documents_folder = "documents"
                    
                    formatted_citations = format_citations(
                        citations,
                        citation_numbers,
                        settings.show_full_citations,
                        documents_folder
                    )
                    
                    if formatted_citations:
                        with citations_placeholder:
                            st.markdown("---")
                            st.markdown("### 📚 Citations")
                            for citation_data in formatted_citations:
                                citation_text = citation_data['text']
                                view_url = citation_data['view_url']
                                source_file = citation_data['source']
                                
                                # Use Streamlit's page navigation with session state for query params
                                # Create a container with citation text and button
                                col1, col2 = st.columns([3, 1])
                                with col1:
                                    st.markdown(citation_text)
                                with col2:
                                    # Store file in session state and navigate to viewer page
                                    button_key = f"view_doc_{citation_data.get('citation_number', hash(source_file))}"
                                    
                                    if st.button("📄 View Document", key=button_key):
                                        # Store file parameter in session state (persists across page navigation)
                                        st.session_state['view_document_file'] = source_file
                                        # Navigate to viewer page
                                        # Try different page identifier formats
                                        try:
                                            # Try with pages/ prefix
                                            st.switch_page("pages/view_document")
                                        except Exception:
                                            try:
                                                # Try without prefix
                                                st.switch_page("view_document")
                                            except Exception:
                                                # Last resort: use JavaScript to navigate
                                                st.markdown(
                                                    f'<script>window.location.href = "/view_document?file={quote(source_file)}";</script>',
                                                    unsafe_allow_html=True
                                                )
                                                st.stop()
                
                # Add new messages to history
                st.session_state.message_history.extend(new_messages)
                
            except Exception as e:
                st.error(f"Error processing request: {e}")
                import traceback
                st.exception(e)


if __name__ == "__main__":
    main()

