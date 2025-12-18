"""
Docling HybridChunker implementation for intelligent document splitting.

This module uses Docling's built-in HybridChunker which combines:
- Token-aware chunking (uses actual tokenizer)
- Document structure preservation (headings, sections, tables)
- Semantic boundary respect (paragraphs, code blocks)
- Contextualized output (chunks include heading hierarchy)

Benefits over custom chunking:
- Fast (no LLM API calls)
- Token-precise (not character-based estimates)
- Better for RAG (chunks include document context)
- Battle-tested (maintained by Docling team)
"""

import os
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from dotenv import load_dotenv
from transformers import AutoTokenizer
from docling.chunking import HybridChunker
from docling_core.types.doc import DoclingDocument

from src.ingestion.section_identifier import (
    identify_sections,
    extract_section_content,
    classify_section
)

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class ChunkingConfig:
    """Configuration for DoclingHybridChunker."""
    chunk_size: int = 1000  # Target characters per chunk (used in fallback)
    chunk_overlap: int = 200  # Character overlap between chunks (used in fallback)
    max_chunk_size: int = 2000  # Maximum chunk size (used in fallback)
    min_chunk_size: int = 100  # Minimum chunk size (used in fallback)
    max_tokens: int = 512  # Maximum tokens for embedding models

    def __post_init__(self):
        """Validate configuration."""
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("Chunk overlap must be less than chunk size")
        if self.min_chunk_size <= 0:
            raise ValueError("Minimum chunk size must be positive")


@dataclass
class DocumentChunk:
    """Represents a document chunk with optional embedding."""
    content: str
    index: int
    start_char: int
    end_char: int
    metadata: Dict[str, Any]
    token_count: Optional[int] = None
    embedding: Optional[List[float]] = None  # For embedder compatibility

    def __post_init__(self):
        """Calculate token count if not provided."""
        if self.token_count is None:
            # Rough estimation: ~4 characters per token
            self.token_count = len(self.content) // 4


class DoclingHybridChunker:
    """
    Docling HybridChunker wrapper for intelligent document splitting.

    This chunker uses Docling's built-in HybridChunker which:
    - Respects document structure (sections, paragraphs, tables)
    - Is token-aware (fits embedding model limits)
    - Preserves semantic coherence
    - Includes heading context in chunks
    """

    def __init__(self, config: ChunkingConfig):
        """
        Initialize chunker.

        Args:
            config: Chunking configuration
        """
        self.config = config

        # Initialize tokenizer for token-aware chunking
        model_id = "sentence-transformers/all-MiniLM-L6-v2"
        logger.info(f"Initializing tokenizer: {model_id}")
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)

        # Create HybridChunker
        self.chunker = HybridChunker(
            tokenizer=self.tokenizer,
            max_tokens=config.max_tokens,
            merge_peers=True  # Merge small adjacent chunks
        )

        logger.info(f"HybridChunker initialized (max_tokens={config.max_tokens})")

    def _is_tax_interpretation(self, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Check if document is a Polish tax interpretation.

        Args:
            metadata: Document metadata

        Returns:
            True if document appears to be a tax interpretation
        """
        if not metadata:
            return False

        # Check for tax interpretation indicators
        return (
            metadata.get('kategoria') == 'Interpretacja indywidualna' or
            metadata.get('id_informacji') is not None or
            metadata.get('sygnatura') is not None
        )

    async def chunk_tax_interpretation(
        self,
        content: str,
        docling_doc: DoclingDocument,
        sections: List[Dict],
        title: str,
        source: str,
        metadata: Dict[str, Any]
    ) -> List[DocumentChunk]:
        """
        Chunk Polish tax interpretation with section awareness.

        Uses variable token limits based on section type:
        - Header: single chunk, 200 token limit
        - Przepis/Zagadnienie: single chunk, 400 token limit
        - Main content: HybridChunker with 800 token limit

        Args:
            content: Document content (markdown format)
            docling_doc: DoclingDocument for HybridChunker
            sections: List of section dictionaries from identify_sections()
            title: Document title
            source: Document source
            metadata: Document metadata

        Returns:
            List of document chunks with section metadata
        """
        chunks = []
        base_metadata = {
            "title": title,
            "source": source,
            "chunk_method": "section_aware_hybrid",
            **(metadata or {})
        }

        current_pos = 0
        chunk_index = 0

        for section_idx, section in enumerate(sections):
            section_content = extract_section_content(content, section)
            section_type = section['type']
            section_title = section['title']

            # Determine token limit based on section type
            if section_type == 'header':
                token_limit = 200
                # Header: Single chunk, no chunking needed
                token_count = len(self.tokenizer.encode(section_content))
                if token_count > token_limit:
                    # Truncate if too long (shouldn't happen for headers)
                    encoded = self.tokenizer.encode(section_content)
                    truncated_encoded = encoded[:token_limit]
                    section_content = self.tokenizer.decode(truncated_encoded, skip_special_tokens=True)
                    token_count = len(truncated_encoded)

                chunk_metadata = {
                    **base_metadata,
                    "section_type": section_type,
                    "section_title": section_title,
                    "section_index": section_idx,
                    "is_header": True,
                    "is_main_content": False,
                    "token_count": token_count
                }

                start_char = current_pos
                end_char = start_char + len(section_content)

                chunks.append(DocumentChunk(
                    content=section_content.strip(),
                    index=chunk_index,
                    start_char=start_char,
                    end_char=end_char,
                    metadata=chunk_metadata,
                    token_count=token_count
                ))

                chunk_index += 1
                current_pos = end_char

            elif section_type in ['przepis', 'zagadnienie']:
                # Short sections: Single chunk with 400 token limit
                token_limit = 400
                token_count = len(self.tokenizer.encode(section_content))
                if token_count > token_limit:
                    # Truncate if too long
                    encoded = self.tokenizer.encode(section_content)
                    truncated_encoded = encoded[:token_limit]
                    section_content = self.tokenizer.decode(truncated_encoded, skip_special_tokens=True)
                    token_count = len(truncated_encoded)

                chunk_metadata = {
                    **base_metadata,
                    "section_type": section_type,
                    "section_title": section_title,
                    "section_index": section_idx,
                    "is_header": False,
                    "is_main_content": False,
                    "token_count": token_count
                }

                start_char = current_pos
                end_char = start_char + len(section_content)

                chunks.append(DocumentChunk(
                    content=section_content.strip(),
                    index=chunk_index,
                    start_char=start_char,
                    end_char=end_char,
                    metadata=chunk_metadata,
                    token_count=token_count
                ))

                chunk_index += 1
                current_pos = end_char

            else:
                # Main content: Use HybridChunker with larger token limit (800)
                # Create a temporary HybridChunker with higher token limit
                section_chunker = HybridChunker(
                    tokenizer=self.tokenizer,
                    max_tokens=800,  # Larger for main content
                    merge_peers=True
                )

                try:
                    # For section-level chunking, we need to work with the full doc
                    # but filter chunks to this section. Since HybridChunker works
                    # on DoclingDocument, we'll chunk the section content separately
                    # by creating a simplified approach for section content

                    # Use tokenizer-based chunking for sections (simpler approach)
                    encoded_section = self.tokenizer.encode(section_content)
                    token_limit = 800

                    section_start = 0
                    while section_start < len(encoded_section):
                        section_end = min(section_start + token_limit, len(encoded_section))
                        section_tokens = encoded_section[section_start:section_end]
                        section_text = self.tokenizer.decode(section_tokens, skip_special_tokens=True)

                        token_count = len(section_tokens)

                        chunk_metadata = {
                            **base_metadata,
                            "section_type": section_type,
                            "section_title": section_title,
                            "section_index": section_idx,
                            "is_header": False,
                            "is_main_content": True,
                            "token_count": token_count
                        }

                        start_char = current_pos
                        end_char = start_char + len(section_text)

                        chunks.append(DocumentChunk(
                            content=section_text.strip(),
                            index=chunk_index,
                            start_char=start_char,
                            end_char=end_char,
                            metadata=chunk_metadata,
                            token_count=token_count
                        ))

                        chunk_index += 1
                        current_pos = end_char
                        section_start = section_end

                except Exception as e:
                    logger.warning(f"Failed to chunk section {section_title} with HybridChunker: {e}")
                    # Fallback to simple chunking for this section
                    token_count = len(self.tokenizer.encode(section_content))
                    chunk_metadata = {
                        **base_metadata,
                        "section_type": section_type,
                        "section_title": section_title,
                        "section_index": section_idx,
                        "is_header": False,
                        "is_main_content": True,
                        "token_count": token_count
                    }

                    start_char = current_pos
                    end_char = start_char + len(section_content)

                    chunks.append(DocumentChunk(
                        content=section_content.strip(),
                        index=chunk_index,
                        start_char=start_char,
                        end_char=end_char,
                        metadata=chunk_metadata,
                        token_count=token_count
                    ))

                    chunk_index += 1
                    current_pos = end_char

        # Update total chunks
        for chunk in chunks:
            chunk.metadata["total_chunks"] = len(chunks)

        logger.info(f"Created {len(chunks)} chunks using section-aware chunking")
        return chunks

    async def chunk_document(
        self,
        content: str,
        title: str,
        source: str,
        metadata: Optional[Dict[str, Any]] = None,
        docling_doc: Optional[DoclingDocument] = None
    ) -> List[DocumentChunk]:
        """
        Chunk a document using Docling's HybridChunker.

        Args:
            content: Document content (markdown format)
            title: Document title
            source: Document source
            metadata: Additional metadata
            docling_doc: Optional pre-converted DoclingDocument (for efficiency)

        Returns:
            List of document chunks with contextualized content
        """
        if not content.strip():
            return []

        base_metadata = {
            "title": title,
            "source": source,
            "chunk_method": "hybrid",
            **(metadata or {})
        }

        # Check if this is a tax interpretation document
        if self._is_tax_interpretation(metadata) and docling_doc is not None:
            try:
                # Use section-aware chunking for tax interpretations
                sections = identify_sections(content)
                if sections:
                    logger.info(f"Using section-aware chunking for tax interpretation ({len(sections)} sections)")
                    return await self.chunk_tax_interpretation(
                        content=content,
                        docling_doc=docling_doc,
                        sections=sections,
                        title=title,
                        source=source,
                        metadata=metadata or {}
                    )
            except Exception as e:
                logger.warning(f"Section-aware chunking failed: {e}, falling back to standard chunking")

        # If we don't have a DoclingDocument, we need to create one from markdown
        if docling_doc is None:
            # For markdown content, we need to convert it to DoclingDocument
            # This is a simplified version - in practice, content comes from
            # Docling's document converter in the ingestion pipeline
            logger.warning("No DoclingDocument provided, using simple chunking fallback")
            return self._simple_fallback_chunk(content, base_metadata)

        try:
            # Use HybridChunker to chunk the DoclingDocument
            chunk_iter = self.chunker.chunk(dl_doc=docling_doc)
            chunks = list(chunk_iter)

            # Convert Docling chunks to DocumentChunk objects
            document_chunks = []
            current_pos = 0

            for i, chunk in enumerate(chunks):
                # Get contextualized text (includes heading hierarchy)
                contextualized_text = self.chunker.contextualize(chunk=chunk)

                # Count actual tokens
                token_count = len(self.tokenizer.encode(contextualized_text))

                # Create chunk metadata
                chunk_metadata = {
                    **base_metadata,
                    "total_chunks": len(chunks),
                    "token_count": token_count,
                    "has_context": True  # Flag indicating contextualized chunk
                }

                # Estimate character positions
                start_char = current_pos
                end_char = start_char + len(contextualized_text)

                document_chunks.append(DocumentChunk(
                    content=contextualized_text.strip(),
                    index=i,
                    start_char=start_char,
                    end_char=end_char,
                    metadata=chunk_metadata,
                    token_count=token_count
                ))

                current_pos = end_char

            logger.info(f"Created {len(document_chunks)} chunks using HybridChunker")
            return document_chunks

        except Exception as e:
            logger.error(f"HybridChunker failed: {e}, falling back to simple chunking")
            return self._simple_fallback_chunk(content, base_metadata)

    def _simple_fallback_chunk(
        self,
        content: str,
        base_metadata: Dict[str, Any]
    ) -> List[DocumentChunk]:
        """
        Simple fallback chunking when HybridChunker can't be used.

        This is used when:
        - No DoclingDocument is provided
        - HybridChunker fails

        Args:
            content: Content to chunk
            base_metadata: Base metadata for chunks

        Returns:
            List of document chunks
        """
        chunks = []
        chunk_size = self.config.chunk_size
        overlap = self.config.chunk_overlap

        # Simple sliding window approach
        start = 0
        chunk_index = 0

        while start < len(content):
            end = start + chunk_size

            if end >= len(content):
                # Last chunk
                chunk_text = content[start:]
            else:
                # Try to end at sentence boundary
                chunk_end = end
                for i in range(end, max(start + self.config.min_chunk_size, end - 200), -1):
                    if i < len(content) and content[i] in '.!?\n':
                        chunk_end = i + 1
                        break
                chunk_text = content[start:chunk_end]
                end = chunk_end

            if chunk_text.strip():
                token_count = len(self.tokenizer.encode(chunk_text))

                chunks.append(DocumentChunk(
                    content=chunk_text.strip(),
                    index=chunk_index,
                    start_char=start,
                    end_char=end,
                    metadata={
                        **base_metadata,
                        "chunk_method": "simple_fallback",
                        "total_chunks": -1  # Will update after
                    },
                    token_count=token_count
                ))

                chunk_index += 1

            # Move forward with overlap
            start = end - overlap

        # Update total chunks
        for chunk in chunks:
            chunk.metadata["total_chunks"] = len(chunks)

        logger.info(f"Created {len(chunks)} chunks using simple fallback")
        return chunks


def create_chunker(config: ChunkingConfig):
    """
    Create DoclingHybridChunker for intelligent document splitting.

    Args:
        config: Chunking configuration

    Returns:
        DoclingHybridChunker instance
    """
    return DoclingHybridChunker(config)
