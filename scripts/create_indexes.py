"""
Create MongoDB indexes for enhanced metadata filtering.

This script creates indexes on the documents and chunks collections to enable
fast filtering by metadata fields such as document_type, date, author, keywords, etc.

Run this script after ingesting documents with enhanced metadata extraction.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pymongo import AsyncMongoClient, ASCENDING, DESCENDING
from pymongo.errors import OperationFailure
from dotenv import load_dotenv

from src.settings import load_settings

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


async def create_indexes():
    """Create all recommended indexes for documents and chunks collections."""
    settings = load_settings()

    # Initialize MongoDB client
    client = AsyncMongoClient(
        settings.mongodb_uri,
        serverSelectionTimeoutMS=5000
    )
    db = client[settings.mongodb_database]

    try:
        # Verify connection
        await client.admin.command("ping")
        logger.info(f"Connected to MongoDB database: {settings.mongodb_database}")

        documents_collection = db[settings.mongodb_collection_documents]
        chunks_collection = db[settings.mongodb_collection_chunks]

        # ============================================================
        # Documents Collection Indexes
        # ============================================================
        logger.info("Creating indexes on documents collection...")

        indexes_created = []
        indexes_skipped = []

        # Single field indexes
        index_specs_documents = [
            ("metadata.document_type", ASCENDING, "document_type"),
            ("metadata.document_date", ASCENDING, "document_date"),
            ("metadata.author", ASCENDING, "author"),
            ("metadata.id_informacji", ASCENDING, "id_informacji"),
            ("metadata.sygnatura", ASCENDING, "sygnatura"),
            ("metadata.slowa_kluczowe", ASCENDING, "slowa_kluczowe"),  # Array index
        ]

        for field, direction, name in index_specs_documents:
            try:
                await documents_collection.create_index(
                    [(field, direction)],
                    name=f"idx_{name}",
                    background=True
                )
                indexes_created.append(f"documents.{name}")
                logger.info(f"  ✓ Created index: documents.{name} on {field}")
            except OperationFailure as e:
                if "already exists" in str(e).lower() or "duplicate key" in str(e).lower():
                    indexes_skipped.append(f"documents.{name} (already exists)")
                    logger.info(f"  - Skipped index: documents.{name} (already exists)")
                else:
                    logger.error(f"  ✗ Failed to create index documents.{name}: {e}")

        # Composite indexes
        composite_indexes_documents = [
            (
                [("metadata.document_type", ASCENDING), ("metadata.document_date", DESCENDING)],
                "document_type_date"
            ),
        ]

        for index_spec, name in composite_indexes_documents:
            try:
                await documents_collection.create_index(
                    index_spec,
                    name=f"idx_{name}",
                    background=True
                )
                indexes_created.append(f"documents.{name}")
                logger.info(f"  ✓ Created composite index: documents.{name}")
            except OperationFailure as e:
                if "already exists" in str(e).lower() or "duplicate key" in str(e).lower():
                    indexes_skipped.append(f"documents.{name} (already exists)")
                    logger.info(f"  - Skipped index: documents.{name} (already exists)")
                else:
                    logger.error(f"  ✗ Failed to create composite index documents.{name}: {e}")

        # ============================================================
        # Chunks Collection Indexes
        # ============================================================
        logger.info("\nCreating indexes on chunks collection...")

        index_specs_chunks = [
            ("metadata.section_type", ASCENDING, "section_type"),
            ("metadata.document_type", ASCENDING, "document_type"),
            ("metadata.document_date", ASCENDING, "document_date"),
            ("metadata.id_informacji", ASCENDING, "id_informacji"),
            ("metadata.slowa_kluczowe", ASCENDING, "slowa_kluczowe"),  # Array index
        ]

        for field, direction, name in index_specs_chunks:
            try:
                await chunks_collection.create_index(
                    [(field, direction)],
                    name=f"idx_{name}",
                    background=True
                )
                indexes_created.append(f"chunks.{name}")
                logger.info(f"  ✓ Created index: chunks.{name} on {field}")
            except OperationFailure as e:
                if "already exists" in str(e).lower() or "duplicate key" in str(e).lower():
                    indexes_skipped.append(f"chunks.{name} (already exists)")
                    logger.info(f"  - Skipped index: chunks.{name} (already exists)")
                else:
                    logger.error(f"  ✗ Failed to create index chunks.{name}: {e}")

        # Composite indexes for chunks
        composite_indexes_chunks = [
            (
                [("metadata.section_type", ASCENDING), ("metadata.document_type", ASCENDING)],
                "section_type_document_type"
            ),
        ]

        for index_spec, name in composite_indexes_chunks:
            try:
                await chunks_collection.create_index(
                    index_spec,
                    name=f"idx_{name}",
                    background=True
                )
                indexes_created.append(f"chunks.{name}")
                logger.info(f"  ✓ Created composite index: chunks.{name}")
            except OperationFailure as e:
                if "already exists" in str(e).lower() or "duplicate key" in str(e).lower():
                    indexes_skipped.append(f"chunks.{name} (already exists)")
                    logger.info(f"  - Skipped index: chunks.{name} (already exists)")
                else:
                    logger.error(f"  ✗ Failed to create composite index chunks.{name}: {e}")

        # ============================================================
        # Summary
        # ============================================================
        logger.info("\n" + "="*60)
        logger.info("INDEX CREATION SUMMARY")
        logger.info("="*60)
        logger.info(f"Indexes created: {len(indexes_created)}")
        logger.info(f"Indexes skipped (already exist): {len(indexes_skipped)}")
        logger.info("\nCreated indexes:")
        for idx in indexes_created:
            logger.info(f"  - {idx}")
        if indexes_skipped:
            logger.info("\nSkipped indexes:")
            for idx in indexes_skipped:
                logger.info(f"  - {idx}")

    except Exception as e:
        logger.exception(f"Failed to create indexes: {e}")
        raise
    finally:
        await client.close()
        logger.info("\nMongoDB connection closed")


async def main():
    """Main function."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    try:
        await create_indexes()
    except KeyboardInterrupt:
        logger.info("\nIndex creation interrupted by user")
    except Exception as e:
        logger.exception(f"Index creation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

