#!/usr/bin/env python3
"""Conversational CLI with real-time streaming and tool call visibility."""

import asyncio
import re
import os
from typing import List, Dict, Set
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.markup import escape

from pydantic_ai import Agent
from pydantic_ai.messages import PartDeltaEvent, PartStartEvent, TextPartDelta
from pydantic_ai.ag_ui import StateDeps
from dotenv import load_dotenv

# Import our agent and dependencies
from src.agent import rag_agent, RAGState, get_citation_metadata, clear_citation_metadata
from src.settings import load_settings

# Load environment variables
load_dotenv(override=True)

console = Console()


async def stream_agent_interaction(
    user_input: str,
    message_history: List,
    deps: StateDeps[RAGState]
) -> tuple[str, List, List[Dict[str, str]], str]:
    """
    Stream agent interaction with real-time tool call display.

    Args:
        user_input: The user's input text
        message_history: List of ModelRequest/ModelResponse objects for conversation context
        deps: StateDeps with RAG state

    Returns:
        Tuple of (streamed_text, updated_message_history, citations, citations_text)
    """
    try:
        return await _stream_agent(user_input, deps, message_history)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        return ("", [], [], "")


def extract_citation_numbers(text: str) -> Set[int]:
    """
    Extract citation numbers from response text.
    Looks for patterns like [1], [2], etc.
    
    Args:
        text: Response text to search
        
    Returns:
        Set of citation numbers found in the text
    """
    # Pattern to match [1], [2], etc.
    # Match [N] where N is 1-3 digits
    # Exclude patterns like [Source: N] or [Document N] by using negative lookbehind
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
) -> List[str]:
    """
    Format citations for display.
    
    Args:
        citations: List of citation metadata dictionaries
        citation_numbers: Set of citation numbers referenced in response
        show_full: Whether to show full citations (True) or simple (False)
        documents_folder: Path to documents folder
        
    Returns:
        List of formatted citation strings
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
        
        # Resolve file path
        # source is relative path like "2025-11-17_0114-KDIP2-1.4010.514.2025.2.DK.pdf"
        # Need to resolve against documents folder
        if os.path.isabs(source):
            file_path = source
        else:
            file_path = os.path.join(documents_folder, source)
        
        # Convert to absolute path and create file:// URL
        abs_path = os.path.abspath(file_path)
        # Normalize path separators for file:// URL
        # On Windows, need file:///C:/path, on Unix file:///path
        if os.name == 'nt':  # Windows
            # Convert C:\path\to\file to /C:/path/to/file
            abs_path_normalized = abs_path.replace('\\', '/')
            if not abs_path_normalized.startswith('/'):
                abs_path_normalized = '/' + abs_path_normalized
            file_url = f"file://{abs_path_normalized}"
        else:  # Unix/Mac
            file_url = f"file://{abs_path}"
        
        # Format as plain text with file:// URL (Rich will still render it as hyperlink)
        if show_full:
            # Full mode: [N] Title (file:///path/to/file.pdf) - Source: relative/path
            formatted.append(
                f"[{citation_num}] {title} ({file_url}) - Source: {source}"
            )
        else:
            # Simple mode: [N] Title (file:///path/to/file.pdf)
            formatted.append(
                f"[{citation_num}] {title} ({file_url})"
            )
    
    return formatted


async def _stream_agent(
    user_input: str,
    deps: StateDeps[RAGState],
    message_history: List
) -> tuple[str, List, List[Dict[str, str]], str]:
    """Stream the agent execution and return response with citations appended."""

    response_text = ""
    all_citations: List[Dict[str, str]] = []

    # Stream the agent execution with message history
    async with rag_agent.iter(
        user_input,
        deps=deps,
        message_history=message_history
    ) as run:

        async for node in run:

            # Handle user prompt node
            if Agent.is_user_prompt_node(node):
                pass  # Clean start

            # Handle model request node - stream the thinking process
            elif Agent.is_model_request_node(node):
                # Show assistant prefix at the start
                console.print("[bold blue]Assistant:[/bold blue] ", end="")

                # Stream model request events for real-time text
                async with node.stream(run.ctx) as request_stream:
                    async for event in request_stream:
                        # Handle text part start events
                        if isinstance(event, PartStartEvent) and event.part.part_kind == 'text':
                            initial_text = event.part.content
                            if initial_text:
                                console.print(initial_text, end="")
                                response_text += initial_text

                        # Handle text delta events for streaming
                        elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                            delta_text = event.delta.content_delta
                            if delta_text:
                                console.print(delta_text, end="")
                                response_text += delta_text

                # New line after streaming completes
                console.print()

            # Handle tool calls
            elif Agent.is_call_tools_node(node):
                # Stream tool execution events
                async with node.stream(run.ctx) as tool_stream:
                    tool_result_text = ""
                    async for event in tool_stream:
                        event_type = type(event).__name__

                        if event_type == "FunctionToolCallEvent":
                            # Extract tool name from the event
                            tool_name = "Unknown Tool"
                            args = None

                            # Check if the part attribute contains the tool call
                            if hasattr(event, 'part'):
                                part = event.part

                                # Check for tool name
                                if hasattr(part, 'tool_name'):
                                    tool_name = part.tool_name
                                elif hasattr(part, 'function_name'):
                                    tool_name = part.function_name
                                elif hasattr(part, 'name'):
                                    tool_name = part.name

                                # Check for arguments
                                if hasattr(part, 'args'):
                                    args = part.args
                                elif hasattr(part, 'arguments'):
                                    args = part.arguments

                            console.print(f"  [cyan]Calling tool:[/cyan] [bold]{tool_name}[/bold]")

                            # Show search query if it's a search tool
                            if args and isinstance(args, dict):
                                if 'query' in args:
                                    console.print(f"    [dim]Query:[/dim] {args['query']}")
                                if 'search_type' in args:
                                    console.print(f"    [dim]Type:[/dim] {args['search_type']}")
                                if 'match_count' in args:
                                    console.print(f"    [dim]Results:[/dim] {args['match_count']}")
                            elif args:
                                args_str = str(args)
                                if len(args_str) > 100:
                                    args_str = args_str[:97] + "..."
                                console.print(f"    [dim]Args: {args_str}[/dim]")

                        elif event_type == "FunctionToolResultEvent":
                            console.print(f"  [green]Search completed successfully[/green]")
                            # Extract tool result text if available
                            if hasattr(event, 'result'):
                                tool_result_text = str(event.result)
                                
                                # Extract citation tracker IDs from tool result
                                tracker_ids = extract_citation_tracker_ids(tool_result_text)
                                for tracker_id in tracker_ids:
                                    # Get citation metadata for this tracker ID
                                    citations = get_citation_metadata(tracker_id)
                                    all_citations.extend(citations)
                                    # Clean up tracker after extracting
                                    clear_citation_metadata(tracker_id)

            # Handle end node
            elif Agent.is_end_node(node):
                pass

    # Get new messages from this run to add to history
    new_messages = run.result.new_messages()

    # Get final output
    final_output = run.result.output if hasattr(run.result, 'output') else str(run.result)
    response = response_text.strip() or final_output

    # Extract citation numbers from response
    citation_numbers = extract_citation_numbers(response)
    
    # Append citations to response if any citations were found
    if all_citations and citation_numbers:
        # Reload settings to ensure we get the latest environment variable values
        # (load_dotenv is called at import time, but this ensures fresh read)
        from dotenv import load_dotenv
        load_dotenv(override=True)
        settings = load_settings()
        documents_folder = "documents"  # Default documents folder
        
        formatted_citations = format_citations(
            all_citations,
            citation_numbers,
            settings.show_full_citations,
            documents_folder
        )
        
        if formatted_citations:
            # Build citations section text
            citations_text = "\n\nCitations:\n"
            for citation_line in formatted_citations:
                citations_text += f"{citation_line}\n"
            citations_text = citations_text.rstrip()
            # Append citations section to response
            response += citations_text
        else:
            citations_text = ""
    else:
        citations_text = ""

    # Return response (with citations appended), new messages, and citations metadata
    return (response, new_messages, all_citations, citations_text)


def display_welcome():
    """Display welcome message with configuration info."""
    settings = load_settings()

    welcome = Panel(
        "[bold blue]MongoDB RAG Agent[/bold blue]\n\n"
        "[green]Intelligent knowledge base search with MongoDB Atlas Vector Search[/green]\n"
        f"[dim]LLM: {settings.llm_model}[/dim]\n\n"
        "[dim]Type 'exit' to quit, 'info' for system info, 'clear' to clear screen[/dim]",
        style="blue",
        padding=(1, 2)
    )
    console.print(welcome)
    console.print()


async def main():
    """Main conversation loop."""

    # Show welcome
    display_welcome()

    # Create the state that the agent will use
    state = RAGState()

    # Create StateDeps wrapper with the state
    deps = StateDeps[RAGState](state=state)

    console.print("[bold green]✓[/bold green] Search system initialized\n")

    # Initialize message history with proper Pydantic AI message objects
    message_history = []

    try:
        while True:
            try:
                # Get user input
                user_input = Prompt.ask("[bold green]You").strip()

                # Handle special commands
                if user_input.lower() in ['exit', 'quit', 'q']:
                    console.print("\n[yellow]👋 Goodbye![/yellow]")
                    break

                elif user_input.lower() == 'info':
                    settings = load_settings()
                    console.print(Panel(
                        f"[cyan]LLM Provider:[/cyan] {settings.llm_provider}\n"
                        f"[cyan]LLM Model:[/cyan] {settings.llm_model}\n"
                        f"[cyan]Embedding Model:[/cyan] {settings.embedding_model}\n"
                        f"[cyan]Default Match Count:[/cyan] {settings.default_match_count}\n"
                        f"[cyan]Default Text Weight:[/cyan] {settings.default_text_weight}",
                        title="System Configuration",
                        border_style="magenta"
                    ))
                    continue

                elif user_input.lower() == 'clear':
                    console.clear()
                    display_welcome()
                    continue

                if not user_input:
                    continue

                # Stream the interaction and get response
                response_text, new_messages, citations, citations_text = await stream_agent_interaction(
                    user_input,
                    message_history,
                    deps
                )

                # Add new messages to history (includes both user prompt and agent response)
                message_history.extend(new_messages)

                # Display citations section if it was appended to the response
                if citations_text:
                    # Citations are already in response_text, but we need to display them
                    # Extract citations section (everything after "Citations:\n")
                    citations_section = citations_text.replace("Citations:\n", "").strip()
                    if citations_section:
                        console.print()
                        console.print("[bold]Citations:[/bold]")
                        for line in citations_section.split("\n"):
                            if line.strip():
                                console.print(f"  {line}")

                # Add spacing after response
                console.print()

            except KeyboardInterrupt:
                console.print("\n[yellow]Use 'exit' to quit[/yellow]")
                continue

            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                import traceback
                traceback.print_exc()
                continue

    finally:
        console.print("\n[dim]Goodbye![/dim]")


if __name__ == "__main__":
    asyncio.run(main())
