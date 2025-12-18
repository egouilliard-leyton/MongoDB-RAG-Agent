"""
Metadata extraction for Polish tax interpretation documents.

This module extracts structured metadata from:
1. Document headers (ID, publication date, title, keywords, etc.)
2. Filenames (document type, date, author, etc.)
3. Enhanced title extraction with multiple fallback strategies
"""

import os
import re
import logging
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)


def extract_tax_interpretation_metadata(content: str, file_path: str) -> Dict:
    """
    Extract structured metadata from Polish tax interpretation header.

    Parses the header section (first ~50 lines) to extract:
    - id_informacji: Numeric ID
    - kategoria: Category (usually "Interpretacja indywidualna")
    - status: Status (usually "Aktualna")
    - data_publikacji: Publication date (ISO datetime)
    - tytul_teza: The main question/title (most important!)
    - autor: Author name
    - data_wydania: Issue date (ISO datetime)
    - sygnatura: Signature (matches filename pattern)
    - slowa_kluczowe: List of keywords/tags

    Args:
        content: Document content (markdown format)
        file_path: Path to the document file

    Returns:
        Dictionary with extracted metadata fields
    """
    metadata = {}
    lines = content.split('\n')

    # Parse header section (first ~50 lines)
    header_lines = lines[:50]

    # Extract fields using pattern matching
    i = 0
    while i < len(header_lines):
        line = header_lines[i].strip()

        # ID informacji
        if 'ID informacji:' in line or line == 'ID informacji:':
            if i + 1 < len(header_lines):
                id_value = header_lines[i + 1].strip()
                if id_value and id_value.isdigit():
                    metadata['id_informacji'] = id_value

        # Kategoria informacji
        elif 'Kategoria informacji:' in line or line == 'Kategoria informacji:':
            if i + 1 < len(header_lines):
                kategoria = header_lines[i + 1].strip()
                if kategoria:
                    metadata['kategoria'] = kategoria

        # Status informacji
        elif 'Status informacji:' in line or line == 'Status informacji:':
            if i + 1 < len(header_lines):
                status = header_lines[i + 1].strip()
                if status:
                    metadata['status'] = status

        # Data publikacji
        elif 'Data publikacji:' in line or line == 'Data publikacji:':
            if i + 1 < len(header_lines):
                data_pub = header_lines[i + 1].strip()
                if data_pub:
                    metadata['data_publikacji'] = data_pub

        # Tytuł (teza) - THE MOST IMPORTANT FIELD
        elif 'Tytuł (teza):' in line or line == 'Tytuł (teza):':
            # Title can span multiple lines, collect until next field
            title_parts = []
            j = i + 1
            while j < len(header_lines) and j < i + 10:  # Max 10 lines for title
                next_line = header_lines[j].strip()
                # Stop if we hit another field marker
                if next_line and (
                    'Autor informacji:' in next_line or
                    'Data wydania:' in next_line or
                    'Sygnatura:' in next_line or
                    next_line.startswith('##') or
                    (next_line.startswith('-') and j > i + 3)  # Keywords start with -
                ):
                    break
                if next_line:
                    title_parts.append(next_line)
                j += 1
            if title_parts:
                metadata['tytul_teza'] = ' '.join(title_parts).strip()

        # Autor informacji
        elif 'Autor informacji:' in line or line == 'Autor informacji:':
            if i + 1 < len(header_lines):
                autor = header_lines[i + 1].strip()
                # Remove leading dash if present
                if autor.startswith('-'):
                    autor = autor[1:].strip()
                if autor:
                    metadata['autor'] = autor

        # Data wydania
        elif 'Data wydania:' in line or line == 'Data wydania:':
            if i + 1 < len(header_lines):
                data_wyd = header_lines[i + 1].strip()
                if data_wyd:
                    metadata['data_wydania'] = data_wyd

        # Sygnatura
        elif 'Sygnatura:' in line or line == 'Sygnatura:':
            if i + 1 < len(header_lines):
                sygnatura = header_lines[i + 1].strip()
                if sygnatura:
                    metadata['sygnatura'] = sygnatura

        # Słowa kluczowe (Keywords)
        elif 'Słowa kluczowe:' in line or line == 'Słowa kluczowe:':
            keywords = []
            j = i + 1
            # Collect keywords until we hit another section or non-keyword line
            while j < len(header_lines) and j < i + 20:
                kw_line = header_lines[j].strip()
                # Keywords are bulleted items starting with "-"
                if kw_line.startswith('-'):
                    keyword = kw_line[1:].strip()
                    if keyword:
                        keywords.append(keyword)
                # Stop if we hit a section marker or non-keyword content
                elif kw_line.startswith('##') or (kw_line and not kw_line.startswith('-')):
                    break
                j += 1
            if keywords:
                metadata['slowa_kluczowe'] = keywords

        i += 1

    return metadata


def extract_structured_metadata(file_path: str) -> Dict:
    """
    Extract metadata from filename pattern.

    Pattern: YYYY-MM-DD_HHMM-[TYPE]-[NUMBER].[VERSION].[YEAR].[REVISION].[AUTHOR].pdf
    Example: 2025-11-17_0114-KDIP2-1.4010.514.2025.2.DK.pdf

    Args:
        file_path: Path to the document file

    Returns:
        Dictionary with extracted filename metadata
    """
    filename = os.path.basename(file_path)
    name_without_ext = os.path.splitext(filename)[0]

    # Pattern: 2025-11-17_0114-KDIP2-1.4010.514.2025.2.DK
    # Groups: date, time, type, number, year, revision, author
    pattern = r'(\d{4}-\d{2}-\d{2})_(\d{4})-([A-Z0-9]+)-(\d+\.\d+\.\d+)\.(\d{4})\.(\d+)\.([A-Z]+)'
    match = re.match(pattern, name_without_ext)

    if match:
        return {
            "document_date": match.group(1),
            "document_time": match.group(2),
            "document_type": match.group(3),
            "document_number": match.group(4),
            "document_year": match.group(5),
            "revision": match.group(6),
            "author": match.group(7),
            "parsed_from_filename": True
        }

    # Fallback: try to extract at least the date
    date_pattern = r'(\d{4}-\d{2}-\d{2})'
    date_match = re.search(date_pattern, name_without_ext)
    if date_match:
        return {
            "document_date": date_match.group(1),
            "parsed_from_filename": False
        }

    return {"parsed_from_filename": False}


def extract_title_enhanced(
    content: str,
    file_path: str,
    metadata: Optional[Dict] = None
) -> str:
    """
    Enhanced title extraction with multiple fallback strategies.

    Strategies (in order):
    1. From metadata['tytul_teza'] (best - the actual question/title)
    2. Parse header section directly for "Tytuł (teza):"
    3. Use document number + type from filename metadata
    4. First H2 heading (skip generic "Interpretacja indywidualna")
    5. Fallback to filename

    Args:
        content: Document content (markdown format)
        file_path: Path to the document file
        metadata: Optional pre-extracted metadata dictionary

    Returns:
        Document title
    """
    # Strategy 1: Extract from header metadata (BEST)
    if metadata and metadata.get('tytul_teza'):
        title = metadata['tytul_teza'].strip()
        if title and len(title) > 10:  # Valid title
            logger.debug(f"Title extracted from metadata: {title[:100]}...")
            return title

    # Strategy 2: Parse from header section directly
    lines = content.split('\n')
    for i, line in enumerate(lines[:50]):
        if 'Tytuł (teza):' in line or line.strip() == 'Tytuł (teza):':
            # Collect title from next lines
            title_parts = []
            j = i + 1
            while j < len(lines) and j < i + 10:
                next_line = lines[j].strip()
                # Stop if we hit another field marker
                if next_line and (
                    'Autor informacji:' in next_line or
                    'Data wydania:' in next_line or
                    'Sygnatura:' in next_line or
                    next_line.startswith('##') or
                    (next_line.startswith('-') and j > i + 3)
                ):
                    break
                if next_line:
                    title_parts.append(next_line)
                j += 1
            if title_parts:
                title = ' '.join(title_parts).strip()
                if title and len(title) > 10:
                    logger.debug(f"Title extracted from header: {title[:100]}...")
                    return title

    # Strategy 3: Use document number + type from filename
    if metadata:
        filename_meta = extract_structured_metadata(file_path)
        if filename_meta.get('document_type') and filename_meta.get('document_number'):
            title = f"{filename_meta['document_type']}-{filename_meta['document_number']}"
            logger.debug(f"Title from filename metadata: {title}")
            return title

    # Strategy 4: First H2 heading (usually "Interpretacja indywidualna")
    for line in lines[:20]:
        if line.strip().startswith('## '):
            heading = line.strip()[3:].strip()
            if heading != "Interpretacja indywidualna":  # Skip generic heading
                logger.debug(f"Title from first H2 heading: {heading}")
                return heading

    # Strategy 5: Fallback to filename
    filename_title = os.path.splitext(os.path.basename(file_path))[0]
    logger.debug(f"Title fallback to filename: {filename_title}")
    return filename_title


def extract_outcome_status(content: str) -> Dict[str, Any]:
    """
    Extract success/unsuccess status from document paragraphs.
    
    Scans for patterns like:
    - "interpretacja jest korzystna" / "interpretacja jest niekorzystna"
    - "stanowisko jest pozytywne" / "stanowisko jest negatywne"
    - "interpretacja zakończona sukcesem" / "interpretacja zakończona niepowodzeniem"
    - "interpretacja korzystna" / "interpretacja niekorzystna"
    - "pozytywna interpretacja" / "negatywna interpretacja"
    
    Args:
        content: Document content (markdown format)
        
    Returns:
        {
            "outcome_status": Optional[str] ("successful" | "unsuccessful"),
            "outcome_paragraphs": List[str] (relevant paragraph texts)
        }
    """
    import re
    
    outcome_status = None
    outcome_paragraphs = []
    
    # Patterns indicating successful outcome
    successful_patterns = [
        r'interpretacja\s+(jest\s+)?korzystna',
        r'stanowisko\s+(jest\s+)?pozytywne',
        r'interpretacja\s+zakończona\s+sukcesem',
        r'pozytywna\s+interpretacja',
        r'interpretacja\s+pozytywna',
        r'korzystna\s+interpretacja',
        r'interpretacja\s+(jest\s+)?pozytywna',
    ]
    
    # Patterns indicating unsuccessful outcome
    unsuccessful_patterns = [
        r'interpretacja\s+(jest\s+)?niekorzystna',
        r'stanowisko\s+(jest\s+)?negatywne',
        r'interpretacja\s+zakończona\s+niepowodzeniem',
        r'negatywna\s+interpretacja',
        r'interpretacja\s+negatywna',
        r'niekorzystna\s+interpretacja',
        r'interpretacja\s+(jest\s+)?negatywna',
    ]
    
    # Split content into paragraphs (lines separated by double newlines or single newline after heading)
    paragraphs = re.split(r'\n\n+', content)
    
    # Also check individual lines for patterns
    lines = content.split('\n')
    
    # Check paragraphs
    for para in paragraphs:
        para_lower = para.lower()
        
        # Check for successful patterns
        for pattern in successful_patterns:
            if re.search(pattern, para_lower, re.IGNORECASE):
                if outcome_status != "unsuccessful":  # Don't override if already marked unsuccessful
                    outcome_status = "successful"
                    if para.strip() and para.strip() not in outcome_paragraphs:
                        outcome_paragraphs.append(para.strip())
                break
        
        # Check for unsuccessful patterns
        for pattern in unsuccessful_patterns:
            if re.search(pattern, para_lower, re.IGNORECASE):
                outcome_status = "unsuccessful"
                if para.strip() and para.strip() not in outcome_paragraphs:
                    outcome_paragraphs.append(para.strip())
                break
    
    # Also check lines for quick matches
    if not outcome_status:
        for line in lines:
            line_lower = line.lower()
            
            for pattern in successful_patterns:
                if re.search(pattern, line_lower, re.IGNORECASE):
                    outcome_status = "successful"
                    if line.strip() and line.strip() not in outcome_paragraphs:
                        outcome_paragraphs.append(line.strip())
                    break
            
            if outcome_status:
                break
            
            for pattern in unsuccessful_patterns:
                if re.search(pattern, line_lower, re.IGNORECASE):
                    outcome_status = "unsuccessful"
                    if line.strip() and line.strip() not in outcome_paragraphs:
                        outcome_paragraphs.append(line.strip())
                    break
            
            if outcome_status:
                break
    
    # Limit outcome paragraphs to avoid storing too much
    outcome_paragraphs = outcome_paragraphs[:5]
    
    logger.debug(
        f"Extracted outcome status: {outcome_status}, "
        f"found {len(outcome_paragraphs)} relevant paragraphs"
    )
    
    return {
        "outcome_status": outcome_status,
        "outcome_paragraphs": outcome_paragraphs
    }

