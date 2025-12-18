"""
Diagnostic script to analyze PDF structure using Docling.
Converts PDFs to markdown and analyzes their organization patterns.
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import Counter
import re

from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.chunking import HybridChunker
from transformers import AutoTokenizer

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

def analyze_markdown_structure(markdown_content: str) -> Dict[str, Any]:
    """Analyze the structure of markdown content."""
    lines = markdown_content.split('\n')
    
    analysis = {
        "total_lines": len(lines),
        "total_chars": len(markdown_content),
        "headings": [],
        "heading_levels": Counter(),
        "tables": [],
        "code_blocks": [],
        "lists": [],
        "paragraphs": [],
        "structure_pattern": []
    }
    
    current_section = []
    in_code_block = False
    in_table = False
    table_start = None
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        # Detect headings
        if stripped.startswith('#'):
            level = len(stripped) - len(stripped.lstrip('#'))
            text = stripped.lstrip('#').strip()
            analysis["headings"].append({
                "line": i + 1,
                "level": level,
                "text": text[:100]  # First 100 chars
            })
            analysis["heading_levels"][level] += 1
            
            # Track section hierarchy
            if current_section:
                analysis["structure_pattern"].append(" > ".join(current_section))
            current_section = current_section[:level-1] + [text[:50]]
        
        # Detect code blocks
        if stripped.startswith('```'):
            in_code_block = not in_code_block
            if in_code_block:
                analysis["code_blocks"].append({"start_line": i + 1})
            else:
                if analysis["code_blocks"]:
                    analysis["code_blocks"][-1]["end_line"] = i + 1
        
        # Detect tables
        if '|' in stripped and '---' in stripped:
            if not in_table:
                in_table = True
                table_start = i + 1
        elif in_table and stripped and '|' not in stripped:
            in_table = False
            if table_start:
                analysis["tables"].append({
                    "start_line": table_start,
                    "end_line": i
                })
                table_start = None
        
        # Detect lists
        if stripped.startswith(('-', '*', '+')):
            analysis["lists"].append({"line": i + 1, "text": stripped[:100]})
    
    # Add final section
    if current_section:
        analysis["structure_pattern"].append(" > ".join(current_section))
    
    return analysis

def analyze_docling_structure(docling_doc) -> Dict[str, Any]:
    """Analyze DoclingDocument structure if available."""
    analysis = {
        "has_structure": False,
        "sections": [],
        "tables": [],
        "metadata": {}
    }
    
    try:
        # Try to access document structure
        # Note: Exact API depends on Docling version
        if hasattr(docling_doc, 'sections'):
            analysis["has_structure"] = True
            analysis["sections"] = len(docling_doc.sections) if docling_doc.sections else 0
        
        if hasattr(docling_doc, 'tables'):
            analysis["tables"] = len(docling_doc.tables) if docling_doc.tables else 0
        
        if hasattr(docling_doc, 'metadata'):
            analysis["metadata"] = dict(docling_doc.metadata) if docling_doc.metadata else {}
        
        # Try to get document structure tree
        if hasattr(docling_doc, 'get_structure'):
            try:
                structure = docling_doc.get_structure()
                analysis["structure_tree"] = str(structure)[:500]
            except:
                pass
                
    except Exception as e:
        analysis["error"] = str(e)
    
    return analysis

def test_chunking(markdown_content: str, docling_doc, max_tokens: int = 512) -> Dict[str, Any]:
    """Test how HybridChunker processes the document."""
    try:
        tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
        chunker = HybridChunker(
            tokenizer=tokenizer,
            max_tokens=max_tokens,
            merge_peers=True
        )
        
        chunks = list(chunker.chunk(dl_doc=docling_doc))
        
        chunk_analysis = {
            "total_chunks": len(chunks),
            "chunks": []
        }
        
        for i, chunk in enumerate(chunks[:5]):  # Analyze first 5 chunks
            contextualized = chunker.contextualize(chunk=chunk)
            token_count = len(tokenizer.encode(contextualized))
            
            # Extract section info from contextualized text
            section_path = None
            lines = contextualized.split('\n')
            for line in lines[:3]:
                if line.strip().startswith('#'):
                    section_path = line.strip()
                    break
            
            chunk_analysis["chunks"].append({
                "chunk_index": i,
                "token_count": token_count,
                "char_count": len(contextualized),
                "section_path": section_path,
                "preview": contextualized[:200] + "..." if len(contextualized) > 200 else contextualized
            })
        
        return chunk_analysis
    except Exception as e:
        return {"error": str(e), "traceback": str(sys.exc_info())}

def diagnose_pdf(file_path: str) -> Dict[str, Any]:
    """Full diagnosis of a PDF file."""
    print(f"\n{'='*80}")
    print(f"Diagnosing: {os.path.basename(file_path)}")
    print(f"{'='*80}")
    
    diagnosis = {
        "filename": os.path.basename(file_path),
        "file_path": file_path,
        "file_size": os.path.getsize(file_path)
    }
    
    try:
        # Convert PDF using Docling
        print("\n[1/4] Converting PDF with Docling...")
        converter = DocumentConverter()
        result = converter.convert(file_path)
        
        markdown_content = result.document.export_to_markdown()
        docling_doc = result.document
        
        diagnosis["conversion"] = {
            "success": True,
            "markdown_length": len(markdown_content),
            "markdown_preview": markdown_content[:1000]  # First 1000 chars
        }
        
        # Analyze markdown structure
        print("[2/4] Analyzing markdown structure...")
        markdown_analysis = analyze_markdown_structure(markdown_content)
        diagnosis["markdown_structure"] = markdown_analysis
        
        # Analyze Docling document structure
        print("[3/4] Analyzing Docling document structure...")
        docling_analysis = analyze_docling_structure(docling_doc)
        diagnosis["docling_structure"] = docling_analysis
        
        # Test chunking
        print("[4/4] Testing chunking with HybridChunker...")
        chunking_analysis = test_chunking(markdown_content, docling_doc)
        diagnosis["chunking"] = chunking_analysis
        
        print(f"\n✓ Diagnosis complete for {os.path.basename(file_path)}")
        
    except Exception as e:
        diagnosis["error"] = str(e)
        diagnosis["traceback"] = str(sys.exc_info())
        print(f"\n✗ Error diagnosing {os.path.basename(file_path)}: {e}")
    
    return diagnosis

def generate_report(diagnoses: List[Dict[str, Any]]) -> str:
    """Generate a comprehensive diagnosis report."""
    report = []
    report.append("# PDF Structure Diagnosis Report\n")
    report.append(f"Analyzed {len(diagnoses)} PDF files\n")
    report.append("=" * 80)
    report.append("\n")
    
    for diag in diagnoses:
        report.append(f"## File: {diag['filename']}\n")
        report.append(f"- File size: {diag['file_size']:,} bytes\n")
        
        if "error" in diag:
            report.append(f"**ERROR**: {diag['error']}\n\n")
            continue
        
        # Conversion info
        if "conversion" in diag:
            conv = diag["conversion"]
            report.append("### Conversion Results\n")
            report.append(f"- Markdown length: {conv['markdown_length']:,} characters\n")
            report.append(f"- Preview:\n```\n{conv['markdown_preview']}\n```\n\n")
        
        # Markdown structure
        if "markdown_structure" in diag:
            ms = diag["markdown_structure"]
            report.append("### Document Structure Analysis\n")
            report.append(f"- Total lines: {ms['total_lines']:,}\n")
            report.append(f"- Total characters: {ms['total_chars']:,}\n")
            report.append(f"- Headings found: {len(ms['headings'])}\n")
            report.append(f"- Tables found: {len(ms['tables'])}\n")
            report.append(f"- Code blocks found: {len(ms['code_blocks'])}\n")
            report.append(f"- Lists found: {len(ms['lists'])}\n\n")
            
            # Heading distribution
            if ms['heading_levels']:
                report.append("**Heading Distribution:**\n")
                for level, count in sorted(ms['heading_levels'].items()):
                    report.append(f"- Level {level} (H{level}): {count} headings\n")
                report.append("\n")
            
            # Sample headings
            if ms['headings']:
                report.append("**Sample Headings:**\n")
                for heading in ms['headings'][:10]:
                    report.append(f"- Line {heading['line']}: {'#' * heading['level']} {heading['text']}\n")
                report.append("\n")
            
            # Structure pattern
            if ms['structure_pattern']:
                report.append("**Document Structure Pattern:**\n")
                for pattern in ms['structure_pattern'][:10]:
                    report.append(f"- {pattern}\n")
                report.append("\n")
        
        # Docling structure
        if "docling_structure" in diag:
            ds = diag["docling_structure"]
            report.append("### Docling Document Structure\n")
            report.append(f"- Has structure: {ds.get('has_structure', False)}\n")
            if ds.get('sections'):
                report.append(f"- Sections detected: {ds['sections']}\n")
            if ds.get('tables'):
                report.append(f"- Tables detected: {ds['tables']}\n")
            if ds.get('metadata'):
                report.append(f"- Metadata: {ds['metadata']}\n")
            report.append("\n")
        
        # Chunking analysis
        if "chunking" in diag:
            ch = diag["chunking"]
            if "error" in ch:
                report.append(f"### Chunking Test\n**ERROR**: {ch['error']}\n\n")
            else:
                report.append("### Chunking Analysis\n")
                report.append(f"- Total chunks created: {ch['total_chunks']}\n")
                report.append("\n**Sample Chunks:**\n")
                for chunk_info in ch.get('chunks', [])[:3]:
                    report.append(f"\n**Chunk {chunk_info['chunk_index']}:**\n")
                    report.append(f"- Tokens: {chunk_info['token_count']}\n")
                    report.append(f"- Characters: {chunk_info['char_count']}\n")
                    if chunk_info.get('section_path'):
                        report.append(f"- Section: {chunk_info['section_path']}\n")
                    report.append(f"- Preview:\n```\n{chunk_info['preview']}\n```\n")
                report.append("\n")
        
        report.append("\n" + "-" * 80 + "\n\n")
    
    # Summary and recommendations
    report.append("# Recommendations\n\n")
    report.append("Based on the analysis above, here are recommendations for:\n")
    report.append("1. Document separation strategy\n")
    report.append("2. Chunking approach\n")
    report.append("3. Metadata extraction\n")
    report.append("4. Indexing strategy\n")
    report.append("5. RAG agent enhancements\n\n")
    
    return "\n".join(report)

def main():
    """Main diagnostic function."""
    documents_folder = "documents"
    
    # Find PDF files
    pdf_files = list(Path(documents_folder).glob("*.pdf"))
    
    if len(pdf_files) < 2:
        print(f"Error: Need at least 2 PDF files, found {len(pdf_files)}")
        return
    
    # Select first 2 PDFs
    selected_pdfs = sorted(pdf_files)[:2]
    
    print(f"Selected PDFs for diagnosis:")
    for pdf in selected_pdfs:
        print(f"  - {pdf.name}")
    
    # Diagnose each PDF
    diagnoses = []
    for pdf_path in selected_pdfs:
        diagnosis = diagnose_pdf(str(pdf_path))
        diagnoses.append(diagnosis)
    
    # Generate report
    report = generate_report(diagnoses)
    
    # Save report
    report_path = "pdf_structure_diagnosis_report.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n{'='*80}")
    print(f"Diagnosis complete! Report saved to: {report_path}")
    print(f"{'='*80}\n")
    
    # Also print summary
    print("\n## Quick Summary\n")
    print(report[:2000])  # First 2000 chars
    print("\n... (full report in file)\n")

if __name__ == "__main__":
    main()

