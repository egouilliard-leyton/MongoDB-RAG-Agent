"""
Main ingestion script for processing documents into MongoDB vector database.

This adapts the examples/ingestion/ingest.py pipeline to use MongoDB instead of PostgreSQL,
changing only the database layer while preserving all document processing logic.
"""

import os
import asyncio
import logging
import glob
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, Awaitable, Protocol, runtime_checkable
from datetime import datetime
import argparse
from dataclasses import dataclass

from pymongo import AsyncMongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from bson import ObjectId
from dotenv import load_dotenv

from src.ingestion.chunker import ChunkingConfig, create_chunker, DocumentChunk
from src.ingestion.embedder import create_embedder
from src.ingestion.metadata_extractor import (
    extract_tax_interpretation_metadata,
    extract_structured_metadata,
    extract_title_enhanced,
    extract_outcome_status,
    extract_interpretation_stance,
)
from src.ingestion.section_identifier import get_section_count
from src.settings import load_settings
from src.services.ingestion_tracker import (
    IngestionStage,
    IngestionStatistics,
    IngestionProgress,
    IngestionResult as TrackerIngestionResult,
)
from src.services.industry_classifier import get_industry_classifier, IndustryClassifier

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


# =============================================================================
# Progress Callback Protocol
# =============================================================================


@runtime_checkable
class ProgressCallback(Protocol):
    """Protocol for progress callbacks during ingestion."""

    async def __call__(
        self,
        stage: IngestionStage,
        progress_pct: int,
        message: str
    ) -> None:
        """
        Called when ingestion progress updates.

        Args:
            stage: Current ingestion stage
            progress_pct: Progress percentage (0-100)
            message: Human-readable status message
        """
        ...


# Type alias for progress callback
ProgressCallbackType = Callable[[IngestionStage, int, str], Awaitable[None]]


@dataclass
class IngestionConfig:
    """Configuration for document ingestion."""
    chunk_size: int = 1000
    chunk_overlap: int = 200
    max_chunk_size: int = 2000
    max_tokens: int = 512
    skip_classification: bool = False  # Skip Gemini industry classification


@dataclass
class IngestionResult:
    """Result of document ingestion (legacy dataclass for CLI compatibility)."""
    document_id: str
    title: str
    chunks_created: int
    processing_time_ms: float
    errors: List[str]


@dataclass
class DetailedIngestionResult:
    """
    Detailed ingestion result with full statistics and metadata.

    Used by the API for comprehensive ingestion tracking.
    """
    document_id: Optional[str]
    title: str
    status: str  # "success", "partial", "failed"
    statistics: IngestionStatistics
    metadata_extracted: Dict[str, Any]
    warnings: List[str]
    errors: List[str]

    def to_tracker_result(self) -> TrackerIngestionResult:
        """Convert to IngestionTracker's result model."""
        return TrackerIngestionResult(
            document_id=self.document_id,
            status=self.status,
            statistics=self.statistics,
            metadata_extracted=self.metadata_extracted,
            warnings=self.warnings,
            errors=self.errors,
        )


class DocumentIngestionPipeline:
    """Pipeline for ingesting documents into MongoDB vector database."""

    def __init__(
        self,
        config: IngestionConfig,
        documents_folder: str = "documents",
        clean_before_ingest: bool = True,
        dry_run: bool = False
    ):
        """
        Initialize ingestion pipeline.

        Args:
            config: Ingestion configuration
            documents_folder: Folder containing documents
            clean_before_ingest: Whether to clean existing data before ingestion
            dry_run: If True, process documents but don't save to MongoDB
        """
        self.config = config
        self.documents_folder = documents_folder
        self.clean_before_ingest = clean_before_ingest
        self.dry_run = dry_run

        # Load settings
        self.settings = load_settings()

        # Initialize MongoDB client and database references
        self.mongo_client: Optional[AsyncMongoClient] = None
        self.db: Optional[Any] = None

        # Initialize components
        self.chunker_config = ChunkingConfig(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            max_chunk_size=config.max_chunk_size,
            max_tokens=config.max_tokens
        )

        self.chunker = create_chunker(self.chunker_config)
        self.embedder = create_embedder()

        # Initialize industry classifier (lazy - will be configured when needed)
        self.skip_classification = config.skip_classification
        self._industry_classifier: Optional[IndustryClassifier] = None

        self._initialized = False

    async def ingest_file(
        self,
        file_path: str,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> IngestionResult:
        """
        Ingest a single file without scanning the full documents folder.

        This is primarily used by the Projects uploads API.
        """
        if not self._initialized:
            await self.initialize()
        return await self._ingest_single_document(file_path, extra_metadata=extra_metadata)

    async def ingest_file_with_tracking(
        self,
        file_path: str,
        extra_metadata: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[ProgressCallbackType] = None,
    ) -> DetailedIngestionResult:
        """
        Ingest a single file with detailed progress tracking.

        This method emits progress updates at each stage and returns
        comprehensive statistics for the ingestion dashboard.

        Args:
            file_path: Path to the file to ingest
            extra_metadata: Optional additional metadata to attach
            progress_callback: Optional async callback for progress updates

        Returns:
            DetailedIngestionResult with full statistics and metadata
        """
        if not self._initialized:
            await self.initialize()
        return await self._ingest_single_document_with_tracking(
            file_path,
            extra_metadata=extra_metadata,
            progress_callback=progress_callback,
        )

    async def initialize(self) -> None:
        """
        Initialize MongoDB connections.

        Raises:
            ConnectionFailure: If MongoDB connection fails
            ServerSelectionTimeoutError: If MongoDB server selection times out
        """
        if self._initialized:
            return

        logger.info("Initializing ingestion pipeline...")

        # Skip MongoDB connection in dry-run mode
        if self.dry_run:
            logger.info("[DRY-RUN] Skipping MongoDB connection")
            self._initialized = True
            return

        try:
            # Initialize MongoDB client
            self.mongo_client = AsyncMongoClient(
                self.settings.mongodb_uri,
                serverSelectionTimeoutMS=5000
            )
            self.db = self.mongo_client[self.settings.mongodb_database]

            # Verify connection
            await self.mongo_client.admin.command("ping")
            logger.info(
                f"Connected to MongoDB database: {self.settings.mongodb_database}"
            )

        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.exception("mongodb_connection_failed", error=str(e))
            raise

        self._initialized = True
        logger.info("Ingestion pipeline initialized")

    async def close(self) -> None:
        """Close MongoDB connections."""
        if self._initialized and self.mongo_client:
            await self.mongo_client.close()
            self.mongo_client = None
            self.db = None
            self._initialized = False
            logger.info("MongoDB connection closed")

    def _find_document_files(self) -> List[str]:
        """
        Find all supported document files in the documents folder.

        Returns:
            List of file paths
        """
        if not os.path.exists(self.documents_folder):
            logger.error(f"Documents folder not found: {self.documents_folder}")
            return []

        # Supported file patterns - Docling + text formats + audio
        patterns = [
            "*.md", "*.markdown", "*.txt",  # Text formats
            "*.pdf",  # PDF
            "*.docx", "*.doc",  # Word
            "*.pptx", "*.ppt",  # PowerPoint
            "*.xlsx", "*.xls",  # Excel
            "*.html", "*.htm",  # HTML
            "*.mp3", "*.wav", "*.m4a", "*.flac",  # Audio formats
        ]
        files = []

        for pattern in patterns:
            files.extend(
                glob.glob(
                    os.path.join(self.documents_folder, "**", pattern),
                    recursive=True
                )
            )

        return sorted(files)

    def _read_document(self, file_path: str) -> tuple[str, Optional[Any]]:
        """
        Read document content from file - supports multiple formats via Docling.

        Args:
            file_path: Path to the document file

        Returns:
            Tuple of (markdown_content, docling_document).
            docling_document is None only for text files.
        """
        file_ext = os.path.splitext(file_path)[1].lower()

        # Audio formats - transcribe with Whisper ASR
        audio_formats = ['.mp3', '.wav', '.m4a', '.flac']
        if file_ext in audio_formats:
            # Returns tuple: (markdown_content, docling_document)
            return self._transcribe_audio(file_path)

        # Docling-supported formats (convert to markdown)
        docling_formats = [
            '.pdf', '.docx', '.doc', '.pptx', '.ppt',
            '.xlsx', '.xls', '.html', '.htm',
            '.md', '.markdown'  # Markdown files for HybridChunker
        ]

        if file_ext in docling_formats:
            try:
                from docling.document_converter import DocumentConverter

                logger.info(
                    f"Converting {file_ext} file using Docling: "
                    f"{os.path.basename(file_path)}"
                )

                converter = DocumentConverter()
                result = converter.convert(file_path)

                # Export to markdown for consistent processing
                markdown_content = result.document.export_to_markdown()
                logger.info(
                    f"Successfully converted {os.path.basename(file_path)} "
                    f"to markdown"
                )

                # Return both markdown and DoclingDocument for HybridChunker
                return (markdown_content, result.document)

            except Exception as e:
                logger.error(f"Failed to convert {file_path} with Docling: {e}")
                # Fall back to raw text if Docling fails
                logger.warning(f"Falling back to raw text extraction for {file_path}")
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        return (f.read(), None)
                except Exception:
                    return (
                        f"[Error: Could not read file {os.path.basename(file_path)}]",
                        None
                    )

        # Text-based formats (read directly)
        else:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return (f.read(), None)
            except UnicodeDecodeError:
                # Try with different encoding
                with open(file_path, 'r', encoding='latin-1') as f:
                    return (f.read(), None)

    def _transcribe_audio(self, file_path: str) -> tuple[str, Optional[Any]]:
        """
        Transcribe audio file using Whisper ASR via Docling.

        Args:
            file_path: Path to the audio file

        Returns:
            Tuple of (markdown_content, docling_document)
        """
        try:
            from pathlib import Path
            from docling.document_converter import (
                DocumentConverter,
                AudioFormatOption
            )
            from docling.datamodel.pipeline_options import AsrPipelineOptions
            from docling.datamodel import asr_model_specs
            from docling.datamodel.base_models import InputFormat
            from docling.pipeline.asr_pipeline import AsrPipeline

            # Use Path object - Docling expects this
            audio_path = Path(file_path).resolve()
            logger.info(
                f"Transcribing audio file using Whisper Turbo: {audio_path.name}"
            )

            # Verify file exists
            if not audio_path.exists():
                raise FileNotFoundError(f"Audio file not found: {audio_path}")

            # Configure ASR pipeline with Whisper Turbo model
            pipeline_options = AsrPipelineOptions()
            pipeline_options.asr_options = asr_model_specs.WHISPER_TURBO

            converter = DocumentConverter(
                format_options={
                    InputFormat.AUDIO: AudioFormatOption(
                        pipeline_cls=AsrPipeline,
                        pipeline_options=pipeline_options,
                    )
                }
            )

            # Transcribe the audio file
            result = converter.convert(audio_path)

            # Export to markdown with timestamps
            markdown_content = result.document.export_to_markdown()
            logger.info(f"Successfully transcribed {os.path.basename(file_path)}")

            # Return both markdown and DoclingDocument for HybridChunker
            return (markdown_content, result.document)

        except Exception as e:
            logger.error(f"Failed to transcribe {file_path} with Whisper ASR: {e}")
            return (
                f"[Error: Could not transcribe audio file "
                f"{os.path.basename(file_path)}]",
                None
            )

    def _extract_title(self, content: str, file_path: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Extract title from document content or filename using enhanced extraction.

        Uses multiple strategies:
        1. From metadata['tytul_teza'] (best - the actual question/title)
        2. Parse header section directly
        3. Use document number + type from filename
        4. First H2 heading
        5. Fallback to filename

        Args:
            content: Document content
            file_path: Path to the document file
            metadata: Optional pre-extracted metadata dictionary

        Returns:
            Document title
        """
        return extract_title_enhanced(content, file_path, metadata)

    def _extract_document_metadata(
        self,
        content: str,
        file_path: str
    ) -> Dict[str, Any]:
        """
        Extract metadata from document content.

        Extracts structured metadata from:
        1. Document header (for tax interpretation documents)
        2. Filename pattern
        3. Basic file metadata

        Args:
            content: Document content
            file_path: Path to the document file

        Returns:
            Document metadata dictionary
        """
        # Base metadata
        metadata = {
            "file_path": file_path,
            "file_size": len(content),
            "ingestion_date": datetime.now().isoformat()
        }

        # Extract structured metadata from tax interpretation header
        try:
            tax_metadata = extract_tax_interpretation_metadata(content, file_path)
            if tax_metadata:
                metadata.update(tax_metadata)
                logger.debug(f"Extracted tax interpretation metadata: {list(tax_metadata.keys())}")
        except Exception as e:
            logger.warning(f"Failed to extract tax interpretation metadata: {e}")

        # Extract metadata from filename
        try:
            filename_metadata = extract_structured_metadata(file_path)
            if filename_metadata:
                metadata.update(filename_metadata)
                logger.debug(f"Extracted filename metadata: {list(filename_metadata.keys())}")
        except Exception as e:
            logger.warning(f"Failed to extract filename metadata: {e}")

        # Try to extract YAML frontmatter (for backward compatibility)
        if content.startswith('---'):
            try:
                import yaml
                end_marker = content.find('\n---\n', 4)
                if end_marker != -1:
                    frontmatter = content[4:end_marker]
                    yaml_metadata = yaml.safe_load(frontmatter)
                    if isinstance(yaml_metadata, dict):
                        metadata.update(yaml_metadata)
            except ImportError:
                logger.warning(
                    "PyYAML not installed, skipping frontmatter extraction"
                )
            except Exception as e:
                logger.warning(f"Failed to parse frontmatter: {e}")

        # Extract some basic metadata from content
        lines = content.split('\n')
        metadata['line_count'] = len(lines)
        metadata['word_count'] = len(content.split())

        # Add section count (number of H2 headings/sections)
        try:
            section_count = get_section_count(content)
            metadata['section_count'] = section_count
        except Exception as e:
            logger.warning(f"Failed to count sections: {e}")

        # Extract outcome status (successful/unsuccessful)
        try:
            outcome_data = extract_outcome_status(content)
            if outcome_data.get("outcome_status"):
                metadata['outcome_status'] = outcome_data['outcome_status']
            if outcome_data.get("outcome_paragraphs"):
                metadata['outcome_paragraphs'] = outcome_data['outcome_paragraphs']
            logger.debug(f"Extracted outcome status: {outcome_data.get('outcome_status')}")
        except Exception as e:
            logger.warning(f"Failed to extract outcome status: {e}")

        # Extract interpretation stance (positive/partial/negative)
        try:
            stance_data = extract_interpretation_stance(content)
            if stance_data.get("stance"):
                metadata["interpretation_stance"] = stance_data["stance"]
            if stance_data.get("evidence"):
                metadata["interpretation_stance_evidence"] = stance_data["evidence"][:5]
            logger.debug(
                "Extracted interpretation stance: "
                f"{stance_data.get('stance')}"
            )
        except Exception as e:
            logger.warning(f"Failed to extract interpretation stance: {e}")

        return metadata

    async def _classify_document_industry(
        self,
        file_path: str,
        document_content: str,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Classify document industry using Gemini API with retry logic.

        Handles rate limiting with exponential backoff.

        Args:
            file_path: Path to the original document file
            document_content: Extracted document content (used if file upload fails)
            max_retries: Maximum number of retry attempts
            base_delay: Base delay in seconds for exponential backoff

        Returns:
            Tuple of (industry_code, industry_name_polish) if successful,
            (None, None) otherwise
        """
        if self.skip_classification:
            logger.info("Industry classification skipped (--skip-classification flag)")
            return None, None

        # Lazy-initialize the classifier
        if self._industry_classifier is None:
            self._industry_classifier = get_industry_classifier()

        if not self._industry_classifier.is_available:
            logger.warning(
                "Industry classification unavailable: GEMINI_API_KEY not configured"
            )
            return None, None

        last_exception: Optional[Exception] = None

        for attempt in range(max_retries):
            try:
                logger.info(
                    f"Classifying industry (attempt {attempt + 1}/{max_retries}): "
                    f"{os.path.basename(file_path)}"
                )

                # Try to classify from file first (better for PDFs, etc.)
                # If file path doesn't exist or fails, fall back to content
                if os.path.exists(file_path):
                    industry_code, industry_name = (
                        await self._industry_classifier.classify_from_file(file_path)
                    )
                else:
                    # Fall back to content-based classification
                    industry_code, industry_name = (
                        await self._industry_classifier.classify_from_content(
                            document_content,
                            display_name=os.path.basename(file_path),
                        )
                    )

                if industry_code:
                    logger.info(
                        f"Industry classified successfully: {industry_code} - {industry_name}"
                    )
                else:
                    logger.info("Industry could not be determined from document")

                return industry_code, industry_name

            except Exception as e:
                last_exception = e
                error_str = str(e).lower()

                # Check for rate limiting errors
                is_rate_limit = (
                    "rate" in error_str
                    or "quota" in error_str
                    or "429" in error_str
                    or "resource_exhausted" in error_str
                )

                if is_rate_limit and attempt < max_retries - 1:
                    # Exponential backoff for rate limits
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        f"Gemini API rate limit hit, retrying in {delay:.1f}s "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(delay)
                elif attempt < max_retries - 1:
                    # Shorter delay for other transient errors
                    delay = base_delay
                    logger.warning(
                        f"Industry classification failed, retrying in {delay:.1f}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.exception(
                        f"Industry classification failed after {max_retries} attempts: {e}"
                    )

        # All retries exhausted
        logger.warning(
            f"Industry classification failed for {os.path.basename(file_path)}: "
            f"{last_exception}"
        )
        return None, None

    async def _save_to_mongodb(
        self,
        title: str,
        source: str,
        content: str,
        chunks: List[DocumentChunk],
        metadata: Dict[str, Any]
    ) -> str:
        """
        Save document and chunks to MongoDB.

        Args:
            title: Document title
            source: Document source path
            content: Document content
            chunks: List of document chunks with embeddings
            metadata: Document metadata

        Returns:
            Document ID (ObjectId as string) or "dry-run-<timestamp>" in dry-run mode

        Raises:
            Exception: If MongoDB operations fail
        """
        # Dry-run mode: don't save to MongoDB
        if self.dry_run:
            fake_id = f"dry-run-{datetime.now().timestamp()}"
            logger.info(f"[DRY-RUN] Would insert document: {title}")
            logger.info(f"[DRY-RUN] Would insert {len(chunks)} chunks")
            return fake_id
        
        # Get collection references
        documents_collection = self.db[
            self.settings.mongodb_collection_documents
        ]
        chunks_collection = self.db[self.settings.mongodb_collection_chunks]

        # Insert document with enhanced metadata structure
        document_dict = {
            "title": title,
            "source": source,
            "content": content,
            "metadata": metadata,  # Already contains structured metadata from extractors
            "created_at": datetime.now()
        }

        document_result = await documents_collection.insert_one(document_dict)
        document_id = document_result.inserted_id

        logger.info(f"Inserted document with ID: {document_id}")

        # Prepare denormalized document metadata for chunks (for filtering)
        # Extract key fields that should be denormalized into chunks
        denormalized_doc_metadata = {}
        if "project_id" in metadata and metadata["project_id"] is not None:
            denormalized_doc_metadata["project_id"] = metadata["project_id"]
        if "document_type" in metadata:
            denormalized_doc_metadata["document_type"] = metadata["document_type"]
        if "document_date" in metadata:
            denormalized_doc_metadata["document_date"] = metadata["document_date"]
        if "id_informacji" in metadata:
            denormalized_doc_metadata["id_informacji"] = metadata["id_informacji"]
        if "sygnatura" in metadata:
            denormalized_doc_metadata["sygnatura"] = metadata["sygnatura"]
        if "interpretation_stance" in metadata:
            denormalized_doc_metadata["interpretation_stance"] = metadata["interpretation_stance"]
        if "slowa_kluczowe" in metadata:
            denormalized_doc_metadata["slowa_kluczowe"] = metadata["slowa_kluczowe"]
        if "author" in metadata:
            denormalized_doc_metadata["author"] = metadata["author"]
        # Industry classification (for filtering)
        if "industry_code" in metadata:
            denormalized_doc_metadata["industry_code"] = metadata["industry_code"]
        if "industry_name" in metadata:
            denormalized_doc_metadata["industry_name"] = metadata["industry_name"]

        # Insert chunks with embeddings and enhanced metadata
        chunk_dicts = []
        for chunk in chunks:
            # Merge chunk metadata with denormalized document metadata
            enhanced_chunk_metadata = {
                **chunk.metadata,
                **denormalized_doc_metadata  # Denormalize for filtering
            }

            chunk_dict = {
                "document_id": document_id,
                "content": chunk.content,
                "embedding": chunk.embedding,  # Python list, NOT string!
                "chunk_index": chunk.index,
                "metadata": enhanced_chunk_metadata,  # Enhanced with denormalized doc metadata
                "token_count": chunk.token_count,
                "created_at": datetime.now()
            }
            chunk_dicts.append(chunk_dict)

        # Batch insert with ordered=False for partial success
        if chunk_dicts and not self.dry_run:
            await chunks_collection.insert_many(chunk_dicts, ordered=False)
            logger.info(f"Inserted {len(chunk_dicts)} chunks")

        return str(document_id)

    async def _clean_databases(self) -> None:
        """Clean existing data from MongoDB collections."""
        logger.warning("Cleaning existing data from MongoDB...")

        # Get collection references
        documents_collection = self.db[
            self.settings.mongodb_collection_documents
        ]
        chunks_collection = self.db[self.settings.mongodb_collection_chunks]

        # Delete all chunks first (to respect FK relationships)
        chunks_result = await chunks_collection.delete_many({})
        logger.info(f"Deleted {chunks_result.deleted_count} chunks")

        # Delete all documents
        docs_result = await documents_collection.delete_many({})
        logger.info(f"Deleted {docs_result.deleted_count} documents")

    async def _ingest_single_document(
        self,
        file_path: str,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> IngestionResult:
        """
        Ingest a single document.

        Args:
            file_path: Path to the document file

        Returns:
            Ingestion result
        """
        start_time = datetime.now()

        # Read document (returns tuple: content, docling_doc)
        document_content, docling_doc = self._read_document(file_path)
        document_source = os.path.relpath(file_path, self.documents_folder)

        # Extract metadata from content (includes tax interpretation metadata)
        document_metadata = self._extract_document_metadata(
            document_content,
            file_path
        )

        # Merge extra metadata (e.g., project scoping)
        if extra_metadata:
            document_metadata.update(extra_metadata)

        # Classify document industry using Gemini (if not skipped)
        industry_code, industry_name = await self._classify_document_industry(
            file_path, document_content
        )
        if industry_code:
            document_metadata["industry_code"] = industry_code
            document_metadata["industry_name"] = industry_name
            logger.info(f"Industry classified: {industry_code} - {industry_name}")

        # Extract title using enhanced extraction (can use metadata)
        document_title = self._extract_title(
            document_content,
            file_path,
            metadata=document_metadata
        )

        logger.info(f"Processing document: {document_title}")

        # Chunk the document - pass DoclingDocument for HybridChunker
        chunks = await self.chunker.chunk_document(
            content=document_content,
            title=document_title,
            source=document_source,
            metadata=document_metadata,
            docling_doc=docling_doc  # Pass DoclingDocument for HybridChunker
        )

        if not chunks:
            logger.warning(f"No chunks created for {document_title}")
            return IngestionResult(
                document_id="",
                title=document_title,
                chunks_created=0,
                processing_time_ms=(
                    datetime.now() - start_time
                ).total_seconds() * 1000,
                errors=["No chunks created"]
            )

        logger.info(f"Created {len(chunks)} chunks")

        # Generate embeddings
        embedded_chunks = await self.embedder.embed_chunks(chunks)
        logger.info(f"Generated embeddings for {len(embedded_chunks)} chunks")

        # Save to MongoDB
        document_id = await self._save_to_mongodb(
            document_title,
            document_source,
            document_content,
            embedded_chunks,
            document_metadata
        )

        logger.info(f"Saved document to MongoDB with ID: {document_id}")

        # Calculate processing time
        processing_time = (
            datetime.now() - start_time
        ).total_seconds() * 1000

        return IngestionResult(
            document_id=document_id,
            title=document_title,
            chunks_created=len(chunks),
            processing_time_ms=processing_time,
            errors=[]
        )

    async def _ingest_single_document_with_tracking(
        self,
        file_path: str,
        extra_metadata: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[ProgressCallbackType] = None,
    ) -> DetailedIngestionResult:
        """
        Ingest a single document with detailed progress tracking.

        Args:
            file_path: Path to the document file
            extra_metadata: Optional additional metadata
            progress_callback: Optional async callback for progress updates

        Returns:
            DetailedIngestionResult with comprehensive statistics
        """
        start_time = datetime.now()
        warnings: List[str] = []
        errors: List[str] = []

        # Helper to emit progress
        async def emit_progress(stage: IngestionStage, pct: int, msg: str) -> None:
            if progress_callback:
                try:
                    await progress_callback(stage, pct, msg)
                except Exception as e:
                    logger.warning(f"Progress callback failed: {e}")

        # Get file size
        try:
            file_size_bytes = os.path.getsize(file_path)
        except OSError:
            file_size_bytes = 0

        # Stage 1: Converting document
        await emit_progress(IngestionStage.CONVERTING, 10, "Converting document to markdown...")

        try:
            document_content, docling_doc = self._read_document(file_path)
            document_source = os.path.relpath(file_path, self.documents_folder)
        except Exception as e:
            logger.exception(f"Failed to convert document: {file_path}")
            errors.append(f"Document conversion failed: {str(e)}")
            return DetailedIngestionResult(
                document_id=None,
                title=os.path.basename(file_path),
                status="failed",
                statistics=IngestionStatistics(file_size_bytes=file_size_bytes),
                metadata_extracted={},
                warnings=warnings,
                errors=errors,
            )

        await emit_progress(IngestionStage.CONVERTING, 20, "Document converted successfully")

        # Stage 2: Extracting metadata
        await emit_progress(IngestionStage.EXTRACTING_METADATA, 25, "Extracting document metadata...")

        try:
            document_metadata = self._extract_document_metadata(document_content, file_path)

            # Merge extra metadata
            if extra_metadata:
                document_metadata.update(extra_metadata)

            # Extract title
            document_title = self._extract_title(
                document_content, file_path, metadata=document_metadata
            )
        except Exception as e:
            logger.warning(f"Metadata extraction partially failed: {e}")
            warnings.append(f"Metadata extraction warning: {str(e)}")
            document_metadata = extra_metadata or {}
            document_title = os.path.basename(file_path)

        await emit_progress(IngestionStage.EXTRACTING_METADATA, 30, f"Metadata extracted for: {document_title}")

        # Stage 2b: Industry classification (optional - uses Gemini API)
        if not self.skip_classification:
            await emit_progress(IngestionStage.EXTRACTING_METADATA, 32, "Classifying document industry...")
            try:
                industry_code, industry_name = await self._classify_document_industry(
                    file_path, document_content
                )
                if industry_code:
                    document_metadata["industry_code"] = industry_code
                    document_metadata["industry_name"] = industry_name
                    logger.info(f"Industry classified: {industry_code} - {industry_name}")
                    await emit_progress(
                        IngestionStage.EXTRACTING_METADATA, 35,
                        f"Industry: {industry_name}"
                    )
                else:
                    await emit_progress(
                        IngestionStage.EXTRACTING_METADATA, 35,
                        "Industry could not be determined"
                    )
            except Exception as e:
                # Industry classification is optional - don't fail the whole ingestion
                warnings.append(f"Industry classification failed: {str(e)}")
                logger.warning(f"Industry classification failed (continuing): {e}")
                await emit_progress(
                    IngestionStage.EXTRACTING_METADATA, 35,
                    "Industry classification skipped due to error"
                )
        else:
            await emit_progress(IngestionStage.EXTRACTING_METADATA, 35, "Industry classification skipped")

        logger.info(f"Processing document with tracking: {document_title}")

        # Stage 3: Chunking document
        await emit_progress(IngestionStage.CHUNKING, 40, "Chunking document...")

        try:
            chunks = await self.chunker.chunk_document(
                content=document_content,
                title=document_title,
                source=document_source,
                metadata=document_metadata,
                docling_doc=docling_doc,
            )
        except Exception as e:
            logger.exception(f"Failed to chunk document: {document_title}")
            errors.append(f"Chunking failed: {str(e)}")
            return DetailedIngestionResult(
                document_id=None,
                title=document_title,
                status="failed",
                statistics=IngestionStatistics(file_size_bytes=file_size_bytes),
                metadata_extracted=document_metadata,
                warnings=warnings,
                errors=errors,
            )

        if not chunks:
            warnings.append("No chunks created from document")
            return DetailedIngestionResult(
                document_id=None,
                title=document_title,
                status="partial",
                statistics=IngestionStatistics(
                    chunks_created=0,
                    file_size_bytes=file_size_bytes,
                ),
                metadata_extracted=document_metadata,
                warnings=warnings,
                errors=errors,
            )

        await emit_progress(IngestionStage.CHUNKING, 50, f"Created {len(chunks)} chunks")

        # Stage 4: Generating embeddings
        await emit_progress(IngestionStage.EMBEDDING, 55, "Generating embeddings...")

        try:
            embedded_chunks = await self.embedder.embed_chunks(chunks)
        except Exception as e:
            logger.exception(f"Failed to generate embeddings: {document_title}")
            errors.append(f"Embedding generation failed: {str(e)}")
            return DetailedIngestionResult(
                document_id=None,
                title=document_title,
                status="failed",
                statistics=IngestionStatistics(
                    chunks_created=len(chunks),
                    file_size_bytes=file_size_bytes,
                ),
                metadata_extracted=document_metadata,
                warnings=warnings,
                errors=errors,
            )

        await emit_progress(IngestionStage.EMBEDDING, 75, f"Generated embeddings for {len(embedded_chunks)} chunks")

        # Calculate statistics
        total_tokens = sum(chunk.token_count for chunk in embedded_chunks)
        avg_chunk_tokens = total_tokens / len(embedded_chunks) if embedded_chunks else 0.0
        sections_found = document_metadata.get("section_count", 0)

        # Stage 5: Storing in database
        await emit_progress(IngestionStage.STORING, 80, "Storing document in database...")

        try:
            document_id = await self._save_to_mongodb(
                document_title,
                document_source,
                document_content,
                embedded_chunks,
                document_metadata,
            )
        except Exception as e:
            logger.exception(f"Failed to store document: {document_title}")
            errors.append(f"Storage failed: {str(e)}")
            return DetailedIngestionResult(
                document_id=None,
                title=document_title,
                status="failed",
                statistics=IngestionStatistics(
                    chunks_created=len(embedded_chunks),
                    total_tokens=total_tokens,
                    avg_chunk_tokens=avg_chunk_tokens,
                    sections_found=sections_found,
                    file_size_bytes=file_size_bytes,
                ),
                metadata_extracted=document_metadata,
                warnings=warnings,
                errors=errors,
            )

        await emit_progress(IngestionStage.STORING, 90, f"Document stored with ID: {document_id}")

        # Stage 6: Verification (optional - just confirm storage)
        await emit_progress(IngestionStage.VERIFYING, 95, "Verifying document storage...")

        # Calculate final processing time
        processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000

        # Build final statistics
        statistics = IngestionStatistics(
            chunks_created=len(embedded_chunks),
            total_tokens=total_tokens,
            avg_chunk_tokens=avg_chunk_tokens,
            sections_found=sections_found,
            sections_expected=0,  # Could be enhanced based on document type
            file_size_bytes=file_size_bytes,
            processing_time_ms=processing_time_ms,
        )

        # Determine final status
        status = "success" if not errors else ("partial" if document_id else "failed")

        await emit_progress(IngestionStage.COMPLETE, 100, "Ingestion complete")

        logger.info(
            f"Ingestion complete for {document_title}: "
            f"{len(embedded_chunks)} chunks, {total_tokens} tokens, {processing_time_ms:.0f}ms"
        )

        return DetailedIngestionResult(
            document_id=document_id,
            title=document_title,
            status=status,
            statistics=statistics,
            metadata_extracted=document_metadata,
            warnings=warnings,
            errors=errors,
        )

    async def ingest_documents(
        self,
        progress_callback: Optional[callable] = None
    ) -> List[IngestionResult]:
        """
        Ingest all documents from the documents folder.

        Args:
            progress_callback: Optional callback for progress updates

        Returns:
            List of ingestion results
        """
        if not self._initialized:
            await self.initialize()

        # Clean existing data if requested (skip in dry-run)
        if self.clean_before_ingest and not self.dry_run:
            await self._clean_databases()
        elif self.clean_before_ingest and self.dry_run:
            logger.info("[DRY-RUN] Would clean existing data")

        # Find all supported document files
        document_files = self._find_document_files()

        if not document_files:
            logger.warning(
                f"No supported document files found in {self.documents_folder}"
            )
            return []

        logger.info(f"Found {len(document_files)} document files to process")

        results = []

        for i, file_path in enumerate(document_files):
            try:
                logger.info(
                    f"Processing file {i+1}/{len(document_files)}: {file_path}"
                )

                result = await self._ingest_single_document(file_path)
                results.append(result)

                if progress_callback:
                    progress_callback(i + 1, len(document_files))

            except Exception as e:
                logger.exception(f"Failed to process {file_path}: {e}")
                results.append(IngestionResult(
                    document_id="",
                    title=os.path.basename(file_path),
                    chunks_created=0,
                    processing_time_ms=0,
                    errors=[str(e)]
                ))

        # Log summary
        total_chunks = sum(r.chunks_created for r in results)
        total_errors = sum(len(r.errors) for r in results)

        logger.info(
            f"Ingestion complete: {len(results)} documents, "
            f"{total_chunks} chunks, {total_errors} errors"
        )

        return results


async def main() -> None:
    """Main function for running ingestion."""
    parser = argparse.ArgumentParser(
        description="Ingest documents into MongoDB vector database"
    )
    parser.add_argument(
        "--documents", "-d",
        default="documents",
        help="Documents folder path"
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Skip cleaning existing data before ingestion"
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1000,
        help="Chunk size for splitting documents"
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=200,
        help="Chunk overlap size"
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=512,
        help="Maximum tokens per chunk for embeddings"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Process documents but don't save to MongoDB (for testing)"
    )
    parser.add_argument(
        "--skip-classification",
        action="store_true",
        help="Skip automatic industry classification using Gemini API"
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Create ingestion configuration
    config = IngestionConfig(
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        max_chunk_size=args.chunk_size * 2,
        max_tokens=args.max_tokens,
        skip_classification=args.skip_classification
    )

    # Create and run pipeline - clean by default unless --no-clean is specified
    pipeline = DocumentIngestionPipeline(
        config=config,
        documents_folder=args.documents,
        clean_before_ingest=not args.no_clean,  # Clean by default
        dry_run=args.dry_run
    )

    if args.dry_run:
        print("\n[DRY-RUN MODE] Documents will be processed but not saved to MongoDB")

    if args.skip_classification:
        print("[SKIP-CLASSIFICATION] Industry classification will be skipped")

    def progress_callback(current: int, total: int) -> None:
        print(f"Progress: {current}/{total} documents processed")

    try:
        start_time = datetime.now()

        results = await pipeline.ingest_documents(progress_callback)

        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()

        # Print summary
        print("\n" + "="*50)
        print("INGESTION SUMMARY")
        print("="*50)
        print(f"Documents processed: {len(results)}")
        print(f"Total chunks created: {sum(r.chunks_created for r in results)}")
        print(f"Total errors: {sum(len(r.errors) for r in results)}")
        print(f"Total processing time: {total_time:.2f} seconds")
        print()

        # Print individual results
        for result in results:
            status = "[OK]" if not result.errors else "[FAILED]"
            print(f"{status} {result.title}: {result.chunks_created} chunks")

            if result.errors:
                for error in result.errors:
                    print(f"  Error: {error}")

        # Print next steps
        print("\n" + "="*50)
        print("NEXT STEPS")
        print("="*50)
        print("1. Create vector search index in Atlas UI:")
        print("   - Index name: vector_index")
        print("   - Collection: chunks")
        print("   - Field: embedding")
        print("   - Dimensions: 1536 (for text-embedding-3-small)")
        print()
        print("2. Create text search index in Atlas UI:")
        print("   - Index name: text_index")
        print("   - Collection: chunks")
        print("   - Field: content")
        print()
        print("See .claude/reference/mongodb-patterns.md for detailed instructions")

    except KeyboardInterrupt:
        print("\nIngestion interrupted by user")
    except Exception as e:
        logger.exception(f"Ingestion failed: {e}")
        raise
    finally:
        await pipeline.close()


if __name__ == "__main__":
    asyncio.run(main())
