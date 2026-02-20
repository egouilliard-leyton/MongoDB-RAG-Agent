# MongoDB Atlas Vector Search Index Auto-Sync Behavior

## Overview

MongoDB Atlas Vector Search indexes automatically update when documents are inserted, updated, or deleted from the indexed collection. This document describes the behavior and best practices for working with vector search indexes in this application.

## Index Update Behavior

### Automatic Synchronization

- **Near Real-Time**: New documents typically appear in search results within **1-3 seconds** after insertion
- **No Manual Refresh**: Unlike some search engines, MongoDB Atlas does not require manual index refresh or rebuild operations
- **Background Processing**: Index updates happen asynchronously in the background without blocking write operations
- **Eventual Consistency**: There is a brief period between document insertion and index availability (typically < 3 seconds)

### Index Building States

MongoDB Atlas vector search indexes can be in the following states:

| State | Description |
|-------|-------------|
| `READY` | Index is fully built and operational |
| `BUILDING` | Index is being built or rebuilt (initial creation or after schema change) |
| `FAILED` | Index build failed (check Atlas UI for details) |
| `PENDING` | Index creation is queued |

### Important Notes

1. **Index Must Be Created in Atlas UI**: Vector search indexes cannot be created programmatically via the MongoDB driver. They must be created through:
   - MongoDB Atlas UI
   - Atlas Admin API
   - Atlas CLI

2. **Schema Changes Trigger Rebuild**: Modifying the index definition triggers a full rebuild. During rebuild:
   - The old index continues serving queries
   - New documents may not be searchable until rebuild completes

3. **Collection Size Impact**: Larger collections take longer to rebuild indexes

## Implementation in This Application

### Document Upload Flow

1. File uploaded via `POST /api/documents/upload`
2. Document converted, chunked, and embedded
3. Chunks inserted into `chunks` collection
4. **Verification step**: Application waits briefly and verifies document is searchable
5. Response includes ingestion results

### Verification Mechanism

The application provides verification at multiple levels:

#### 1. Post-Upload Verification (Automatic)
After document ingestion, the system automatically verifies the document is indexed:

```python
# In ingestion pipeline (src/ingestion/ingest.py)
async def verify_document_indexed(document_id: str, max_retries: int = 3) -> bool:
    """Verify document chunks are searchable via vector search."""
    for attempt in range(max_retries):
        result = await chunks_collection.aggregate([
            {"$vectorSearch": {..., "filter": {"document_id": document_id}}},
            {"$limit": 1}
        ]).to_list(length=1)
        if result:
            return True
        await asyncio.sleep(1)  # Wait before retry
    return False
```

#### 2. Manual Verification Endpoint
`GET /api/system/verify-document/{document_id}`

Explicitly check if a document's chunks are indexed:

```json
{
  "document_id": "675abc123...",
  "exists": true,
  "indexed": true,
  "chunks_in_database": 12,
  "chunks_searchable": 12,
  "message": "Document is fully indexed and searchable"
}
```

#### 3. System Index Status
`GET /api/system/index-status`

Check overall vector search index health:

```json
{
  "vector_index": {
    "name": "vector_index",
    "type": "vectorSearch",
    "status": "ready"
  },
  "verification": {
    "searchable": true,
    "chunks_found": 1234,
    "search_latency_ms": 45.2
  },
  "recommendations": []
}
```

## Best Practices

### For Document Upload

1. **Don't rely on immediate availability**: After upload, wait at least 1-2 seconds before searching
2. **Use verification endpoints**: For critical workflows, verify documents are indexed before proceeding
3. **Handle partial indexing gracefully**: Show appropriate UI feedback during the brief indexing window

### For Search Implementation

1. **Retry on empty results**: If searching immediately after upload and getting no results, retry with a short delay
2. **Monitor index status**: Use `/api/system/index-status` to check index health
3. **Log search latencies**: Unusual latencies may indicate index issues

### For Production Monitoring

1. **Set up Atlas alerts**: Configure alerts for index build failures
2. **Monitor index size**: Track vector index size growth
3. **Review search latencies**: Periodically check search performance metrics

## Index Configuration

### Vector Search Index Definition

Create this index in MongoDB Atlas on the `chunks` collection:

```json
{
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 1536,
      "similarity": "cosine"
    },
    {
      "type": "filter",
      "path": "document_id"
    },
    {
      "type": "filter",
      "path": "metadata.project_id"
    }
  ]
}
```

### Required Filters

Include filter fields for:
- `document_id` - For document-scoped searches
- `metadata.project_id` - For project-scoped searches

## Troubleshooting

### Document Not Appearing in Search

1. **Check if document exists**: `GET /api/documents/{id}`
2. **Check if chunks exist**: Verify `chunks_created > 0` in upload response
3. **Verify index status**: `GET /api/system/index-status`
4. **Check specific document**: `GET /api/system/verify-document/{id}`

### Index Not Found Error (Code 291)

This error means the vector search index doesn't exist. Solution:
1. Navigate to MongoDB Atlas UI
2. Go to the collection's "Search Indexes" tab
3. Create a new vector search index with the configuration above

### Slow Search Performance

1. Check Atlas cluster metrics
2. Review index definition (numCandidates setting)
3. Consider adding pre-filters to reduce candidate set

## References

- [MongoDB Atlas Vector Search Documentation](https://www.mongodb.com/docs/atlas/atlas-search/vector-search/)
- [Vector Search Index Definition](https://www.mongodb.com/docs/atlas/atlas-search/define-field-mappings-for-vector-search/)
- [Atlas Search Index Management](https://www.mongodb.com/docs/atlas/atlas-search/manage-indexes/)
