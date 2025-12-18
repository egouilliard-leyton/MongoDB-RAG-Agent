"""Test utilities for PDF structure testing."""

import os
from pathlib import Path
from typing import Dict, List, Any
from docling.document_converter import DocumentConverter


def load_sample_markdown(pdf_path: str, max_lines: int = None) -> str:
    """
    Load sample markdown from a PDF file.
    
    Args:
        pdf_path: Path to PDF file
        max_lines: Optional limit on number of lines to return
        
    Returns:
        Markdown content from PDF
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    converter = DocumentConverter()
    result = converter.convert(pdf_path)
    markdown = result.document.export_to_markdown()
    
    if max_lines:
        lines = markdown.split('\n')
        return '\n'.join(lines[:max_lines])
    
    return markdown


def create_mock_document(
    id_informacji: str = "668085",
    tytul_teza: str = "Test document title",
    kategoria: str = "Interpretacja indywidualna",
    status: str = "Aktualna",
    data_publikacji: str = "2025-11-17",
    autor: str = "DK",
    data_wydania: str = "2025-11-17",
    sygnatura: str = "KDIP2-1.4010.514.2025.2.DK",
    slowa_kluczowe: List[str] = None,
    sections: List[Dict[str, str]] = None
) -> str:
    """
    Create a mock markdown document with known structure.
    
    Args:
        id_informacji: Document ID
        tytul_teza: Document title/question
        kategoria: Category
        status: Status
        data_publikacji: Publication date
        autor: Author
        data_wydania: Issue date
        sygnatura: Signature
        slowa_kluczowe: List of keywords
        sections: List of section dictionaries with 'title' and 'content'
        
    Returns:
        Mock markdown document
    """
    if slowa_kluczowe is None:
        slowa_kluczowe = ["ulga badawczo-rozwojowa", "R&D"]
    
    if sections is None:
        sections = [
            {"title": "Interpretacja indywidualna", "content": "Header section content"},
            {"title": "Przepis", "content": "Regulation content here"},
            {"title": "Zagadnienie", "content": "Issue/question content"},
            {"title": "Stanowisko", "content": "Interpretation content"}
        ]
    
    # Build header section
    header_lines = [
        "ID informacji:",
        id_informacji,
        "",
        "Kategoria informacji:",
        kategoria,
        "",
        "Status informacji:",
        status,
        "",
        "Data publikacji:",
        data_publikacji,
        "",
        "Tytuł (teza):",
        tytul_teza,
        "",
        "Autor informacji:",
        autor,
        "",
        "Data wydania:",
        data_wydania,
        "",
        "Sygnatura:",
        sygnatura,
        "",
        "Słowa kluczowe:"
    ]
    
    # Add keywords
    for keyword in slowa_kluczowe:
        header_lines.append(f"- {keyword}")
    
    header_lines.append("")
    
    # Build sections
    content_lines = []
    for section in sections:
        content_lines.append(f"## {section['title']}")
        content_lines.append("")
        content_lines.append(section['content'])
        content_lines.append("")
    
    # Combine header and content
    full_markdown = '\n'.join(header_lines + content_lines)
    
    return full_markdown


def create_mock_sections() -> List[Dict[str, Any]]:
    """
    Create mock section structures for testing.
    
    Returns:
        List of section dictionaries
    """
    return [
        {
            "type": "header",
            "title": "Interpretacja indywidualna",
            "start_line": 0,
            "end_line": 50
        },
        {
            "type": "przepis",
            "title": "Przepis",
            "start_line": 51,
            "end_line": 100
        },
        {
            "type": "zagadnienie",
            "title": "Zagadnienie",
            "start_line": 101,
            "end_line": 150
        },
        {
            "type": "interpretation",
            "title": "Stanowisko",
            "start_line": 151,
            "end_line": 200
        },
        {
            "type": "analysis",
            "title": "Analiza",
            "start_line": 201,
            "end_line": 250
        }
    ]


def assert_metadata_structure(metadata: Dict[str, Any], required_fields: List[str] = None):
    """
    Assert that metadata has the expected structure.
    
    Args:
        metadata: Metadata dictionary to validate
        required_fields: List of required field names
        
    Raises:
        AssertionError: If structure is invalid
    """
    if required_fields is None:
        required_fields = [
            "id_informacji",
            "tytul_teza",
            "kategoria",
            "status",
            "data_publikacji",
            "autor",
            "data_wydania",
            "sygnatura",
            "slowa_kluczowe"
        ]
    
    missing_fields = [field for field in required_fields if field not in metadata]
    if missing_fields:
        raise AssertionError(
            f"Missing required metadata fields: {missing_fields}. "
            f"Found fields: {list(metadata.keys())}"
        )
    
    # Validate keywords is a list
    if "slowa_kluczowe" in metadata:
        if not isinstance(metadata["slowa_kluczowe"], list):
            raise AssertionError(
                f"slowa_kluczowe should be a list, got {type(metadata['slowa_kluczowe'])}"
            )
    
    # Validate id_informacji is numeric string
    if "id_informacji" in metadata:
        if not metadata["id_informacji"].isdigit():
            raise AssertionError(
                f"id_informacji should be numeric string, got {metadata['id_informacji']}"
            )


def assert_chunk_metadata(
    chunk_metadata: Dict[str, Any],
    required_fields: List[str] = None,
    section_fields: bool = True
):
    """
    Assert that chunk metadata has the expected structure.
    
    Args:
        chunk_metadata: Chunk metadata dictionary to validate
        required_fields: List of required field names
        section_fields: Whether to require section-related fields
        
    Raises:
        AssertionError: If structure is invalid
    """
    if required_fields is None:
        required_fields = ["title", "source"]
    
    if section_fields:
        section_required = ["section_type", "section_title", "section_index"]
        required_fields.extend(section_required)
    
    missing_fields = [field for field in required_fields if field not in chunk_metadata]
    if missing_fields:
        raise AssertionError(
            f"Missing required chunk metadata fields: {missing_fields}. "
            f"Found fields: {list(chunk_metadata.keys())}"
        )
    
    # Validate section_type if present
    if "section_type" in chunk_metadata:
        valid_types = ["header", "przepis", "zagadnienie", "interpretation", "analysis"]
        if chunk_metadata["section_type"] not in valid_types:
            raise AssertionError(
                f"Invalid section_type: {chunk_metadata['section_type']}. "
                f"Expected one of: {valid_types}"
            )
    
    # Validate section_index is integer
    if "section_index" in chunk_metadata:
        if not isinstance(chunk_metadata["section_index"], int):
            raise AssertionError(
                f"section_index should be int, got {type(chunk_metadata['section_index'])}"
            )


def get_sample_pdf_path() -> str:
    """
    Get path to a sample PDF for testing.
    
    Returns:
        Path to sample PDF file
    """
    base_dir = Path(__file__).parent.parent
    sample_pdf = base_dir / "documents" / "2025-11-17_0114-KDIP2-1.4010.514.2025.2.DK.pdf"
    
    if not sample_pdf.exists():
        # Try to find any PDF in documents folder
        documents_dir = base_dir / "documents"
        if documents_dir.exists():
            pdf_files = list(documents_dir.glob("*.pdf"))
            if pdf_files:
                return str(pdf_files[0])
        
        raise FileNotFoundError(
            f"Sample PDF not found at {sample_pdf}. "
            "Please ensure documents folder contains PDF files."
        )
    
    return str(sample_pdf)

