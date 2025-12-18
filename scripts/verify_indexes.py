"""
Verify MongoDB indexes for vector search and text search.

This script checks if required indexes exist on chunks and qa_pairs collections
and provides instructions for creating missing indexes.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pymongo import AsyncMongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from dotenv import load_dotenv

from src.settings import load_settings

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


async def verify_indexes():
    """Verify MongoDB indexes."""
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

        chunks_collection = db[settings.mongodb_collection_chunks]
        qa_pairs_collection = db[settings.mongodb_collection_qa_pairs]

        # Get all indexes
        chunks_indexes = []
        async for idx in chunks_collection.list_indexes():
            chunks_indexes.append(idx)
        
        qa_pairs_indexes = []
        async for idx in qa_pairs_collection.list_indexes():
            qa_pairs_indexes.append(idx)

        # Extract index names
        chunks_index_names = [idx["name"] for idx in chunks_indexes]
        qa_pairs_index_names = [idx["name"] for idx in qa_pairs_indexes]

        logger.info("\n" + "="*60)
        logger.info("INDEX VERIFICATION REPORT")
        logger.info("="*60)

        # Check chunks collection indexes
        logger.info("\nChunks Collection Indexes:")
        logger.info(f"  Total indexes: {len(chunks_indexes)}")

        # Check for vector index on chunks.embedding
        vector_index_found = False
        vector_index_name = settings.mongodb_vector_index
        for idx in chunks_indexes:
            if idx.get("type") == "vectorSearch" or vector_index_name in idx.get("name", ""):
                vector_index_found = True
                logger.info(f"  ✅ Vector index found: {idx['name']}")
                logger.info(f"     Type: {idx.get('type', 'unknown')}")
                if "definition" in idx:
                    logger.info(f"     Path: {idx['definition'].get('path', 'unknown')}")
                break

        if not vector_index_found:
            logger.warning(f"  ✗ Vector index '{vector_index_name}' NOT FOUND on chunks.embedding")
            logger.info("     Action required: Create vector index in MongoDB Atlas UI")
            logger.info(f"     Index name: {vector_index_name}")
            logger.info(f"     Path: embedding")
            logger.info(f"     Dimension: {settings.embedding_dimension}")

        # Check for text index on chunks.content
        text_index_found = False
        text_index_name = settings.mongodb_text_index
        for idx in chunks_indexes:
            if idx.get("type") == "text" or text_index_name in idx.get("name", ""):
                text_index_found = True
                logger.info(f"  ✅ Text index found: {idx['name']}")
                break

        if not text_index_found:
            logger.warning(f"  ⚠️  Text index '{text_index_name}' NOT FOUND on chunks.content")
            logger.info("     Note: Text index is optional for hybrid search")

        # List all chunks indexes
        logger.info("\n  All chunks indexes:")
        for idx in chunks_indexes:
            idx_type = idx.get("type", "unknown")
            idx_name = idx.get("name", "unnamed")
            logger.info(f"    - {idx_name} ({idx_type})")

        # Check qa_pairs collection indexes
        logger.info("\nQA Pairs Collection Indexes:")
        logger.info(f"  Total indexes: {len(qa_pairs_indexes)}")

        # Check for vector index on qa_pairs.question_embedding
        qa_vector_index_found = False
        for idx in qa_pairs_indexes:
            if idx.get("type") == "vectorSearch":
                qa_vector_index_found = True
                logger.info(f"  ✅ Vector index found: {idx['name']}")
                logger.info(f"     Type: {idx.get('type', 'unknown')}")
                if "definition" in idx:
                    logger.info(f"     Path: {idx['definition'].get('path', 'unknown')}")
                break

        if not qa_vector_index_found:
            logger.warning("  ✗ Vector index NOT FOUND on qa_pairs.question_embedding")
            logger.info("     Action required: Create vector index in MongoDB Atlas UI")
            logger.info(f"     Index name: {settings.mongodb_vector_index} (or custom name)")
            logger.info("     Path: question_embedding")
            logger.info(f"     Dimension: {settings.embedding_dimension}")
            logger.info("     Note: Required for Q&A history search")

        # List all qa_pairs indexes
        logger.info("\n  All qa_pairs indexes:")
        for idx in qa_pairs_indexes:
            idx_type = idx.get("type", "unknown")
            idx_name = idx.get("name", "unnamed")
            logger.info(f"    - {idx_name} ({idx_type})")

        # Summary and recommendations
        logger.info("\n" + "="*60)
        logger.info("RECOMMENDATIONS")
        logger.info("="*60)

        all_ready = True

        if not vector_index_found:
            all_ready = False
            logger.warning("1. Create vector index on chunks.embedding:")
            logger.info("   - Go to MongoDB Atlas UI")
            logger.info("   - Navigate to Search Indexes")
            logger.info(f"   - Create Vector Search index")
            logger.info(f"   - Name: {vector_index_name}")
            logger.info(f"   - Collection: {settings.mongodb_collection_chunks}")
            logger.info(f"   - Field: embedding")
            logger.info(f"   - Dimension: {settings.embedding_dimension}")
            logger.info("   - Similarity: cosine")

        if not qa_vector_index_found:
            all_ready = False
            logger.warning("2. Create vector index on qa_pairs.question_embedding:")
            logger.info("   - Go to MongoDB Atlas UI")
            logger.info("   - Navigate to Search Indexes")
            logger.info("   - Create Vector Search index")
            logger.info(f"   - Name: {settings.mongodb_vector_index} (or custom name)")
            logger.info(f"   - Collection: {settings.mongodb_collection_qa_pairs}")
            logger.info("   - Field: question_embedding")
            logger.info(f"   - Dimension: {settings.embedding_dimension}")
            logger.info("   - Similarity: cosine")

        if all_ready:
            logger.info("✅ All required indexes are present")
            logger.info("   System is ready for vector search operations")

        # Note about other indexes
        logger.info("\nNote: Other indexes (text, metadata filters) can be created using:")
        logger.info("  python scripts/create_indexes.py")
        logger.info("  python scripts/create_qa_indexes.py")

        return {
            "chunks_vector_index": vector_index_found,
            "chunks_text_index": text_index_found,
            "qa_pairs_vector_index": qa_vector_index_found,
            "all_ready": all_ready
        }

    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise
    except Exception as e:
        logger.exception(f"Error verifying indexes: {e}")
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
        result = await verify_indexes()
        if result["all_ready"]:
            sys.exit(0)
        else:
            logger.warning("\n⚠️  Some required indexes are missing")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("\nVerification interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Index verification failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

