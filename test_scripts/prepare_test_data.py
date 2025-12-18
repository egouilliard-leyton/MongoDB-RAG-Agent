"""Prepare test data for PDF structure testing."""

import os
import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from test_scripts.test_utils import load_sample_markdown, create_mock_document


def extract_sample_markdowns(output_dir: str = "test_scripts/test_fixtures"):
    """
    Extract sample markdown from PDFs and save as test fixtures.
    
    Args:
        output_dir: Directory to save test fixtures
    """
    os.makedirs(output_dir, exist_ok=True)
    
    base_dir = Path(__file__).parent.parent
    documents_dir = base_dir / "documents"
    
    if not documents_dir.exists():
        print(f"Documents directory not found: {documents_dir}")
        return
    
    # Get first few PDFs
    pdf_files = sorted(list(documents_dir.glob("*.pdf")))[:3]
    
    if not pdf_files:
        print("No PDF files found in documents directory")
        return
    
    print(f"Extracting markdown from {len(pdf_files)} PDF files...")
    
    for pdf_file in pdf_files:
        try:
            print(f"Processing {pdf_file.name}...")
            
            # Extract full markdown
            markdown = load_sample_markdown(str(pdf_file))
            
            # Extract first 200 lines (header section)
            header_markdown = load_sample_markdown(str(pdf_file), max_lines=200)
            
            # Save to files
            output_file = Path(output_dir) / f"{pdf_file.stem}_full.md"
            header_file = Path(output_dir) / f"{pdf_file.stem}_header.md"
            
            output_file.write_text(markdown, encoding='utf-8')
            header_file.write_text(header_markdown, encoding='utf-8')
            
            print(f"  Saved: {output_file.name}")
            print(f"  Saved: {header_file.name}")
            
        except Exception as e:
            print(f"  Error processing {pdf_file.name}: {e}")
    
    print(f"\nTest fixtures saved to: {output_dir}")


def create_mock_test_documents(output_dir: str = "test_scripts/test_fixtures"):
    """
    Create mock test documents with known structure.
    
    Args:
        output_dir: Directory to save test fixtures
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Create various test scenarios
    test_cases = [
        {
            "name": "complete_document",
            "kwargs": {
                "id_informacji": "668085",
                "tytul_teza": "Czy wydatki na badania i rozwój mogą być uznane za koszty uzyskania przychodu?",
                "kategoria": "Interpretacja indywidualna",
                "status": "Aktualna",
                "data_publikacji": "2025-11-17",
                "autor": "DK",
                "data_wydania": "2025-11-17",
                "sygnatura": "KDIP2-1.4010.514.2025.2.DK",
                "slowa_kluczowe": ["ulga badawczo-rozwojowa", "R&D", "koszty uzyskania przychodu"],
                "sections": [
                    {"title": "Interpretacja indywidualna", "content": "This is the header section."},
                    {"title": "Przepis", "content": "Art. 26 ust. 1 ustawy o podatku dochodowym od osób fizycznych."},
                    {"title": "Zagadnienie", "content": "Czy wydatki na badania i rozwój mogą być uznane za koszty?"},
                    {"title": "Stanowisko", "content": "Tak, wydatki na badania i rozwój mogą być uznane za koszty uzyskania przychodu, jeśli spełniają określone warunki."}
                ]
            }
        },
        {
            "name": "missing_fields",
            "kwargs": {
                "id_informacji": "123456",
                "tytul_teza": "Test document with missing fields",
                "kategoria": "Interpretacja indywidualna",
                "status": None,
                "data_publikacji": None,
                "autor": None,
                "data_wydania": None,
                "sygnatura": None,
                "slowa_kluczowe": [],
                "sections": [
                    {"title": "Interpretacja indywidualna", "content": "Header content"}
                ]
            }
        },
        {
            "name": "no_sections",
            "kwargs": {
                "id_informacji": "789012",
                "tytul_teza": "Document without sections",
                "kategoria": "Interpretacja indywidualna",
                "status": "Aktualna",
                "data_publikacji": "2025-11-18",
                "autor": "AN",
                "data_wydania": "2025-11-18",
                "sygnatura": "KDIB1-3.4010.555.2025.2.AN",
                "slowa_kluczowe": ["test"],
                "sections": []
            }
        }
    ]
    
    print("Creating mock test documents...")
    
    for test_case in test_cases:
        try:
            # Create markdown (handle None values)
            kwargs = {k: v for k, v in test_case["kwargs"].items() if v is not None}
            markdown = create_mock_document(**kwargs)
            
            # Save to file
            output_file = Path(output_dir) / f"mock_{test_case['name']}.md"
            output_file.write_text(markdown, encoding='utf-8')
            
            print(f"  Created: {output_file.name}")
            
        except Exception as e:
            print(f"  Error creating {test_case['name']}: {e}")
    
    print(f"\nMock test documents saved to: {output_dir}")


if __name__ == "__main__":
    print("="*80)
    print("Preparing Test Data")
    print("="*80)
    
    print("\n1. Extracting sample markdown from PDFs...")
    extract_sample_markdowns()
    
    print("\n2. Creating mock test documents...")
    create_mock_test_documents()
    
    print("\n" + "="*80)
    print("Test data preparation complete!")
    print("="*80)

