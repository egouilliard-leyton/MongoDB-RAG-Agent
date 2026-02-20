"""Extract sample content from PDFs to understand structure better."""

import sys
from pathlib import Path
from docling.document_converter import DocumentConverter

sys.path.insert(0, str(Path(__file__).parent))

def extract_sample(file_path: str, max_lines: int = 200):
    """Extract first N lines of markdown."""
    converter = DocumentConverter()
    result = converter.convert(file_path)
    markdown = result.document.export_to_markdown()
    
    lines = markdown.split('\n')
    return '\n'.join(lines[:max_lines])

if __name__ == "__main__":
    pdf1 = "documents/2025-11-17_0114-KDIP2-1.4010.514.2025.2.DK.pdf"
    pdf2 = "documents/2025-11-18_0114-KDIP2-1.4010.555.2025.2.AZ.pdf"
    
    print("="*80)
    print("PDF 1 Sample (first 200 lines):")
    print("="*80)
    print(extract_sample(pdf1, 200))
    
    print("\n\n" + "="*80)
    print("PDF 2 Sample (first 200 lines):")
    print("="*80)
    print(extract_sample(pdf2, 200))

