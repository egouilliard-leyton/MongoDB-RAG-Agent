"""System health and index status endpoints."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from pymongo.errors import OperationFailure

from src.dependencies import AgentDependencies
from src.settings import load_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system", tags=["system"])


# =============================================================================
# Response Models
# =============================================================================


class DatabaseStatus(BaseModel):
    """Database connection status."""
    connected: bool
    database: str
    latency_ms: Optional[float] = None
    error: Optional[str] = None


class CollectionStatus(BaseModel):
    """Collection status details."""
    name: str
    document_count: int
    status: str  # "available", "empty", "error"
    error: Optional[str] = None


class IndexInfo(BaseModel):
    """Vector search index information."""
    name: str
    type: str
    status: str  # "ready", "building", "not_found", "error"
    dimensions: Optional[int] = None
    similarity: Optional[str] = None
    num_vectors: Optional[int] = None
    error: Optional[str] = None


class IndexVerificationResult(BaseModel):
    """Result of index verification test."""
    searchable: bool
    document_id: Optional[str] = None
    search_latency_ms: Optional[float] = None
    chunks_found: int = 0
    error: Optional[str] = None


class HealthCheckResponse(BaseModel):
    """Response model for system health check."""
    status: str  # "healthy", "degraded", "unhealthy"
    timestamp: datetime
    database: DatabaseStatus
    collections: Dict[str, CollectionStatus]
    background_tasks: Optional[Dict[str, Any]] = None


class IndexStatusResponse(BaseModel):
    """Response model for index status."""
    vector_index: IndexInfo
    text_index: Optional[IndexInfo] = None
    verification: IndexVerificationResult
    recommendations: List[str] = Field(default_factory=list)


# =============================================================================
# Helper Functions
# =============================================================================


async def verify_index_with_search(
    deps: AgentDependencies,
    document_id: Optional[str] = None,
    max_retries: int = 3,
) -> IndexVerificationResult:
    """
    Verify the vector search index is working by performing a test search.

    Args:
        deps: Agent dependencies with initialized MongoDB connection
        document_id: Optional specific document ID to search for
        max_retries: Number of retry attempts for the search

    Returns:
        IndexVerificationResult with search test results
    """
    settings = deps.settings
    chunks_collection = deps.db[settings.mongodb_collection_chunks]

    for attempt in range(max_retries):
        try:
            start_time = datetime.now(timezone.utc)

            # Build a simple vector search query
            # Use a sample embedding or search for a known document
            if document_id:
                # Search with filter for specific document
                pipeline = [
                    {
                        "$vectorSearch": {
                            "index": settings.mongodb_vector_index,
                            "path": "embedding",
                            "queryVector": [0.0] * settings.embedding_dimension,  # Dummy vector
                            "numCandidates": 100,
                            "limit": 5,
                            "filter": {"document_id": document_id},
                        }
                    },
                    {"$limit": 5},
                    {"$project": {"_id": 1, "document_id": 1}},
                ]
            else:
                # General search without filter
                pipeline = [
                    {
                        "$vectorSearch": {
                            "index": settings.mongodb_vector_index,
                            "path": "embedding",
                            "queryVector": [0.0] * settings.embedding_dimension,  # Dummy vector
                            "numCandidates": 100,
                            "limit": 5,
                        }
                    },
                    {"$limit": 5},
                    {"$project": {"_id": 1, "document_id": 1}},
                ]

            cursor = await chunks_collection.aggregate(pipeline)
            results = await cursor.to_list(length=5)

            end_time = datetime.now(timezone.utc)
            latency_ms = (end_time - start_time).total_seconds() * 1000

            if results:
                return IndexVerificationResult(
                    searchable=True,
                    document_id=str(results[0].get("document_id")) if results else None,
                    search_latency_ms=round(latency_ms, 2),
                    chunks_found=len(results),
                )
            else:
                # No results but no error - index exists but may be empty or building
                return IndexVerificationResult(
                    searchable=True,
                    search_latency_ms=round(latency_ms, 2),
                    chunks_found=0,
                )

        except OperationFailure as e:
            error_code = getattr(e, "code", None)

            # Error code 291 = Index not found
            if error_code == 291:
                return IndexVerificationResult(
                    searchable=False,
                    error=f"Vector search index '{settings.mongodb_vector_index}' not found. Create in Atlas UI.",
                )

            # Other operation failures
            if attempt < max_retries - 1:
                await asyncio.sleep(1)  # Wait before retry
                continue

            return IndexVerificationResult(
                searchable=False,
                error=f"Search operation failed: {str(e)}",
            )

        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(1)
                continue

            return IndexVerificationResult(
                searchable=False,
                error=f"Unexpected error: {str(e)}",
            )

    return IndexVerificationResult(
        searchable=False,
        error="Max retries exceeded",
    )


async def get_index_info(
    deps: AgentDependencies,
    index_name: str,
    index_type: str = "vectorSearch",
) -> IndexInfo:
    """
    Get information about a search index.

    Note: MongoDB Atlas search indexes are not directly queryable via the driver.
    We check if the index exists by attempting to use it.

    Args:
        deps: Agent dependencies
        index_name: Name of the index
        index_type: Type of index ("vectorSearch" or "search")

    Returns:
        IndexInfo with index details
    """
    settings = deps.settings
    chunks_collection = deps.db[settings.mongodb_collection_chunks]

    try:
        # Try to list search indexes (only works with certain privileges)
        # This is an Atlas-specific command
        indexes = await chunks_collection.list_search_indexes().to_list()

        for idx in indexes:
            if idx.get("name") == index_name:
                # Found the index
                idx_type = idx.get("type", "unknown")
                status = idx.get("status", "unknown")

                # Extract definition details
                definition = idx.get("latestDefinition", {})
                mappings = definition.get("mappings", {})
                fields = mappings.get("fields", {})

                # For vector indexes, extract dimensions and similarity
                embedding_field = fields.get("embedding", {})
                dimensions = embedding_field.get("dimensions")
                similarity = embedding_field.get("similarity")

                return IndexInfo(
                    name=index_name,
                    type=idx_type,
                    status="ready" if status == "READY" else status.lower(),
                    dimensions=dimensions,
                    similarity=similarity,
                )

        # Index not found in list
        return IndexInfo(
            name=index_name,
            type=index_type,
            status="not_found",
            error=f"Index '{index_name}' not found in Atlas search indexes",
        )

    except OperationFailure as e:
        # Fallback: we can't list indexes directly, try to verify by usage
        return IndexInfo(
            name=index_name,
            type=index_type,
            status="unknown",
            error="Cannot list search indexes. Verifying via test search.",
        )

    except Exception as e:
        return IndexInfo(
            name=index_name,
            type=index_type,
            status="error",
            error=str(e),
        )


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/health", response_model=HealthCheckResponse)
async def system_health_check():
    """
    Comprehensive system health check.

    Checks:
    - MongoDB database connectivity and latency
    - Collection status (documents, chunks, qa_sessions, qa_pairs)
    - Document and chunk counts

    Returns health status: "healthy", "degraded", or "unhealthy".

    - healthy: All systems operational
    - degraded: Core systems work but some issues exist (empty collections, etc.)
    - unhealthy: Critical systems unavailable (database connection failed)
    """
    settings = load_settings()
    deps = AgentDependencies()

    # Initialize response with defaults
    db_status = DatabaseStatus(
        connected=False,
        database=settings.mongodb_database,
    )
    collections_status: Dict[str, CollectionStatus] = {}
    overall_status = "unhealthy"

    try:
        # Test database connection with ping
        start_time = datetime.now(timezone.utc)
        await deps.initialize()

        # Measure ping latency
        await deps.mongo_client.admin.command("ping")
        end_time = datetime.now(timezone.utc)
        latency_ms = (end_time - start_time).total_seconds() * 1000

        db_status = DatabaseStatus(
            connected=True,
            database=settings.mongodb_database,
            latency_ms=round(latency_ms, 2),
        )

        # Check each collection
        collection_names = [
            settings.mongodb_collection_documents,
            settings.mongodb_collection_chunks,
            settings.mongodb_collection_qa_sessions,
            settings.mongodb_collection_qa_pairs,
        ]

        for coll_name in collection_names:
            try:
                count = await deps.db[coll_name].count_documents({})
                collections_status[coll_name] = CollectionStatus(
                    name=coll_name,
                    document_count=count,
                    status="available" if count > 0 else "empty",
                )
            except Exception as e:
                collections_status[coll_name] = CollectionStatus(
                    name=coll_name,
                    document_count=0,
                    status="error",
                    error=str(e),
                )

        # Determine overall status
        has_errors = any(c.status == "error" for c in collections_status.values())
        has_empty = any(c.status == "empty" for c in collections_status.values())

        if has_errors:
            overall_status = "degraded"
        elif has_empty:
            overall_status = "degraded"
        else:
            overall_status = "healthy"

    except Exception as e:
        logger.exception(f"Health check failed: {e}")
        db_status.error = str(e)
        overall_status = "unhealthy"

    finally:
        await deps.cleanup()

    return HealthCheckResponse(
        status=overall_status,
        timestamp=datetime.now(timezone.utc),
        database=db_status,
        collections=collections_status,
    )


@router.get("/index-status", response_model=IndexStatusResponse)
async def get_index_status(
    document_id: Optional[str] = Query(
        None,
        description="Optional document ID to verify in search results"
    ),
):
    """
    Get vector search index status and verify searchability.

    This endpoint:
    1. Retrieves information about the vector search index configuration
    2. Optionally checks the text search index
    3. Performs a verification search to confirm the index is working
    4. Provides recommendations for any issues found

    MongoDB Atlas Vector Search indexes update automatically when documents
    are inserted. New documents typically appear in search results within seconds.

    Args:
        document_id: Optional document ID to specifically verify is searchable

    Returns:
        Index status information with verification results and recommendations
    """
    settings = load_settings()
    deps = AgentDependencies()
    recommendations: List[str] = []

    # Validate document_id format if provided (raises ValidationError -> 400)
    if document_id is not None:
        from src.api.validators import validate_object_id
        validate_object_id(document_id, "Document")

    try:
        await deps.initialize()

        # Get vector index info
        vector_index = await get_index_info(
            deps,
            settings.mongodb_vector_index,
            "vectorSearch"
        )

        # Get text index info (optional)
        text_index = None
        if settings.mongodb_text_index:
            text_index = await get_index_info(
                deps,
                settings.mongodb_text_index,
                "search"
            )

        # Verify index with actual search
        verification = await verify_index_with_search(
            deps,
            document_id=document_id,
        )

        # Generate recommendations based on findings
        if not verification.searchable:
            if "not found" in (verification.error or "").lower():
                recommendations.append(
                    f"Create vector search index '{settings.mongodb_vector_index}' in MongoDB Atlas UI"
                )
            else:
                recommendations.append(
                    "Check MongoDB Atlas for index status and any error messages"
                )

        if vector_index.status == "not_found":
            recommendations.append(
                "Vector search index is required for semantic search functionality"
            )
        elif vector_index.status == "building":
            recommendations.append(
                "Index is still building. Search may return incomplete results."
            )

        if verification.chunks_found == 0 and verification.searchable:
            recommendations.append(
                "No chunks found in search. Upload documents using /api/documents/upload"
            )

        if text_index and text_index.status == "not_found":
            recommendations.append(
                f"Text search index '{settings.mongodb_text_index}' not found. "
                "Hybrid search may not work optimally."
            )

        return IndexStatusResponse(
            vector_index=vector_index,
            text_index=text_index,
            verification=verification,
            recommendations=recommendations,
        )

    except Exception as e:
        logger.exception(f"Index status check failed: {e}")
        return IndexStatusResponse(
            vector_index=IndexInfo(
                name=settings.mongodb_vector_index,
                type="vectorSearch",
                status="error",
                error=str(e),
            ),
            text_index=None,
            verification=IndexVerificationResult(
                searchable=False,
                error=str(e),
            ),
            recommendations=[
                "Failed to check index status. Verify MongoDB connection and permissions."
            ],
        )

    finally:
        await deps.cleanup()


@router.get("/verify-document/{document_id}")
async def verify_document_indexed(
    document_id: str,
    max_retries: int = Query(3, ge=1, le=10, description="Maximum retry attempts"),
    retry_delay_seconds: float = Query(1.0, ge=0.5, le=5.0, description="Delay between retries"),
) -> Dict[str, Any]:
    """
    Verify a specific document is searchable in the vector index.

    After uploading a new document, use this endpoint to confirm the document's
    chunks are indexed and searchable. MongoDB Atlas typically indexes new
    documents within seconds, but this endpoint provides explicit verification.

    Args:
        document_id: The document ID to verify
        max_retries: Number of times to retry if document not found (default: 3)
        retry_delay_seconds: Seconds to wait between retries (default: 1.0)

    Returns:
        Verification result with searchability status and chunk count
    """
    from src.api.validators import validate_object_id
    from bson import ObjectId

    validate_object_id(document_id, "Document")

    settings = load_settings()
    deps = AgentDependencies()

    try:
        await deps.initialize()

        # First check if the document exists
        doc = await deps.db[settings.mongodb_collection_documents].find_one(
            {"_id": ObjectId(document_id)}
        )

        if not doc:
            return {
                "document_id": document_id,
                "exists": False,
                "indexed": False,
                "chunks_in_database": 0,
                "chunks_searchable": 0,
                "message": "Document not found in database",
            }

        # Count chunks in database for this document
        chunks_in_db = await deps.db[settings.mongodb_collection_chunks].count_documents(
            {"document_id": ObjectId(document_id)}
        )

        if chunks_in_db == 0:
            return {
                "document_id": document_id,
                "exists": True,
                "indexed": False,
                "chunks_in_database": 0,
                "chunks_searchable": 0,
                "message": "Document exists but has no chunks. Ingestion may have failed.",
            }

        # Try to find chunks via vector search (verifies they're indexed)
        chunks_searchable = 0
        for attempt in range(max_retries):
            try:
                # Use a simple aggregation to check if chunks with this document_id
                # are accessible via vector search
                pipeline = [
                    {
                        "$vectorSearch": {
                            "index": settings.mongodb_vector_index,
                            "path": "embedding",
                            "queryVector": [0.0] * settings.embedding_dimension,
                            "numCandidates": 100,
                            "limit": 50,
                            "filter": {"document_id": ObjectId(document_id)},
                        }
                    },
                    {"$count": "total"},
                ]

                result = await deps.db[settings.mongodb_collection_chunks].aggregate(
                    pipeline
                ).to_list(length=1)

                chunks_searchable = result[0]["total"] if result else 0

                if chunks_searchable > 0:
                    break

            except OperationFailure as e:
                if e.code == 291:  # Index not found
                    return {
                        "document_id": document_id,
                        "exists": True,
                        "indexed": False,
                        "chunks_in_database": chunks_in_db,
                        "chunks_searchable": 0,
                        "message": f"Vector search index '{settings.mongodb_vector_index}' not found",
                        "error": str(e),
                    }

            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay_seconds)

        indexed = chunks_searchable > 0

        return {
            "document_id": document_id,
            "exists": True,
            "indexed": indexed,
            "chunks_in_database": chunks_in_db,
            "chunks_searchable": chunks_searchable,
            "message": (
                "Document is fully indexed and searchable"
                if chunks_searchable >= chunks_in_db
                else f"Document partially indexed ({chunks_searchable}/{chunks_in_db} chunks searchable)"
                if indexed
                else "Document chunks are in database but not yet searchable. Index may be building."
            ),
            "retry_attempts": max_retries if not indexed else None,
        }

    except Exception as e:
        logger.exception(f"Document verification failed: {e}")
        return {
            "document_id": document_id,
            "exists": None,
            "indexed": False,
            "chunks_in_database": None,
            "chunks_searchable": 0,
            "message": "Verification failed",
            "error": str(e),
        }

    finally:
        await deps.cleanup()
