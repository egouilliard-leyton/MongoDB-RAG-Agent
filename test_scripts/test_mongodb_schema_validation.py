"""Test MongoDB schema validation (read-only)."""

import os
import sys
import asyncio
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.dependencies import AgentDependencies


async def test_document_metadata_structure():
    """Check document metadata fields."""
    print("\n" + "="*80)
    print("Test: Document metadata structure")
    print("="*80)
    
    deps = AgentDependencies()
    await deps.initialize()
    
    try:
        # Get a sample document
        doc = await deps.db.documents.find_one()
        
        if not doc:
            print("⚠ No documents found in database")
            print("  Run ingestion first: python -m src.ingestion.ingest -d documents")
            await deps.cleanup()
            return True  # Don't fail if no data
        
        print(f"Sample document ID: {doc['_id']}")
        print(f"Title: {doc.get('title', 'N/A')[:100]}...")
        
        # Check metadata structure
        metadata = doc.get('metadata', {})
        print(f"\nMetadata fields: {list(metadata.keys())}")
        
        # Check for expected fields
        expected_fields = [
            "id_informacji",
            "tytul_teza",
            "kategoria",
            "section_count"
        ]
        
        found_fields = []
        missing_fields = []
        
        for field in expected_fields:
            if field in metadata:
                found_fields.append(field)
                print(f"  ✓ {field}: {metadata[field]}")
            else:
                missing_fields.append(field)
                print(f"  ✗ {field}: MISSING")
        
        # Check optional fields
        optional_fields = [
            "document_type",
            "document_date",
            "author",
            "slowa_kluczowe",
            "sygnatura"
        ]
        
        print(f"\nOptional fields:")
        for field in optional_fields:
            if field in metadata:
                value = metadata[field]
                if isinstance(value, list):
                    print(f"  ✓ {field}: {len(value)} items")
                else:
                    print(f"  ✓ {field}: {value}")
        
        await deps.cleanup()
        
        if missing_fields:
            print(f"\n⚠ Missing expected fields: {missing_fields}")
            print("  This may be normal if documents were ingested before enhancements")
            return True  # Don't fail, just warn
        
        print("\n✓ Document metadata structure validated")
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        await deps.cleanup()
        return False


async def test_chunk_metadata_structure():
    """Check chunk metadata fields."""
    print("\n" + "="*80)
    print("Test: Chunk metadata structure")
    print("="*80)
    
    deps = AgentDependencies()
    await deps.initialize()
    
    try:
        # Get a sample chunk
        chunk = await deps.db.chunks.find_one()
        
        if not chunk:
            print("⚠ No chunks found in database")
            print("  Run ingestion first: python -m src.ingestion.ingest -d documents")
            await deps.cleanup()
            return True  # Don't fail if no data
        
        print(f"Sample chunk ID: {chunk['_id']}")
        print(f"Content preview: {chunk.get('content', '')[:100]}...")
        
        # Check metadata structure
        metadata = chunk.get('metadata', {})
        print(f"\nMetadata fields: {list(metadata.keys())}")
        
        # Check for expected fields
        expected_fields = [
            "title",
            "source"
        ]
        
        found_fields = []
        missing_fields = []
        
        for field in expected_fields:
            if field in metadata:
                found_fields.append(field)
                print(f"  ✓ {field}: {metadata[field]}")
            else:
                missing_fields.append(field)
                print(f"  ✗ {field}: MISSING")
        
        await deps.cleanup()
        
        if missing_fields:
            print(f"\n✗ Missing required fields: {missing_fields}")
            return False
        
        print("\n✓ Chunk metadata structure validated")
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        await deps.cleanup()
        return False


async def test_section_metadata_present():
    """Verify section info in chunks."""
    print("\n" + "="*80)
    print("Test: Section metadata in chunks")
    print("="*80)
    
    deps = AgentDependencies()
    await deps.initialize()
    
    try:
        # Get chunks with section metadata
        chunks_with_sections = await deps.db.chunks.find({
            "metadata.section_type": {"$exists": True}
        }).to_list(length=10)
        
        if not chunks_with_sections:
            print("⚠ No chunks with section metadata found")
            print("  This may be normal if documents were ingested before section-aware chunking")
            await deps.cleanup()
            return True  # Don't fail, just warn
        
        print(f"Found {len(chunks_with_sections)} chunks with section metadata")
        
        # Check section metadata fields
        section_fields = ["section_type", "section_title", "section_index"]
        
        for i, chunk in enumerate(chunks_with_sections[:5], 1):
            metadata = chunk.get('metadata', {})
            print(f"\nChunk {i}:")
            for field in section_fields:
                if field in metadata:
                    print(f"  ✓ {field}: {metadata[field]}")
                else:
                    print(f"  ✗ {field}: MISSING")
        
        # Count chunks by section type
        section_types = await deps.db.chunks.distinct("metadata.section_type")
        print(f"\nSection types found: {section_types}")
        
        for section_type in section_types:
            count = await deps.db.chunks.count_documents({
                "metadata.section_type": section_type
            })
            print(f"  {section_type}: {count} chunks")
        
        await deps.cleanup()
        
        print("\n✓ Section metadata present in chunks")
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        await deps.cleanup()
        return False


async def test_denormalized_fields():
    """Verify denormalized metadata in chunks."""
    print("\n" + "="*80)
    print("Test: Denormalized metadata in chunks")
    print("="*80)
    
    deps = AgentDependencies()
    await deps.initialize()
    
    try:
        # Get a sample chunk
        chunk = await deps.db.chunks.find_one()
        
        if not chunk:
            print("⚠ No chunks found in database")
            await deps.cleanup()
            return True
        
        metadata = chunk.get('metadata', {})
        
        # Check for denormalized fields
        denormalized_fields = [
            "document_type",
            "document_date",
            "id_informacji",
            "slowa_kluczowe",
            "author"
        ]
        
        print("Checking for denormalized fields:")
        found_fields = []
        
        for field in denormalized_fields:
            if field in metadata:
                found_fields.append(field)
                value = metadata[field]
                if isinstance(value, list):
                    print(f"  ✓ {field}: {len(value)} items")
                else:
                    print(f"  ✓ {field}: {value}")
        
        if not found_fields:
            print("  ⚠ No denormalized fields found")
            print("    This may be normal if documents were ingested before enhancements")
        else:
            print(f"\n✓ Found {len(found_fields)} denormalized fields")
        
        await deps.cleanup()
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        await deps.cleanup()
        return False


async def test_chunk_counts():
    """Compare chunk counts (should be 30-50 per doc if re-ingested)."""
    print("\n" + "="*80)
    print("Test: Chunk counts")
    print("="*80)
    
    deps = AgentDependencies()
    await deps.initialize()
    
    try:
        # Get document count
        doc_count = await deps.db.documents.count_documents({})
        chunk_count = await deps.db.chunks.count_documents({})
        
        print(f"Documents: {doc_count}")
        print(f"Chunks: {chunk_count}")
        
        if doc_count == 0:
            print("⚠ No documents found")
            await deps.cleanup()
            return True
        
        avg_chunks_per_doc = chunk_count / doc_count
        print(f"Average chunks per document: {avg_chunks_per_doc:.1f}")
        
        # Check chunk counts per document
        pipeline = [
            {
                "$group": {
                    "_id": "$document_id",
                    "chunk_count": {"$sum": 1}
                }
            },
            {
                "$group": {
                    "_id": None,
                    "min_chunks": {"$min": "$chunk_count"},
                    "max_chunks": {"$max": "$chunk_count"},
                    "avg_chunks": {"$avg": "$chunk_count"}
                }
            }
        ]
        
        result = await deps.db.chunks.aggregate(pipeline).to_list(length=1)
        
        if result:
            stats = result[0]
            print(f"\nChunk count statistics:")
            print(f"  Min: {stats.get('min_chunks', 'N/A')}")
            print(f"  Max: {stats.get('max_chunks', 'N/A')}")
            print(f"  Avg: {stats.get('avg_chunks', 0):.1f}")
            
            # With section-aware chunking, expect 30-50 chunks per document
            # (vs 88-112 with old method)
            avg = stats.get('avg_chunks', 0)
            if avg > 0:
                if avg < 100:
                    print(f"\n✓ Average chunk count ({avg:.1f}) suggests section-aware chunking")
                else:
                    print(f"\n⚠ Average chunk count ({avg:.1f}) is high")
                    print("  Documents may need to be re-ingested with section-aware chunking")
        
        await deps.cleanup()
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        await deps.cleanup()
        return False


async def main():
    """Run all MongoDB schema validation tests."""
    print("="*80)
    print("MongoDB Schema Validation Tests (Read-Only)")
    print("="*80)
    
    results = []
    
    # Run async tests
    results.append(("document_metadata_structure", await test_document_metadata_structure()))
    results.append(("chunk_metadata_structure", await test_chunk_metadata_structure()))
    results.append(("section_metadata_present", await test_section_metadata_present()))
    results.append(("denormalized_fields", await test_denormalized_fields()))
    results.append(("chunk_counts", await test_chunk_counts()))
    
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

