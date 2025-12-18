"""
Section identification for Polish tax interpretation documents.

This module identifies and classifies sections in tax interpretation documents
to enable section-aware chunking and retrieval.
"""

import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


def classify_section(heading: str) -> str:
    """
    Classify section type based on heading text.

    Categories:
    - header: Document header/metadata section
    - przepis: Regulation references section
    - zagadnienie: Issue/question section
    - interpretation: Main interpretation content
    - analysis: Legal analysis sections

    Args:
        heading: Section heading text

    Returns:
        Section type string
    """
    heading_lower = heading.lower().strip()

    # Header section
    if heading_lower == "interpretacja indywidualna":
        return "header"

    # Przepis (Regulation) section
    if heading_lower.startswith("przepis"):
        return "przepis"

    # Zagadnienie (Issue/Question) section
    if heading_lower.startswith("zagadnienie"):
        return "zagadnienie"

    # Interpretation sections (contain "stanowisko")
    if "stanowisko" in heading_lower:
        return "interpretation"

    # Default to analysis for other sections
    return "analysis"


def identify_sections(markdown_content: str) -> List[Dict]:
    """
    Identify and categorize sections in Polish tax interpretation document.

    Scans markdown for H2 headings (##) and identifies section boundaries.

    Args:
        markdown_content: Document content in markdown format

    Returns:
        List of section dictionaries with:
        - type: Section category (header, przepis, zagadnienie, interpretation, analysis)
        - title: Heading text
        - start_line: Line number where section starts
        - end_line: Line number where section ends (calculated)
    """
    sections = []
    lines = markdown_content.split('\n')

    current_section = None

    for i, line in enumerate(lines):
        # Check for H2 heading (##)
        if line.strip().startswith('##'):
            # If we have a previous section, set its end line
            if current_section is not None:
                current_section['end_line'] = i - 1

            # Extract heading text
            heading = line.strip()[2:].strip()  # Remove "##"

            # Classify section type
            section_type = classify_section(heading)

            # Create new section
            current_section = {
                'type': section_type,
                'title': heading,
                'start_line': i,
                'end_line': len(lines) - 1  # Will be updated when next section found
            }
            sections.append(current_section)

    # Set end line for last section
    if current_section is not None:
        current_section['end_line'] = len(lines) - 1

    logger.debug(f"Identified {len(sections)} sections in document")
    return sections


def extract_section_content(content: str, section: Dict) -> str:
    """
    Extract content between section boundaries.

    Args:
        content: Full document content
        section: Section dictionary with start_line and end_line

    Returns:
        Section content as string
    """
    lines = content.split('\n')
    start = section['start_line']
    end = section['end_line'] + 1  # +1 because end_line is inclusive

    # Ensure valid range
    start = max(0, start)
    end = min(len(lines), end)

    section_lines = lines[start:end]
    return '\n'.join(section_lines)


def get_section_count(content: str) -> int:
    """
    Count the number of sections in a document.

    Args:
        content: Document content

    Returns:
        Number of sections (H2 headings)
    """
    sections = identify_sections(content)
    return len(sections)

