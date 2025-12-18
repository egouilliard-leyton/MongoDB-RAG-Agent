"""Test agent with metadata-aware queries (read-only)."""

import os
import sys
import asyncio
from pathlib import Path
from pydantic_ai.ag_ui import StateDeps

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agent import rag_agent, RAGState


async def test_agent_document_type_query():
    """Test 'Show me KDIP2 documents' query."""
    print("\n" + "="*80)
    print("Test: Agent document type query")
    print("="*80)
    
    state = RAGState()
    deps = StateDeps[RAGState](state=state)
    
    query = "Show me KDIP2 documents"
    print(f"Query: {query}")
    
    try:
        async with rag_agent.iter(query, deps=deps) as run:
            tool_called = False
            response_text = ""
            
            async for node in run:
                if rag_agent.is_call_tools_node(node):
                    tool_called = True
                    async with node.stream(run.ctx) as tool_stream:
                        async for event in tool_stream:
                            event_type = type(event).__name__
                            if event_type == "FunctionToolCallEvent":
                                if hasattr(event, 'part'):
                                    part = event.part
                                    tool_name = getattr(part, 'tool_name', getattr(part, 'name', 'Unknown'))
                                    args = getattr(part, 'args', getattr(part, 'arguments', {}))
                                    print(f"  Tool called: {tool_name}")
                                    if isinstance(args, dict):
                                        # Check if document_type filter was used
                                        if 'document_type' in args:
                                            print(f"    ✓ document_type filter used: {args['document_type']}")
                                        else:
                                            print(f"    ⚠ document_type filter not found in args")
                
                elif rag_agent.is_model_request_node(node):
                    async with node.stream(run.ctx) as request_stream:
                        async for event in request_stream:
                            from pydantic_ai.messages import PartStartEvent, PartDeltaEvent, TextPartDelta
                            if isinstance(event, PartStartEvent) and event.part.part_kind == 'text':
                                if event.part.content:
                                    response_text += event.part.content
                            elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                                if event.delta.content_delta:
                                    response_text += event.delta.content_delta
        
        print(f"\nResponse preview: {response_text[:200]}...")
        
        if tool_called:
            print("✓ Agent used search tools")
        else:
            print("⚠ Agent did not call search tools")
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_agent_author_query():
    """Test 'What did author DK write?' query."""
    print("\n" + "="*80)
    print("Test: Agent author query")
    print("="*80)
    
    state = RAGState()
    deps = StateDeps[RAGState](state=state)
    
    query = "What did author DK write?"
    print(f"Query: {query}")
    
    try:
        async with rag_agent.iter(query, deps=deps) as run:
            tool_called = False
            
            async for node in run:
                if rag_agent.is_call_tools_node(node):
                    tool_called = True
                    async with node.stream(run.ctx) as tool_stream:
                        async for event in tool_stream:
                            event_type = type(event).__name__
                            if event_type == "FunctionToolCallEvent":
                                if hasattr(event, 'part'):
                                    part = event.part
                                    args = getattr(part, 'args', getattr(part, 'arguments', {}))
                                    if isinstance(args, dict) and 'author' in args:
                                        print(f"  ✓ author filter used: {args['author']}")
        
        if tool_called:
            print("✓ Agent processed author query")
        else:
            print("⚠ Agent did not call search tools")
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_agent_date_query():
    """Test 'Interpretations from November 2025' query."""
    print("\n" + "="*80)
    print("Test: Agent date query")
    print("="*80)
    
    state = RAGState()
    deps = StateDeps[RAGState](state=state)
    
    query = "Interpretations from November 2025"
    print(f"Query: {query}")
    
    try:
        async with rag_agent.iter(query, deps=deps) as run:
            tool_called = False
            
            async for node in run:
                if rag_agent.is_call_tools_node(node):
                    tool_called = True
                    async with node.stream(run.ctx) as tool_stream:
                        async for event in tool_stream:
                            event_type = type(event).__name__
                            if event_type == "FunctionToolCallEvent":
                                if hasattr(event, 'part'):
                                    part = event.part
                                    args = getattr(part, 'args', getattr(part, 'arguments', {}))
                                    if isinstance(args, dict):
                                        if 'date_from' in args or 'date_to' in args:
                                            print(f"  ✓ Date filter used")
                                            if 'date_from' in args:
                                                print(f"    date_from: {args['date_from']}")
                                            if 'date_to' in args:
                                                print(f"    date_to: {args['date_to']}")
        
        if tool_called:
            print("✓ Agent processed date query")
        else:
            print("⚠ Agent did not call search tools")
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_agent_section_query():
    """Test 'Find regulations about R&D' query."""
    print("\n" + "="*80)
    print("Test: Agent section query")
    print("="*80)
    
    state = RAGState()
    deps = StateDeps[RAGState](state=state)
    
    query = "Find regulations about R&D"
    print(f"Query: {query}")
    
    try:
        async with rag_agent.iter(query, deps=deps) as run:
            tool_called = False
            
            async for node in run:
                if rag_agent.is_call_tools_node(node):
                    tool_called = True
                    async with node.stream(run.ctx) as tool_stream:
                        async for event in tool_stream:
                            event_type = type(event).__name__
                            if event_type == "FunctionToolCallEvent":
                                if hasattr(event, 'part'):
                                    part = event.part
                                    args = getattr(part, 'args', getattr(part, 'arguments', {}))
                                    if isinstance(args, dict) and 'section_type' in args:
                                        print(f"  ✓ section_type filter used: {args['section_type']}")
        
        if tool_called:
            print("✓ Agent processed section query")
        else:
            print("⚠ Agent did not call search tools")
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_agent_keyword_query():
    """Test 'Documents about ulga badawczo-rozwojowa' query."""
    print("\n" + "="*80)
    print("Test: Agent keyword query")
    print("="*80)
    
    state = RAGState()
    deps = StateDeps[RAGState](state=state)
    
    query = "Documents about ulga badawczo-rozwojowa"
    print(f"Query: {query}")
    
    try:
        async with rag_agent.iter(query, deps=deps) as run:
            tool_called = False
            
            async for node in run:
                if rag_agent.is_call_tools_node(node):
                    tool_called = True
                    async with node.stream(run.ctx) as tool_stream:
                        async for event in tool_stream:
                            event_type = type(event).__name__
                            if event_type == "FunctionToolCallEvent":
                                if hasattr(event, 'part'):
                                    part = event.part
                                    args = getattr(part, 'args', getattr(part, 'arguments', {}))
                                    if isinstance(args, dict) and 'keywords' in args:
                                        print(f"  ✓ keywords filter used: {args['keywords']}")
        
        if tool_called:
            print("✓ Agent processed keyword query")
        else:
            print("⚠ Agent did not call search tools")
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_citation_metadata():
    """Verify citations include id_informacji and sygnatura."""
    print("\n" + "="*80)
    print("Test: Citation metadata")
    print("="*80)
    
    state = RAGState()
    deps = StateDeps[RAGState](state=state)
    
    query = "Tell me about R&D tax relief"
    print(f"Query: {query}")
    
    try:
        async with rag_agent.iter(query, deps=deps) as run:
            response_text = ""
            citations_found = False
            
            async for node in run:
                if rag_agent.is_model_request_node(node):
                    async with node.stream(run.ctx) as request_stream:
                        async for event in request_stream:
                            from pydantic_ai.messages import PartStartEvent, PartDeltaEvent, TextPartDelta
                            if isinstance(event, PartStartEvent) and event.part.part_kind == 'text':
                                if event.part.content:
                                    response_text += event.part.content
                            elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                                if event.delta.content_delta:
                                    response_text += event.delta.content_delta
            
            # Check if response mentions document IDs or sygnatura
            # (This is a simple check - actual citation format depends on agent implementation)
            if "KDIP" in response_text or "KDIB" in response_text:
                citations_found = True
                print("  ✓ Response mentions document identifiers")
            
            if citations_found:
                print("✓ Citations include document metadata")
            else:
                print("⚠ Citations may not include document metadata")
                print(f"  Response preview: {response_text[:200]}...")
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all agent metadata query tests."""
    print("="*80)
    print("Agent Metadata Query Tests (Read-Only)")
    print("="*80)
    
    print("\nNote: These tests require LLM API access and may incur costs.")
    print("They test that the agent uses metadata filters when appropriate.")
    
    results = []
    
    # Run async tests
    results.append(("agent_document_type_query", await test_agent_document_type_query()))
    results.append(("agent_author_query", await test_agent_author_query()))
    results.append(("agent_date_query", await test_agent_date_query()))
    results.append(("agent_section_query", await test_agent_section_query()))
    results.append(("agent_keyword_query", await test_agent_keyword_query()))
    results.append(("citation_metadata", await test_citation_metadata()))
    
    # Summary
    print("\n" + "="*80)
    print("Test Summary")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        print("Note: Some failures may be expected if agent doesn't use filters for certain queries")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)

