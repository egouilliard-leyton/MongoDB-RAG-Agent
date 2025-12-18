"""Test metadata extraction for Polish tax interpretation documents."""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion.metadata_extractor import (
    extract_tax_interpretation_metadata,
    extract_structured_metadata,
    extract_title_enhanced
)
from test_scripts.test_utils import (
    load_sample_markdown,
    create_mock_document,
    assert_metadata_structure,
    get_sample_pdf_path
)


def test_extract_tax_interpretation_metadata():
    """Test extraction of all header fields from sample markdown."""
    print("\n" + "="*80)
    print("Test: extract_tax_interpretation_metadata()")
    print("="*80)
    
    # Create mock document with known structure
    mock_markdown = create_mock_document(
        id_informacji="668085",
        tytul_teza="Czy wydatki na badania i rozwój mogą być uznane za koszty?",
        kategoria="Interpretacja indywidualna",
        status="Aktualna",
        data_publikacji="2025-11-17",
        autor="DK",
        data_wydania="2025-11-17",
        sygnatura="KDIP2-1.4010.514.2025.2.DK",
        slowa_kluczowe=["ulga badawczo-rozwojowa", "R&D"]
    )
    
    # Extract metadata
    metadata = extract_tax_interpretation_metadata(mock_markdown, "test.pdf")
    
    print(f"Extracted metadata: {metadata}")
    
    # Validate structure
    try:
        assert_metadata_structure(metadata)
        print("✓ All required fields present")
    except AssertionError as e:
        print(f"✗ Validation failed: {e}")
        return False
    
    # Validate specific values
    assert metadata["id_informacji"] == "668085", f"Expected id_informacji='668085', got '{metadata.get('id_informacji')}'"
    assert metadata["tytul_teza"] == "Czy wydatki na badania i rozwój mogą być uznane za koszty?", "Title mismatch"
    assert metadata["kategoria"] == "Interpretacja indywidualna", "Category mismatch"
    assert isinstance(metadata["slowa_kluczowe"], list), "Keywords should be a list"
    assert len(metadata["slowa_kluczowe"]) == 2, "Expected 2 keywords"
    
    print("✓ All field values correct")
    return True


def test_extract_structured_metadata():
    """Test parsing of various filename patterns."""
    print("\n" + "="*80)
    print("Test: extract_structured_metadata()")
    print("="*80)
    
    test_cases = [
        {
            "filename": "2025-11-17_0114-KDIP2-1.4010.514.2025.2.DK.pdf",
            "expected": {
                "document_date": "2025-11-17",
                "document_time": "0114",
                "document_type": "KDIP2",
                "document_number": "1.4010.514",
                "document_year": "2025",
                "revision": "2",
                "author": "DK"
            }
        },
        {
            "filename": "2025-11-18_0114-KDIP2-1.4010.555.2025.2.AZ.pdf",
            "expected": {
                "document_date": "2025-11-18",
                "document_type": "KDIP2",
                "author": "AZ"
            }
        },
        {
            "filename": "2025-12-01_0111-KDIB1-3.4010.570.2025.2.AN.pdf",
            "expected": {
                "document_date": "2025-12-01",
                "document_type": "KDIB1-3",
                "author": "AN"
            }
        }
    ]
    
    all_passed = True
    
    for test_case in test_cases:
        print(f"\nTesting filename: {test_case['filename']}")
        metadata = extract_structured_metadata(test_case['filename'])
        
        print(f"Extracted: {metadata}")
        
        # Check expected fields
        for key, expected_value in test_case['expected'].items():
            if key not in metadata:
                print(f"✗ Missing field: {key}")
                all_passed = False
            elif metadata[key] != expected_value:
                print(f"✗ Field {key} mismatch: expected '{expected_value}', got '{metadata[key]}'")
                all_passed = False
            else:
                print(f"  ✓ {key}: {metadata[key]}")
    
    if all_passed:
        print("\n✓ All filename patterns parsed correctly")
    else:
        print("\n✗ Some filename patterns failed")
    
    return all_passed


def test_extract_title_enhanced():
    """Test all 5 fallback strategies for title extraction."""
    print("\n" + "="*80)
    print("Test: extract_title_enhanced()")
    print("="*80)
    
    # Strategy 1: From metadata['tytul_teza'] (best)
    print("\n1. Testing Strategy 1: From metadata['tytul_teza']")
    mock_markdown = create_mock_document(tytul_teza="Test title from tytul_teza")
    metadata = extract_tax_interpretation_metadata(mock_markdown, "test.pdf")
    title = extract_title_enhanced(mock_markdown, "test.pdf", metadata)
    assert title == "Test title from tytul_teza", f"Expected 'Test title from tytul_teza', got '{title}'"
    print(f"  ✓ Title: {title}")
    
    # Strategy 2: Parse header section directly
    print("\n2. Testing Strategy 2: Parse header section directly")
    mock_markdown2 = """
ID informacji:
123456

Tytuł (teza):
Test title from header section

Autor informacji:
DK
"""
    title2 = extract_title_enhanced(mock_markdown2, "test.pdf", None)
    assert "Test title from header section" in title2, f"Expected title containing 'Test title from header section', got '{title2}'"
    print(f"  ✓ Title: {title2}")
    
    # Strategy 3: Use document number + type from filename
    print("\n3. Testing Strategy 3: Document number + type from filename")
    mock_markdown3 = "Some content without title"
    metadata3 = extract_structured_metadata("2025-11-17_0114-KDIP2-1.4010.514.2025.2.DK.pdf")
    title3 = extract_title_enhanced(mock_markdown3, "2025-11-17_0114-KDIP2-1.4010.514.2025.2.DK.pdf", metadata3)
    assert "KDIP2" in title3 and "1.4010.514" in title3, f"Expected title with document type and number, got '{title3}'"
    print(f"  ✓ Title: {title3}")
    
    # Strategy 4: First H2 heading (skip generic)
    print("\n4. Testing Strategy 4: First H2 heading")
    mock_markdown4 = """
## Interpretacja indywidualna

## Actual Title Section

Content here
"""
    title4 = extract_title_enhanced(mock_markdown4, "test.pdf", None)
    assert title4 == "Actual Title Section", f"Expected 'Actual Title Section', got '{title4}'"
    print(f"  ✓ Title: {title4}")
    
    # Strategy 5: Fallback to filename
    print("\n5. Testing Strategy 5: Fallback to filename")
    mock_markdown5 = "Content without any structure"
    title5 = extract_title_enhanced(mock_markdown5, "test_document.pdf", None)
    assert "test_document" in title5, f"Expected title containing 'test_document', got '{title5}'"
    print(f"  ✓ Title: {title5}")
    
    print("\n✓ All title extraction strategies work correctly")
    return True


def test_keywords_extraction():
    """Test that keywords are extracted as an array."""
    print("\n" + "="*80)
    print("Test: Keywords extraction")
    print("="*80)
    
    mock_markdown = create_mock_document(
        slowa_kluczowe=["keyword1", "keyword2", "keyword3"]
    )
    
    metadata = extract_tax_interpretation_metadata(mock_markdown, "test.pdf")
    
    print(f"Extracted keywords: {metadata.get('slowa_kluczowe')}")
    
    assert "slowa_kluczowe" in metadata, "Keywords field missing"
    assert isinstance(metadata["slowa_kluczowe"], list), f"Keywords should be list, got {type(metadata['slowa_kluczowe'])}"
    assert len(metadata["slowa_kluczowe"]) == 3, f"Expected 3 keywords, got {len(metadata['slowa_kluczowe'])}"
    assert metadata["slowa_kluczowe"] == ["keyword1", "keyword2", "keyword3"], "Keywords mismatch"
    
    print("✓ Keywords extracted correctly as array")
    return True


def test_missing_fields():
    """Test handling of documents with missing header fields."""
    print("\n" + "="*80)
    print("Test: Missing fields handling")
    print("="*80)
    
    # Create markdown with only some fields
    minimal_markdown = """
ID informacji:
123456

Tytuł (teza):
Minimal document title
"""
    
    metadata = extract_tax_interpretation_metadata(minimal_markdown, "test.pdf")
    
    print(f"Extracted metadata: {metadata}")
    
    # Should have at least id_informacji and tytul_teza
    assert "id_informacji" in metadata, "id_informacji should be present"
    assert "tytul_teza" in metadata, "tytul_teza should be present"
    assert metadata["id_informacji"] == "123456", "id_informacji mismatch"
    assert metadata["tytul_teza"] == "Minimal document title", "tytul_teza mismatch"
    
    # Missing fields should not cause errors
    print("✓ Missing fields handled gracefully")
    return True


def test_real_pdf_extraction():
    """Test metadata extraction from real PDF file."""
    print("\n" + "="*80)
    print("Test: Real PDF extraction")
    print("="*80)
    
    try:
        sample_pdf = get_sample_pdf_path()
        print(f"Using sample PDF: {sample_pdf}")
        
        # Load markdown from PDF
        markdown = load_sample_markdown(sample_pdf, max_lines=200)
        
        # Extract metadata
        metadata = extract_tax_interpretation_metadata(markdown, sample_pdf)
        
        print(f"Extracted metadata: {metadata}")
        
        # Check if we got at least some fields
        if metadata:
            print(f"✓ Successfully extracted {len(metadata)} metadata fields")
            if "id_informacji" in metadata:
                print(f"  ID: {metadata['id_informacji']}")
            if "tytul_teza" in metadata:
                print(f"  Title: {metadata['tytul_teza'][:100]}...")
            return True
        else:
            print("✗ No metadata extracted")
            return False
            
    except FileNotFoundError as e:
        print(f"⚠ Sample PDF not found: {e}")
        print("  Skipping real PDF test")
        return True  # Don't fail if PDF not available
    except Exception as e:
        print(f"✗ Error extracting from real PDF: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all metadata extraction tests."""
    print("="*80)
    print("Metadata Extraction Tests")
    print("="*80)
    
    results = []
    
    # Run tests
    results.append(("extract_tax_interpretation_metadata", test_extract_tax_interpretation_metadata()))
    results.append(("extract_structured_metadata", test_extract_structured_metadata()))
    results.append(("extract_title_enhanced", test_extract_title_enhanced()))
    results.append(("keywords_extraction", test_keywords_extraction()))
    results.append(("missing_fields", test_missing_fields()))
    results.append(("real_pdf_extraction", test_real_pdf_extraction()))
    
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
    exit_code = main()
    exit(exit_code)

