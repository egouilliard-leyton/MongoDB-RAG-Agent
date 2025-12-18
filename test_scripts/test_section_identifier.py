"""Test section identification for Polish tax interpretation documents."""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion.section_identifier import (
    identify_sections,
    classify_section,
    get_section_count,
    extract_section_content
)
from test_scripts.test_utils import (
    load_sample_markdown,
    create_mock_document,
    get_sample_pdf_path
)


def test_identify_sections():
    """Test detection of all H2 headings in markdown."""
    print("\n" + "="*80)
    print("Test: identify_sections()")
    print("="*80)
    
    # Create mock document with known sections
    mock_markdown = """
## Interpretacja indywidualna

Header content here.

## Przepis

Regulation content.

## Zagadnienie

Issue/question content.

## Stanowisko

Interpretation content.

## Analiza

Analysis content.
"""
    
    sections = identify_sections(mock_markdown)
    
    print(f"Identified {len(sections)} sections:")
    for i, section in enumerate(sections, 1):
        print(f"  {i}. {section['title']} (type: {section['type']}, lines: {section['start_line']}-{section['end_line']})")
    
    # Validate
    assert len(sections) == 5, f"Expected 5 sections, got {len(sections)}"
    
    expected_titles = [
        "Interpretacja indywidualna",
        "Przepis",
        "Zagadnienie",
        "Stanowisko",
        "Analiza"
    ]
    
    for i, expected_title in enumerate(expected_titles):
        assert sections[i]['title'] == expected_title, f"Section {i} title mismatch"
    
    print("✓ All H2 headings detected correctly")
    return True


def test_classify_section():
    """Test correct categorization of section types."""
    print("\n" + "="*80)
    print("Test: classify_section()")
    print("="*80)
    
    test_cases = [
        ("Interpretacja indywidualna", "header"),
        ("Przepis", "przepis"),
        ("Przepis art. 26", "przepis"),
        ("Zagadnienie", "zagadnienie"),
        ("Zagadnienie prawne", "zagadnienie"),
        ("Stanowisko", "interpretation"),
        ("Stanowisko organu", "interpretation"),
        ("Analiza", "analysis"),
        ("Podsumowanie", "analysis"),
        ("Inne", "analysis")
    ]
    
    all_passed = True
    
    for heading, expected_type in test_cases:
        section_type = classify_section(heading)
        status = "✓" if section_type == expected_type else "✗"
        print(f"  {status} '{heading}' → {section_type} (expected: {expected_type})")
        
        if section_type != expected_type:
            all_passed = False
    
    if all_passed:
        print("\n✓ All section types classified correctly")
    else:
        print("\n✗ Some section types misclassified")
    
    return all_passed


def test_get_section_count():
    """Test that section count matches number of H2 headings."""
    print("\n" + "="*80)
    print("Test: get_section_count()")
    print("="*80)
    
    # Test with known number of sections
    mock_markdown = """
## Section 1
Content

## Section 2
Content

## Section 3
Content
"""
    
    count = get_section_count(mock_markdown)
    print(f"Section count: {count}")
    
    assert count == 3, f"Expected 3 sections, got {count}"
    
    # Test with no sections
    no_sections_markdown = "Just some content without sections."
    count_zero = get_section_count(no_sections_markdown)
    assert count_zero == 0, f"Expected 0 sections, got {count_zero}"
    
    print("✓ Section count matches H2 headings")
    return True


def test_extract_section_content():
    """Test extraction of content between section boundaries."""
    print("\n" + "="*80)
    print("Test: extract_section_content()")
    print("="*80)
    
    mock_markdown = """Line 0
Line 1
## Section 1
Line 3
Line 4
## Section 2
Line 6
Line 7
Line 8
"""
    
    sections = identify_sections(mock_markdown)
    
    # Extract first section content
    section1_content = extract_section_content(mock_markdown, sections[0])
    print(f"Section 1 content:\n{section1_content}")
    
    assert "## Section 1" in section1_content, "Section 1 heading should be in content"
    assert "Line 3" in section1_content, "Section 1 content should include Line 3"
    assert "Line 4" in section1_content, "Section 1 content should include Line 4"
    assert "## Section 2" not in section1_content, "Section 1 should not include Section 2"
    
    # Extract second section content
    section2_content = extract_section_content(mock_markdown, sections[1])
    print(f"\nSection 2 content:\n{section2_content}")
    
    assert "## Section 2" in section2_content, "Section 2 heading should be in content"
    assert "Line 6" in section2_content, "Section 2 content should include Line 6"
    assert "Line 7" in section2_content, "Section 2 content should include Line 7"
    assert "Line 8" in section2_content, "Section 2 content should include Line 8"
    
    print("✓ Section content extracted correctly")
    return True


def test_edge_cases():
    """Test edge cases: no sections, single section, etc."""
    print("\n" + "="*80)
    print("Test: Edge cases")
    print("="*80)
    
    # Test 1: No sections
    print("\n1. Testing document with no sections...")
    no_sections = "Just some content without any headings."
    sections = identify_sections(no_sections)
    assert len(sections) == 0, f"Expected 0 sections, got {len(sections)}"
    print("  ✓ No sections handled correctly")
    
    # Test 2: Single section
    print("\n2. Testing document with single section...")
    single_section = """
## Single Section
Content here.
"""
    sections = identify_sections(single_section)
    assert len(sections) == 1, f"Expected 1 section, got {len(sections)}"
    assert sections[0]['end_line'] >= sections[0]['start_line'], "End line should be >= start line"
    print("  ✓ Single section handled correctly")
    
    # Test 3: Sections with empty content
    print("\n3. Testing sections with empty content...")
    empty_sections = """
## Section 1

## Section 2

## Section 3
"""
    sections = identify_sections(empty_sections)
    assert len(sections) == 3, f"Expected 3 sections, got {len(sections)}"
    print("  ✓ Empty sections handled correctly")
    
    # Test 4: Nested headings (should only detect H2)
    print("\n4. Testing nested headings (H2 only)...")
    nested_headings = """
## H2 Section 1
### H3 Subsection
## H2 Section 2
#### H4 Sub-subsection
"""
    sections = identify_sections(nested_headings)
    assert len(sections) == 2, f"Expected 2 H2 sections, got {len(sections)}"
    assert sections[0]['title'] == "H2 Section 1", "First section should be H2 Section 1"
    assert sections[1]['title'] == "H2 Section 2", "Second section should be H2 Section 2"
    print("  ✓ Only H2 headings detected (H3/H4 ignored)")
    
    print("\n✓ All edge cases handled correctly")
    return True


def test_real_pdf_sections():
    """Test section identification on real PDF."""
    print("\n" + "="*80)
    print("Test: Real PDF section identification")
    print("="*80)
    
    try:
        sample_pdf = get_sample_pdf_path()
        print(f"Using sample PDF: {sample_pdf}")
        
        # Load markdown from PDF
        markdown = load_sample_markdown(sample_pdf)
        
        # Identify sections
        sections = identify_sections(markdown)
        
        print(f"Identified {len(sections)} sections:")
        for i, section in enumerate(sections[:10], 1):  # Show first 10
            print(f"  {i}. {section['title']} (type: {section['type']})")
        
        if len(sections) > 10:
            print(f"  ... and {len(sections) - 10} more sections")
        
        # Validate section count
        count = get_section_count(markdown)
        assert count == len(sections), f"Section count mismatch: get_section_count={count}, identify_sections={len(sections)}"
        
        # Check that we have at least some sections
        if len(sections) > 0:
            print(f"\n✓ Successfully identified {len(sections)} sections")
            return True
        else:
            print("\n⚠ No sections found in PDF (may be valid)")
            return True  # Don't fail if PDF has no sections
            
    except FileNotFoundError as e:
        print(f"⚠ Sample PDF not found: {e}")
        print("  Skipping real PDF test")
        return True  # Don't fail if PDF not available
    except Exception as e:
        print(f"✗ Error processing real PDF: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all section identification tests."""
    print("="*80)
    print("Section Identification Tests")
    print("="*80)
    
    results = []
    
    # Run tests
    results.append(("identify_sections", test_identify_sections()))
    results.append(("classify_section", test_classify_section()))
    results.append(("get_section_count", test_get_section_count()))
    results.append(("extract_section_content", test_extract_section_content()))
    results.append(("edge_cases", test_edge_cases()))
    results.append(("real_pdf_sections", test_real_pdf_sections()))
    
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

