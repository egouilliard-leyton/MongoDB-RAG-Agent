"""
Create MongoDB collections and indexes for Q&A system.

This script creates the qa_sessions and qa_pairs collections with appropriate
indexes for the Q&A system, including vector search indexes for question embeddings.

Run this script to set up the Q&A system database schema.
"""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pymongo import AsyncMongoClient, ASCENDING, DESCENDING
from pymongo.errors import OperationFailure
from dotenv import load_dotenv

from src.settings import load_settings

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


async def create_qa_indexes():
    """Create all Q&A collections and indexes."""
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

        qa_sessions_collection = db[settings.mongodb_collection_qa_sessions]
        qa_pairs_collection = db[settings.mongodb_collection_qa_pairs]

        indexes_created = []
        indexes_skipped = []

        # ============================================================
        # QA Sessions Collection Indexes
        # ============================================================
        logger.info("Creating indexes on qa_sessions collection...")

        # Single field indexes
        index_specs_sessions = [
            ("session_name", ASCENDING, "session_name"),
            ("user_role", ASCENDING, "user_role"),
            ("outcome_status", ASCENDING, "outcome_status"),
            ("metadata.parent_session_id", ASCENDING, "parent_session_id"),
        ]

        for field, direction, name in index_specs_sessions:
            try:
                await qa_sessions_collection.create_index(
                    [(field, direction)],
                    name=f"idx_{name}",
                    background=True
                )
                indexes_created.append(f"qa_sessions.{name}")
                logger.info(f"  ✓ Created index: qa_sessions.{name} on {field}")
            except OperationFailure as e:
                if "already exists" in str(e).lower() or "duplicate key" in str(e).lower():
                    indexes_skipped.append(f"qa_sessions.{name} (already exists)")
                    logger.info(f"  - Skipped index: qa_sessions.{name} (already exists)")
                else:
                    logger.error(f"  ✗ Failed to create index qa_sessions.{name}: {e}")

        # Composite index: session_name + created_at
        try:
            await qa_sessions_collection.create_index(
                [("session_name", ASCENDING), ("created_at", DESCENDING)],
                name="idx_session_name_created_at",
                background=True
            )
            indexes_created.append("qa_sessions.session_name_created_at")
            logger.info("  ✓ Created composite index: qa_sessions.session_name_created_at")
        except OperationFailure as e:
            if "already exists" in str(e).lower() or "duplicate key" in str(e).lower():
                indexes_skipped.append("qa_sessions.session_name_created_at (already exists)")
                logger.info("  - Skipped index: qa_sessions.session_name_created_at (already exists)")
            else:
                logger.error(f"  ✗ Failed to create composite index qa_sessions.session_name_created_at: {e}")

        # ============================================================
        # QA Pairs Collection Indexes
        # ============================================================
        logger.info("\nCreating indexes on qa_pairs collection...")

        # Single field indexes
        index_specs_pairs = [
            ("session_id", ASCENDING, "session_id"),
            ("question_index", ASCENDING, "question_index"),
            ("outcome_status", ASCENDING, "outcome_status"),
        ]

        for field, direction, name in index_specs_pairs:
            try:
                await qa_pairs_collection.create_index(
                    [(field, direction)],
                    name=f"idx_{name}",
                    background=True
                )
                indexes_created.append(f"qa_pairs.{name}")
                logger.info(f"  ✓ Created index: qa_pairs.{name} on {field}")
            except OperationFailure as e:
                if "already exists" in str(e).lower() or "duplicate key" in str(e).lower():
                    indexes_skipped.append(f"qa_pairs.{name} (already exists)")
                    logger.info(f"  - Skipped index: qa_pairs.{name} (already exists)")
                else:
                    logger.error(f"  ✗ Failed to create index qa_pairs.{name}: {e}")

        # Text index on question field
        try:
            await qa_pairs_collection.create_index(
                [("question", "text")],
                name="idx_question_text",
                background=True
            )
            indexes_created.append("qa_pairs.question_text")
            logger.info("  ✓ Created text index: qa_pairs.question_text")
        except OperationFailure as e:
            if "already exists" in str(e).lower() or "duplicate key" in str(e).lower():
                indexes_skipped.append("qa_pairs.question_text (already exists)")
                logger.info("  - Skipped index: qa_pairs.question_text (already exists)")
            else:
                logger.error(f"  ✗ Failed to create text index qa_pairs.question_text: {e}")

        # Composite index: session_id + question_index
        try:
            await qa_pairs_collection.create_index(
                [("session_id", ASCENDING), ("question_index", ASCENDING)],
                name="idx_session_question_index",
                background=True
            )
            indexes_created.append("qa_pairs.session_question_index")
            logger.info("  ✓ Created composite index: qa_pairs.session_question_index")
        except OperationFailure as e:
            if "already exists" in str(e).lower() or "duplicate key" in str(e).lower():
                indexes_skipped.append("qa_pairs.session_question_index (already exists)")
                logger.info("  - Skipped index: qa_pairs.session_question_index (already exists)")
            else:
                logger.error(f"  ✗ Failed to create composite index qa_pairs.session_question_index: {e}")

        # Note: Vector index on question_embedding must be created in Atlas UI
        # The index name should match settings.mongodb_vector_index
        logger.info("\n⚠️  Note: Vector index on qa_pairs.question_embedding must be created in MongoDB Atlas UI")
        logger.info(f"   Index name: {settings.mongodb_vector_index}")
        logger.info("   Path: question_embedding")
        logger.info(f"   Dimension: {settings.embedding_dimension}")

        # ============================================================
        # Summary
        # ============================================================
        logger.info("\n" + "="*60)
        logger.info("Q&A INDEX CREATION SUMMARY")
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
        logger.exception(f"Failed to create Q&A indexes: {e}")
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
        await create_qa_indexes()
    except KeyboardInterrupt:
        logger.info("\nIndex creation interrupted by user")
    except Exception as e:
        logger.exception(f"Q&A index creation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

