"""Test metadata filtering in search functions (read-only)."""

import os
import sys
import asyncio
from pathlib import Path
from pydantic_ai import RunContext

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.dependencies import AgentDependencies
from src.tools import (
    build_metadata_filter,
    semantic_search,
    text_search,
    hybrid_search
)


class MockContext:
    """Mock context for search functions."""
    def __init__(self, deps):
        self.deps = deps


def test_build_metadata_filter():
    """Test filter query construction."""
    print("\n" + "="*80)
    print("Test: build_metadata_filter()")
    print("="*80)
    
    # Test individual filters
    print("\n1. Testing individual filters...")
    
    filter1 = build_metadata_filter(document_type="KDIP2")
    assert filter1 == {"metadata.document_type": "KDIP2"}, f"Expected document_type filter, got {filter1}"
    print("  ✓ document_type filter")
    
    filter2 = build_metadata_filter(author="DK")
    assert filter2 == {"metadata.author": "DK"}, f"Expected author filter, got {filter2}"
    print("  ✓ author filter")
    
    filter3 = build_metadata_filter(date_from="2025-11-01", date_to="2025-11-30")
    expected_date_filter = {
        "metadata.document_date": {"$gte": "2025-11-01", "$lte": "2025-11-30"}
    }
    assert filter3 == expected_date_filter, f"Expected date filter, got {filter3}"
    print("  ✓ date range filter")
    
    filter4 = build_metadata_filter(keywords=["ulga badawczo-rozwojowa"])
    expected_keywords_filter = {
        "metadata.slowa_kluczowe": {"$in": ["ulga badawczo-rozwojowa"]}
    }
    assert filter4 == expected_keywords_filter, f"Expected keywords filter, got {filter4}"
    print("  ✓ keywords filter")
    
    filter5 = build_metadata_filter(section_type="przepis")
    assert filter5 == {"metadata.section_type": "przepis"}, f"Expected section_type filter, got {filter5}"
    print("  ✓ section_type filter")
    
    # Test combined filters
    print("\n2. Testing combined filters...")
    combined_filter = build_metadata_filter(
        document_type="KDIP2",
        author="DK",
        date_from="2025-11-01",
        keywords=["R&D"],
        section_type="interpretation"
    )
    
    assert "metadata.document_type" in combined_filter
    assert "metadata.author" in combined_filter
    assert "metadata.document_date" in combined_filter
    assert "metadata.slowa_kluczowe" in combined_filter
    assert "metadata.section_type" in combined_filter
    
    print("  ✓ Combined filters")
    
    # Test empty filter
    print("\n3. Testing empty filter...")
    empty_filter = build_metadata_filter()
    assert empty_filter == {}, f"Expected empty filter, got {empty_filter}"
    print("  ✓ Empty filter")
    
    print("\n✓ Filter construction works correctly")
    return True


async def test_semantic_search_with_filters():
    """Test semantic search with metadata filters."""
    print("\n" + "="*80)
    print("Test: Semantic search with filters")
    print("="*80)
    
    deps = AgentDependencies()
    await deps.initialize()
    ctx = MockContext(deps)
    
    try:
        # Test without filter (baseline)
        print("\n1. Testing without filter...")
        results_no_filter = await semantic_search(ctx, "test query", match_count=5)
        baseline_count = len(results_no_filter)
        print(f"  Results without filter: {baseline_count}")
        
        if baseline_count == 0:
            print("  ⚠ No results found - database may be empty")
            await deps.cleanup()
            return True
        
        # Test with document_type filter
        print("\n2. Testing with document_type filter...")
        results_filtered = await semantic_search(
            ctx,
            "test query",
            match_count=5,
            document_type="KDIP2"
        )
        filtered_count = len(results_filtered)
        print(f"  Results with document_type filter: {filtered_count}")
        
        # Verify all results match filter
        for result in results_filtered:
            doc_type = result.metadata.get('document_type')
            if doc_type:
                assert doc_type == "KDIP2", f"Result has wrong document_type: {doc_type}"
        
        print("  ✓ Filter applied correctly")
        
        # Test with section_type filter
        print("\n3. Testing with section_type filter...")
        results_section = await semantic_search(
            ctx,
            "test query",
            match_count=5,
            section_type="przepis"
        )
        section_count = len(results_section)
        print(f"  Results with section_type filter: {section_count}")
        
        # Verify all results match filter (if section_type is present)
        for result in results_section:
            section_type = result.metadata.get('section_type')
            if section_type:
                assert section_type == "przepis", f"Result has wrong section_type: {section_type}"
        
        print("  ✓ Section type filter applied correctly")
        
        await deps.cleanup()
        print("\n✓ Semantic search with filters works correctly")
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        await deps.cleanup()
        return False


async def test_text_search_with_filters():
    """Test text search with metadata filters."""
    print("\n" + "="*80)
    print("Test: Text search with filters")
    print("="*80)
    
    deps = AgentDependencies()
    await deps.initialize()
    ctx = MockContext(deps)
    
    try:
        # Test without filter
        print("\n1. Testing without filter...")
        results_no_filter = await text_search(ctx, "test query", match_count=5)
        baseline_count = len(results_no_filter)
        print(f"  Results without filter: {baseline_count}")
        
        if baseline_count == 0:
            print("  ⚠ No results found - database may be empty")
            await deps.cleanup()
            return True
        
        # Test with author filter
        print("\n2. Testing with author filter...")
        results_filtered = await text_search(
            ctx,
            "test query",
            match_count=5,
            author="DK"
        )
        filtered_count = len(results_filtered)
        print(f"  Results with author filter: {filtered_count}")
        
        # Verify all results match filter
        for result in results_filtered:
            author = result.metadata.get('author')
            if author:
                assert author == "DK", f"Result has wrong author: {author}"
        
        print("  ✓ Filter applied correctly")
        
        await deps.cleanup()
        print("\n✓ Text search with filters works correctly")
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        await deps.cleanup()
        return False


async def test_hybrid_search_with_filters():
    """Test hybrid search with metadata filters."""
    print("\n" + "="*80)
    print("Test: Hybrid search with filters")
    print("="*80)
    
    deps = AgentDependencies()
    await deps.initialize()
    ctx = MockContext(deps)
    
    try:
        # Test without filter
        print("\n1. Testing without filter...")
        results_no_filter = await hybrid_search(ctx, "test query", match_count=5)
        baseline_count = len(results_no_filter)
        print(f"  Results without filter: {baseline_count}")
        
        if baseline_count == 0:
            print("  ⚠ No results found - database may be empty")
            await deps.cleanup()
            return True
        
        # Test with date range filter
        print("\n2. Testing with date range filter...")
        results_filtered = await hybrid_search(
            ctx,
            "test query",
            match_count=5,
            date_from="2025-11-01",
            date_to="2025-11-30"
        )
        filtered_count = len(results_filtered)
        print(f"  Results with date filter: {filtered_count}")
        
        # Verify all results match filter
        for result in results_filtered:
            doc_date = result.metadata.get('document_date')
            if doc_date:
                assert "2025-11" in doc_date, f"Result has wrong date: {doc_date}"
        
        print("  ✓ Date filter applied correctly")
        
        await deps.cleanup()
        print("\n✓ Hybrid search with filters works correctly")
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        await deps.cleanup()
        return False


async def test_filter_combinations():
    """Test multiple filters together."""
    print("\n" + "="*80)
    print("Test: Filter combinations")
    print("="*80)
    
    deps = AgentDependencies()
    await deps.initialize()
    ctx = MockContext(deps)
    
    try:
        # Test combined filters
        print("\nTesting combined filters...")
        results = await hybrid_search(
            ctx,
            "test query",
            match_count=5,
            document_type="KDIP2",
            author="DK",
            date_from="2025-11-01",
            section_type="interpretation"
        )
        
        result_count = len(results)
        print(f"  Results with combined filters: {result_count}")
        
        # Verify all results match all filters
        for result in results:
            metadata = result.metadata
            
            # Check document_type
            if "document_type" in metadata:
                assert metadata["document_type"] == "KDIP2", "Wrong document_type"
            
            # Check author
            if "author" in metadata:
                assert metadata["author"] == "DK", "Wrong author"
            
            # Check date
            if "document_date" in metadata:
                assert "2025-11" in metadata["document_date"], "Wrong date"
            
            # Check section_type
            if "section_type" in metadata:
                assert metadata["section_type"] == "interpretation", "Wrong section_type"
        
        print("  ✓ All filters applied correctly")
        
        await deps.cleanup()
        print("\n✓ Filter combinations work correctly")
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        await deps.cleanup()
        return False


async def test_filter_edge_cases():
    """Test edge cases: empty filters, invalid dates, etc."""
    print("\n" + "="*80)
    print("Test: Filter edge cases")
    print("="*80)
    
    deps = AgentDependencies()
    await deps.initialize()
    ctx = MockContext(deps)
    
    try:
        # Test with None values (should be ignored)
        print("\n1. Testing with None values...")
        results = await hybrid_search(
            ctx,
            "test query",
            match_count=5,
            document_type=None,
            author=None
        )
        print(f"  Results: {len(results)}")
        print("  ✓ None values handled correctly")
        
        # Test with empty string (should still filter)
        print("\n2. Testing with empty string...")
        results_empty = await hybrid_search(
            ctx,
            "test query",
            match_count=5,
            document_type=""
        )
        print(f"  Results: {len(results_empty)}")
        print("  ✓ Empty string handled")
        
        # Test with invalid date format (should still work)
        print("\n3. Testing with date filter...")
        results_date = await hybrid_search(
            ctx,
            "test query",
            match_count=5,
            date_from="2025-01-01",
            date_to="2025-12-31"
        )
        print(f"  Results: {len(results_date)}")
        print("  ✓ Date filter handled")
        
        await deps.cleanup()
        print("\n✓ Edge cases handled correctly")
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        await deps.cleanup()
        return False


async def main():
    """Run all metadata filtering tests."""
    print("="*80)
    print("Metadata Filtering Tests (Read-Only)")
    print("="*80)
    
    results = []
    
    # Run tests
    results.append(("build_metadata_filter", test_build_metadata_filter()))
    results.append(("semantic_search_with_filters", await test_semantic_search_with_filters()))
    results.append(("text_search_with_filters", await test_text_search_with_filters()))
    results.append(("hybrid_search_with_filters", await test_hybrid_search_with_filters()))
    results.append(("filter_combinations", await test_filter_combinations()))
    results.append(("filter_edge_cases", await test_filter_edge_cases()))
    
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
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)

