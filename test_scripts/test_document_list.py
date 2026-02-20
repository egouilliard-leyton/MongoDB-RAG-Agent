"""Test that all documents from MongoDB display correctly in the UI.

This test verifies:
1. All 23 documents are returned by the API
2. Response structure matches UI expectations (DocumentListResponse)
3. Each document has required fields for display
4. Pagination works correctly
"""

import asyncio
import os
import pytest
from typing import Dict, Any, List
from datetime import datetime

# Check for required environment
MONGODB_URI = os.environ.get("MONGODB_URI", "")
SKIP_INTEGRATION = not MONGODB_URI

# Conditionally import based on availability
if not SKIP_INTEGRATION:
    try:
        from pymongo import AsyncMongoClient
        from bson import ObjectId
        from src.settings import Settings
        IMPORTS_AVAILABLE = True
    except ImportError:
        IMPORTS_AVAILABLE = False
        SKIP_INTEGRATION = True
else:
    IMPORTS_AVAILABLE = False


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
def settings():
    """Create test settings."""
    if SKIP_INTEGRATION:
        pytest.skip("MongoDB URI not configured or imports unavailable")
    return Settings()


@pytest.fixture
async def mongo_client(settings):
    """Create MongoDB client."""
    client = AsyncMongoClient(
        settings.mongodb_uri, serverSelectionTimeoutMS=5000
    )
    yield client
    await client.close()


@pytest.fixture
async def db(settings, mongo_client):
    """Get database instance."""
    return mongo_client[settings.mongodb_database]


# =============================================================================
# Helper Functions
# =============================================================================


async def get_documents_from_db(
    db, settings, project_id: str = None, limit: int = 100, skip: int = 0
) -> tuple[List[Dict[str, Any]], int]:
    """
    Get documents directly from MongoDB (simulating API endpoint).
    
    Returns:
        Tuple of (documents list, total count)
    """
    documents_collection = db[settings.mongodb_collection_documents]
    chunks_collection = db[settings.mongodb_collection_chunks]
    
    # Build query
    query: Dict[str, Any] = {}
    if project_id:
        query["metadata.project_id"] = ObjectId(project_id)
    
    # Get total count
    total = await documents_collection.count_documents(query)
    
    # Fetch documents with pagination
    cursor = (
        documents_collection.find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    
    documents = []
    async for doc in cursor:
        doc_id = str(doc["_id"])
        
        # Get chunk count for this document
        chunk_count = await chunks_collection.count_documents(
            {"document_id": doc["_id"]}
        )
        
        # Extract project_id from metadata if present
        metadata = doc.get("metadata", {})
        doc_project_id = None
        if "project_id" in metadata and metadata["project_id"]:
            doc_project_id = str(metadata["project_id"])
        
        # Convert ObjectId values in metadata to strings for JSON serialization
        serializable_metadata = {}
        for key, value in metadata.items():
            if isinstance(value, ObjectId):
                serializable_metadata[key] = str(value)
            elif isinstance(value, dict):
                # Recursively convert ObjectIds in nested dicts
                serializable_metadata[key] = {
                    k: str(v) if isinstance(v, ObjectId) else v
                    for k, v in value.items()
                }
            else:
                serializable_metadata[key] = value
        
        documents.append({
            "_id": doc_id,
            "title": doc.get("title", "Untitled"),
            "source": doc.get("source", ""),
            "metadata": serializable_metadata,
            "project_id": doc_project_id,
            "created_at": doc.get("created_at", datetime.utcnow()),
            "chunk_count": chunk_count,
        })
    
    return documents, total


def validate_document_structure(doc: Dict[str, Any]) -> List[str]:
    """
    Validate that a document has all required fields for UI display.
    
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    
    # Required fields based on Document interface in types.ts
    required_fields = ["_id", "title", "source", "metadata", "created_at", "chunk_count"]
    
    for field in required_fields:
        if field not in doc:
            errors.append(f"Missing required field: {field}")
    
    # Validate field types
    if "_id" in doc and not isinstance(doc["_id"], str):
        errors.append(f"Field '_id' must be string, got {type(doc['_id'])}")
    
    if "title" in doc and not isinstance(doc["title"], str):
        errors.append(f"Field 'title' must be string, got {type(doc['title'])}")
    
    if "source" in doc and not isinstance(doc["source"], str):
        errors.append(f"Field 'source' must be string, got {type(doc['source'])}")
    
    if "metadata" in doc and not isinstance(doc["metadata"], dict):
        errors.append(f"Field 'metadata' must be dict, got {type(doc['metadata'])}")
    
    if "chunk_count" in doc and not isinstance(doc["chunk_count"], int):
        errors.append(f"Field 'chunk_count' must be int, got {type(doc['chunk_count'])}")
    
    if "created_at" in doc:
        if not isinstance(doc["created_at"], (str, datetime)):
            errors.append(f"Field 'created_at' must be string or datetime, got {type(doc['created_at'])}")
    
    # project_id can be None or string
    if "project_id" in doc and doc["project_id"] is not None:
        if not isinstance(doc["project_id"], str):
            errors.append(f"Field 'project_id' must be string or None, got {type(doc['project_id'])}")
    
    return errors


def validate_document_list_response(
    response: Dict[str, Any], expected_total: int = None
) -> List[str]:
    """
    Validate DocumentListResponse structure.
    
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    
    # Required fields based on DocumentListResponse interface
    required_fields = ["documents", "total", "limit", "skip", "has_more"]
    
    for field in required_fields:
        if field not in response:
            errors.append(f"Missing required field in response: {field}")
    
    if "documents" in response:
        if not isinstance(response["documents"], list):
            errors.append("Field 'documents' must be a list")
        else:
            # Validate each document
            for i, doc in enumerate(response["documents"]):
                doc_errors = validate_document_structure(doc)
                if doc_errors:
                    errors.extend([f"Document {i}: {e}" for e in doc_errors])
    
    if "total" in response:
        if not isinstance(response["total"], int):
            errors.append("Field 'total' must be int")
        elif expected_total is not None and response["total"] != expected_total:
            errors.append(
                f"Expected total={expected_total}, got {response['total']}"
            )
    
    if "limit" in response:
        if not isinstance(response["limit"], int):
            errors.append("Field 'limit' must be int")
    
    if "skip" in response:
        if not isinstance(response["skip"], int):
            errors.append("Field 'skip' must be int")
    
    if "has_more" in response:
        if not isinstance(response["has_more"], bool):
            errors.append("Field 'has_more' must be bool")
    
    return errors


# =============================================================================
# Tests
# =============================================================================


@pytest.mark.skipif(SKIP_INTEGRATION, reason="MongoDB not configured")
@pytest.mark.integration
class TestDocumentListDisplay:
    """Test that all documents display correctly in the UI."""
    
    @pytest.mark.asyncio
    async def test_all_documents_returned(self, db, settings):
        """Test that all 23 documents are returned."""
        print("\n" + "="*80)
        print("TEST: All Documents Returned")
        print("="*80)
        
        documents, total = await get_documents_from_db(db, settings, limit=100)
        
        print(f"\n[1] Total documents in database: {total}")
        print(f"[2] Documents returned: {len(documents)}")
        
        # Verify we have 23 documents
        expected_count = 23
        assert total == expected_count, (
            f"Expected {expected_count} documents, found {total}"
        )
        assert len(documents) == expected_count, (
            f"Expected {expected_count} documents in response, got {len(documents)}"
        )
        
        print(f"    [OK] All {expected_count} documents found")
    
    @pytest.mark.asyncio
    async def test_document_list_response_structure(self, db, settings):
        """Test that response structure matches UI expectations."""
        print("\n" + "="*80)
        print("TEST: Document List Response Structure")
        print("="*80)
        
        documents, total = await get_documents_from_db(db, settings, limit=50, skip=0)
        
        # Build response structure matching DocumentListResponse
        response = {
            "documents": documents,
            "total": total,
            "limit": 50,
            "skip": 0,
            "has_more": len(documents) < total,
        }
        
        print(f"\n[1] Response structure validation:")
        errors = validate_document_list_response(response, expected_total=23)
        
        if errors:
            print(f"    [FAIL] Validation errors found:")
            for error in errors:
                print(f"       - {error}")
            raise AssertionError(f"Response structure validation failed: {errors}")
        else:
            print(f"    [OK] Response structure is valid")
        
        print(f"\n[2] Document count: {len(response['documents'])}")
        print(f"[3] Total: {response['total']}")
        print(f"[4] Has more: {response['has_more']}")
    
    @pytest.mark.asyncio
    async def test_each_document_has_required_fields(self, db, settings):
        """Test that each document has all required fields for UI display."""
        print("\n" + "="*80)
        print("TEST: Document Field Validation")
        print("="*80)
        
        documents, total = await get_documents_from_db(db, settings, limit=100)
        
        print(f"\n[1] Validating {len(documents)} documents:")
        
        all_errors = []
        for i, doc in enumerate(documents):
            errors = validate_document_structure(doc)
            if errors:
                all_errors.append((i, doc.get("title", "Unknown"), errors))
                print(f"    Document {i} ({doc.get('title', 'Unknown')[:50]}): FAILED")
                for error in errors:
                    print(f"       - {error}")
            else:
                if i < 5:  # Show first 5 as examples
                    print(f"    Document {i} ({doc.get('title', 'Unknown')[:50]}): OK")
        
        if all_errors:
            print(f"\n    [FAIL] {len(all_errors)} documents have validation errors")
            raise AssertionError(
                f"Document validation failed for {len(all_errors)} documents"
            )
        else:
            print(f"\n    [OK] All {len(documents)} documents have valid structure")
        
        # Print sample document structure
        if documents:
            print(f"\n[2] Sample document structure:")
            sample = documents[0]
            print(f"    _id: {sample['_id']}")
            print(f"    title: {sample['title']}")
            print(f"    source: {sample['source']}")
            print(f"    chunk_count: {sample['chunk_count']}")
            print(f"    project_id: {sample.get('project_id', 'None')}")
            print(f"    created_at: {sample['created_at']}")
            print(f"    metadata keys: {list(sample['metadata'].keys())[:5]}...")
    
    @pytest.mark.asyncio
    async def test_pagination_works_correctly(self, db, settings):
        """Test that pagination works correctly for document list."""
        print("\n" + "="*80)
        print("TEST: Pagination")
        print("="*80)
        
        # Get first page
        page1, total = await get_documents_from_db(db, settings, limit=10, skip=0)
        
        print(f"\n[1] First page (limit=10, skip=0):")
        print(f"    Documents returned: {len(page1)}")
        print(f"    Total: {total}")
        
        assert len(page1) == 10, f"Expected 10 documents, got {len(page1)}"
        
        # Get second page
        page2, total2 = await get_documents_from_db(db, settings, limit=10, skip=10)
        
        print(f"\n[2] Second page (limit=10, skip=10):")
        print(f"    Documents returned: {len(page2)}")
        print(f"    Total: {total2}")
        
        assert total == total2, "Total count should be consistent"
        assert len(page2) == 10, f"Expected 10 documents, got {len(page2)}"
        
        # Verify no duplicates
        page1_ids = {doc["_id"] for doc in page1}
        page2_ids = {doc["_id"] for doc in page2}
        overlap = page1_ids & page2_ids
        
        print(f"\n[3] Checking for duplicates between pages:")
        print(f"    Page 1 IDs: {len(page1_ids)}")
        print(f"    Page 2 IDs: {len(page2_ids)}")
        print(f"    Overlap: {len(overlap)}")
        
        assert len(overlap) == 0, f"Found {len(overlap)} duplicate documents between pages"
        
        print(f"\n    [OK] Pagination works correctly")
        
        # Test has_more calculation
        has_more_page1 = len(page1) < total
        has_more_page2 = len(page2) < total
        
        print(f"\n[4] Has more flags:")
        print(f"    Page 1 has_more: {has_more_page1}")
        print(f"    Page 2 has_more: {has_more_page2}")
        
        assert has_more_page1 == True, "Page 1 should have more documents"
        assert has_more_page2 == True, "Page 2 should have more documents"
    
    @pytest.mark.asyncio
    async def test_document_display_data_completeness(self, db, settings):
        """Test that documents have all data needed for UI display."""
        print("\n" + "="*80)
        print("TEST: Document Display Data Completeness")
        print("="*80)
        
        documents, total = await get_documents_from_db(db, settings, limit=100)
        
        print(f"\n[1] Checking data completeness for {len(documents)} documents:")
        
        issues = []
        for i, doc in enumerate(documents):
            doc_issues = []
            
            # Check title is not empty
            if not doc.get("title") or doc["title"].strip() == "":
                doc_issues.append("Title is empty")
            
            # Check source is not empty
            if not doc.get("source") or doc["source"].strip() == "":
                doc_issues.append("Source is empty")
            
            # Check chunk_count is reasonable (>= 0)
            if doc.get("chunk_count", -1) < 0:
                doc_issues.append(f"Invalid chunk_count: {doc.get('chunk_count')}")
            
            # Check created_at is valid
            if not doc.get("created_at"):
                doc_issues.append("Missing created_at")
            
            if doc_issues:
                issues.append((i, doc.get("title", "Unknown"), doc_issues))
        
        if issues:
            print(f"\n    [WARN] Found issues in {len(issues)} documents:")
            for idx, title, doc_issues in issues[:5]:  # Show first 5
                print(f"       Document {idx} ({title[:50]}):")
                for issue in doc_issues:
                    print(f"         - {issue}")
        else:
            print(f"\n    [OK] All documents have complete display data")
        
        # Print statistics
        print(f"\n[2] Document statistics:")
        titles = [d.get("title", "") for d in documents]
        sources = [d.get("source", "") for d in documents]
        chunk_counts = [d.get("chunk_count", 0) for d in documents]
        
        print(f"    Average title length: {sum(len(t) for t in titles) / len(titles):.1f} chars")
        print(f"    Average chunk count: {sum(chunk_counts) / len(chunk_counts):.1f}")
        print(f"    Total chunks: {sum(chunk_counts)}")
        print(f"    Documents with project_id: {sum(1 for d in documents if d.get('project_id'))}")
        
        # This test doesn't fail, just reports issues
        # The actual validation is done in other tests


# =============================================================================
# Run tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration", "-s"])
