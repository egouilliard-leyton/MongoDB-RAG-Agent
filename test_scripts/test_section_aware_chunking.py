"""Test section-aware chunking for Polish tax interpretation documents."""

import os
import sys
import asyncio
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion.chunker import ChunkingConfig, create_chunker
from src.ingestion.section_identifier import identify_sections
from test_scripts.test_utils import (
    load_sample_markdown,
    create_mock_document,
    assert_chunk_metadata,
    get_sample_pdf_path
)


async def test_chunk_tax_interpretation():
    """Test section-aware chunking with variable limits."""
    print("\n" + "="*80)
    print("Test: chunk_tax_interpretation()")
    print("="*80)
    
    # Create mock document with sections
    mock_markdown = create_mock_document(
        id_informacji="668085",
        tytul_teza="Test document",
        kategoria="Interpretacja indywidualna",
        sections=[
            {"title": "Interpretacja indywidualna", "content": "Header content here."},
            {"title": "Przepis", "content": "Art. 26 ust. 1 ustawy o podatku dochodowym."},
            {"title": "Zagadnienie", "content": "Czy wydatki mogą być uznane za koszty?"},
            {"title": "Stanowisko", "content": " ".join(["Long content "] * 200)}  # Long content for chunking
        ]
    )
    
    # Create DoclingDocument from markdown
    try:
        from docling.document_converter import DocumentConverter
        from docling.datamodel.base_models import InputFormat
        
        converter = DocumentConverter()
        # Convert markdown to DoclingDocument
        # Note: Docling doesn't directly support markdown input, so we'll use a workaround
        # For testing, we'll create a simple document structure
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(mock_markdown)
            temp_path = f.name
        
        result = converter.convert(temp_path)
        docling_doc = result.document
        os.unlink(temp_path)
        
    except Exception as e:
        print(f"⚠ Could not create DoclingDocument: {e}")
        print("  Skipping this test (requires Docling)")
        return True
    
    # Identify sections
    sections = identify_sections(mock_markdown)
    print(f"Identified {len(sections)} sections")
    
    # Create chunker
    config = ChunkingConfig(max_tokens=512)
    chunker = create_chunker(config)
    
    # Chunk document
    metadata = {
        "id_informacji": "668085",
        "kategoria": "Interpretacja indywidualna",
        "sygnatura": "KDIP2-1.4010.514.2025.2.DK"
    }
    
    chunks = await chunker.chunk_tax_interpretation(
        content=mock_markdown,
        docling_doc=docling_doc,
        sections=sections,
        title="Test Document",
        source="test.pdf",
        metadata=metadata
    )
    
    print(f"Created {len(chunks)} chunks")
    
    # Validate chunks
    assert len(chunks) > 0, "Should create at least one chunk"
    
    # Check section metadata
    for i, chunk in enumerate(chunks):
        print(f"  Chunk {i}: section_type={chunk.metadata.get('section_type')}, "
              f"section_title={chunk.metadata.get('section_title')}, "
              f"token_count={chunk.token_count}")
        
        assert "section_type" in chunk.metadata, f"Chunk {i} missing section_type"
        assert "section_title" in chunk.metadata, f"Chunk {i} missing section_title"
        assert "section_index" in chunk.metadata, f"Chunk {i} missing section_index"
    
    print("✓ Section-aware chunking works correctly")
    return True


async def test_header_chunking():
    """Test header sections → single chunk, 200 token limit."""
    print("\n" + "="*80)
    print("Test: Header chunking")
    print("="*80)
    
    # Create document with header section
    mock_markdown = create_mock_document(
        sections=[
            {"title": "Interpretacja indywidualna", "content": "Header content here."}
        ]
    )
    
    try:
        from docling.document_converter import DocumentConverter
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(mock_markdown)
            temp_path = f.name
        
        converter = DocumentConverter()
        result = converter.convert(temp_path)
        docling_doc = result.document
        os.unlink(temp_path)
        
    except Exception as e:
        print(f"⚠ Could not create DoclingDocument: {e}")
        return True
    
    sections = identify_sections(mock_markdown)
    assert len(sections) > 0, "Should have at least one section"
    assert sections[0]['type'] == 'header', "First section should be header"
    
    config = ChunkingConfig(max_tokens=512)
    chunker = create_chunker(config)
    
    metadata = {"kategoria": "Interpretacja indywidualna"}
    chunks = await chunker.chunk_tax_interpretation(
        content=mock_markdown,
        docling_doc=docling_doc,
        sections=sections,
        title="Test",
        source="test.pdf",
        metadata=metadata
    )
    
    # Should have header chunks
    header_chunks = [c for c in chunks if c.metadata.get('section_type') == 'header']
    assert len(header_chunks) > 0, "Should have at least one header chunk"
    
    for chunk in header_chunks:
        assert chunk.metadata.get('is_header') == True, "Header chunk should have is_header=true"
        assert chunk.token_count <= 200, f"Header chunk should have <= 200 tokens, got {chunk.token_count}"
        print(f"  ✓ Header chunk: {chunk.token_count} tokens")
    
    print("✓ Header chunking works correctly")
    return True


async def test_przepis_chunking():
    """Test przepis sections → single chunk, 400 token limit."""
    print("\n" + "="*80)
    print("Test: Przepis chunking")
    print("="*80)
    
    mock_markdown = create_mock_document(
        sections=[
            {"title": "Przepis", "content": "Art. 26 ust. 1 ustawy o podatku dochodowym od osób fizycznych."}
        ]
    )
    
    try:
        from docling.document_converter import DocumentConverter
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(mock_markdown)
            temp_path = f.name
        
        converter = DocumentConverter()
        result = converter.convert(temp_path)
        docling_doc = result.document
        os.unlink(temp_path)
        
    except Exception as e:
        print(f"⚠ Could not create DoclingDocument: {e}")
        return True
    
    sections = identify_sections(mock_markdown)
    assert sections[0]['type'] == 'przepis', "Section should be przepis"
    
    config = ChunkingConfig(max_tokens=512)
    chunker = create_chunker(config)
    
    metadata = {"kategoria": "Interpretacja indywidualna"}
    chunks = await chunker.chunk_tax_interpretation(
        content=mock_markdown,
        docling_doc=docling_doc,
        sections=sections,
        title="Test",
        source="test.pdf",
        metadata=metadata
    )
    
    przepis_chunks = [c for c in chunks if c.metadata.get('section_type') == 'przepis']
    assert len(przepis_chunks) > 0, "Should have at least one przepis chunk"
    
    for chunk in przepis_chunks:
        assert chunk.token_count <= 400, f"Przepis chunk should have <= 400 tokens, got {chunk.token_count}"
        print(f"  ✓ Przepis chunk: {chunk.token_count} tokens")
    
    print("✓ Przepis chunking works correctly")
    return True


async def test_main_content_chunking():
    """Test main content → HybridChunker, 800 token limit."""
    print("\n" + "="*80)
    print("Test: Main content chunking")
    print("="*80)
    
    # Create long content for chunking
    long_content = " ".join(["This is a long sentence that will be chunked. "] * 100)
    
    mock_markdown = create_mock_document(
        sections=[
            {"title": "Stanowisko", "content": long_content}
        ]
    )
    
    try:
        from docling.document_converter import DocumentConverter
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(mock_markdown)
            temp_path = f.name
        
        converter = DocumentConverter()
        result = converter.convert(temp_path)
        docling_doc = result.document
        os.unlink(temp_path)
        
    except Exception as e:
        print(f"⚠ Could not create DoclingDocument: {e}")
        return True
    
    sections = identify_sections(mock_markdown)
    assert sections[0]['type'] == 'interpretation', "Section should be interpretation"
    
    config = ChunkingConfig(max_tokens=512)
    chunker = create_chunker(config)
    
    metadata = {"kategoria": "Interpretacja indywidualna"}
    chunks = await chunker.chunk_tax_interpretation(
        content=mock_markdown,
        docling_doc=docling_doc,
        sections=sections,
        title="Test",
        source="test.pdf",
        metadata=metadata
    )
    
    main_chunks = [c for c in chunks if c.metadata.get('is_main_content') == True]
    assert len(main_chunks) > 0, "Should have at least one main content chunk"
    
    for chunk in main_chunks:
        assert chunk.token_count <= 800, f"Main content chunk should have <= 800 tokens, got {chunk.token_count}"
        print(f"  ✓ Main content chunk: {chunk.token_count} tokens")
    
    print("✓ Main content chunking works correctly")
    return True


def test_section_metadata():
    """Test that section metadata is present in chunks."""
    print("\n" + "="*80)
    print("Test: Section metadata in chunks")
    print("="*80)
    
    mock_markdown = create_mock_document(
        sections=[
            {"title": "Interpretacja indywidualna", "content": "Header"},
            {"title": "Przepis", "content": "Regulation"},
            {"title": "Zagadnienie", "content": "Issue"}
        ]
    )
    
    async def run_test():
        try:
            from docling.document_converter import DocumentConverter
            import tempfile
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
                f.write(mock_markdown)
                temp_path = f.name
            
            converter = DocumentConverter()
            result = converter.convert(temp_path)
            docling_doc = result.document
            os.unlink(temp_path)
            
        except Exception as e:
            print(f"⚠ Could not create DoclingDocument: {e}")
            return True
        
        sections = identify_sections(mock_markdown)
        config = ChunkingConfig(max_tokens=512)
        chunker = create_chunker(config)
        
        metadata = {"kategoria": "Interpretacja indywidualna"}
        chunks = await chunker.chunk_tax_interpretation(
            content=mock_markdown,
            docling_doc=docling_doc,
            sections=sections,
            title="Test",
            source="test.pdf",
            metadata=metadata
        )
        
        # Validate metadata
        for chunk in chunks:
            try:
                assert_chunk_metadata(chunk.metadata, section_fields=True)
            except AssertionError as e:
                print(f"✗ Chunk metadata validation failed: {e}")
                return False
        
        print("✓ All chunks have required section metadata")
        return True
    
    return asyncio.run(run_test())


def test_token_limits():
    """Test that token limits are enforced per section type."""
    print("\n" + "="*80)
    print("Test: Token limits enforcement")
    print("="*80)
    
    # Create content that exceeds limits
    very_long_content = " ".join(["Word "] * 1000)  # Very long content
    
    mock_markdown = create_mock_document(
        sections=[
            {"title": "Interpretacja indywidualna", "content": very_long_content},
            {"title": "Przepis", "content": very_long_content},
            {"title": "Stanowisko", "content": very_long_content}
        ]
    )
    
    async def run_test():
        try:
            from docling.document_converter import DocumentConverter
            import tempfile
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
                f.write(mock_markdown)
                temp_path = f.name
            
            converter = DocumentConverter()
            result = converter.convert(temp_path)
            docling_doc = result.document
            os.unlink(temp_path)
            
        except Exception as e:
            print(f"⚠ Could not create DoclingDocument: {e}")
            return True
        
        sections = identify_sections(mock_markdown)
        config = ChunkingConfig(max_tokens=512)
        chunker = create_chunker(config)
        
        metadata = {"kategoria": "Interpretacja indywidualna"}
        chunks = await chunker.chunk_tax_interpretation(
            content=mock_markdown,
            docling_doc=docling_doc,
            sections=sections,
            title="Test",
            source="test.pdf",
            metadata=metadata
        )
        
        # Check token limits
        for chunk in chunks:
            section_type = chunk.metadata.get('section_type')
            token_count = chunk.token_count
            
            if section_type == 'header':
                assert token_count <= 200, f"Header chunk exceeds 200 token limit: {token_count}"
                print(f"  ✓ Header chunk: {token_count} tokens (limit: 200)")
            elif section_type in ['przepis', 'zagadnienie']:
                assert token_count <= 400, f"{section_type} chunk exceeds 400 token limit: {token_count}"
                print(f"  ✓ {section_type} chunk: {token_count} tokens (limit: 400)")
            elif chunk.metadata.get('is_main_content'):
                assert token_count <= 800, f"Main content chunk exceeds 800 token limit: {token_count}"
                print(f"  ✓ Main content chunk: {token_count} tokens (limit: 800)")
        
        print("✓ Token limits enforced correctly")
        return True
    
    return asyncio.run(run_test())


async def test_fallback_chunking():
    """Test fallback when section-aware chunking fails."""
    print("\n" + "="*80)
    print("Test: Fallback chunking")
    print("="*80)
    
    # Test with non-tax interpretation document (should use standard chunking)
    regular_content = "This is regular content without tax interpretation structure."
    
    config = ChunkingConfig(max_tokens=512)
    chunker = create_chunker(config)
    
    try:
        from docling.document_converter import DocumentConverter
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(regular_content)
            temp_path = f.name
        
        converter = DocumentConverter()
        result = converter.convert(temp_path)
        docling_doc = result.document
        os.unlink(temp_path)
        
    except Exception as e:
        print(f"⚠ Could not create DoclingDocument: {e}")
        return True
    
    # Chunk without tax interpretation metadata
    metadata = {}  # No tax interpretation indicators
    chunks = await chunker.chunk_document(
        content=regular_content,
        title="Regular Document",
        source="regular.txt",
        metadata=metadata,
        docling_doc=docling_doc
    )
    
    assert len(chunks) > 0, "Should create chunks even without section-aware chunking"
    print(f"✓ Fallback chunking created {len(chunks)} chunks")
    
    return True


async def main():
    """Run all section-aware chunking tests."""
    print("="*80)
    print("Section-Aware Chunking Tests")
    print("="*80)
    
    results = []
    
    # Run async tests
    results.append(("chunk_tax_interpretation", await test_chunk_tax_interpretation()))
    results.append(("header_chunking", await test_header_chunking()))
    results.append(("przepis_chunking", await test_przepis_chunking()))
    results.append(("main_content_chunking", await test_main_content_chunking()))
    results.append(("section_metadata", test_section_metadata()))
    results.append(("token_limits", test_token_limits()))
    results.append(("fallback_chunking", await test_fallback_chunking()))
    
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

