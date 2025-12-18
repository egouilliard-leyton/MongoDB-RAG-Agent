"""
Verify document ingestion status in MongoDB.

This script checks if documents and chunks exist in the database,
verifies embeddings are present, and provides recommendations.
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


async def verify_ingestion():
    """Verify document ingestion status."""
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

        # Check document count
        doc_count = await documents_collection.count_documents({})
        logger.info(f"\nDocuments collection: {doc_count} documents")

        # Check chunk count
        chunk_count = await chunks_collection.count_documents({})
        logger.info(f"Chunks collection: {chunk_count} chunks")

        # Sample chunks to verify embeddings
        sample_size = min(10, chunk_count)
        chunks_with_embeddings = 0
        chunks_without_embeddings = 0

        if chunk_count > 0:
            logger.info(f"\nSampling {sample_size} chunks to verify embeddings...")
            async for chunk in chunks_collection.find({}).limit(sample_size):
                if chunk.get("embedding"):
                    embedding = chunk["embedding"]
                    if isinstance(embedding, list) and len(embedding) > 0:
                        chunks_with_embeddings += 1
                    else:
                        chunks_without_embeddings += 1
                else:
                    chunks_without_embeddings += 1

            logger.info(f"  ✓ Chunks with embeddings: {chunks_with_embeddings}")
            if chunks_without_embeddings > 0:
                logger.warning(f"  ✗ Chunks without embeddings: {chunks_without_embeddings}")

        # Check for PDFs in documents folder
        documents_folder = Path(__file__).parent.parent / "documents"
        pdf_files = list(documents_folder.glob("*.pdf")) if documents_folder.exists() else []
        logger.info(f"\nPDF files in documents/ folder: {len(pdf_files)}")

        # Generate report
        logger.info("\n" + "="*60)
        logger.info("INGESTION STATUS REPORT")
        logger.info("="*60)

        if doc_count == 0:
            logger.warning("⚠️  NO DOCUMENTS FOUND IN DATABASE")
            logger.info("   Action required: Run document ingestion")
            logger.info(f"   Command: uv run python -m src.ingestion.ingest -d ./documents")
            logger.info(f"   PDF files available: {len(pdf_files)}")
        else:
            logger.info(f"✅ Documents found: {doc_count}")

        if chunk_count == 0:
            logger.warning("⚠️  NO CHUNKS FOUND IN DATABASE")
            logger.info("   Action required: Run document ingestion")
        else:
            logger.info(f"✅ Chunks found: {chunk_count}")

        if chunk_count > 0:
            embedding_percentage = (chunks_with_embeddings / sample_size * 100) if sample_size > 0 else 0
            if embedding_percentage == 100:
                logger.info(f"✅ Embeddings verified: {chunks_with_embeddings}/{sample_size} chunks have embeddings")
            elif embedding_percentage > 0:
                logger.warning(f"⚠️  Partial embeddings: {chunks_with_embeddings}/{sample_size} chunks have embeddings ({embedding_percentage:.1f}%)")
            else:
                logger.error(f"✗ NO EMBEDDINGS FOUND: {chunks_without_embeddings}/{sample_size} chunks missing embeddings")
                logger.info("   Action required: Re-run ingestion to generate embeddings")

        # Recommendations
        logger.info("\n" + "="*60)
        logger.info("RECOMMENDATIONS")
        logger.info("="*60)

        if doc_count == 0 or chunk_count == 0:
            logger.info("1. Run document ingestion:")
            logger.info("   uv run python -m src.ingestion.ingest -d ./documents")
        elif chunks_without_embeddings > 0:
            logger.info("1. Re-run ingestion to generate missing embeddings")
        else:
            logger.info("✅ Ingestion status: OK")
            logger.info("   Documents and chunks are ready for question processing")

        if doc_count > 0 and chunk_count > 0 and chunks_with_embeddings == sample_size:
            logger.info("2. Verify vector indexes exist:")
            logger.info("   python scripts/verify_indexes.py")

        return {
            "documents_count": doc_count,
            "chunks_count": chunk_count,
            "chunks_with_embeddings": chunks_with_embeddings,
            "chunks_without_embeddings": chunks_without_embeddings,
            "pdf_files_available": len(pdf_files),
            "ready_for_processing": doc_count > 0 and chunk_count > 0 and chunks_with_embeddings > 0
        }

    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise
    except Exception as e:
        logger.exception(f"Error verifying ingestion: {e}")
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
        result = await verify_ingestion()
        if result["ready_for_processing"]:
            sys.exit(0)
        else:
            logger.warning("\n⚠️  System not ready for question processing")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("\nVerification interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Ingestion verification failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

