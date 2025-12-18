# PDF Structure Testing Suite

This directory contains comprehensive tests for the PDF structure enhancements, including metadata extraction, section-aware chunking, and metadata filtering.

## Test Structure

The tests are organized into 7 phases:

1. **Phase 1: Metadata Extraction** (`test_metadata_extractor.py`)
   - Tests metadata extraction from document headers
   - Tests filename parsing
   - Tests enhanced title extraction with 5 fallback strategies
   - Tests keyword extraction as arrays

2. **Phase 2: Section Identification** (`test_section_identifier.py`)
   - Tests H2 heading detection
   - Tests section type classification
   - Tests section content extraction

3. **Phase 3: Section-Aware Chunking** (`test_section_aware_chunking.py`)
   - Tests section-aware chunking with variable token limits
   - Tests header chunking (200 token limit)
   - Tests przepis/zagadnienie chunking (400 token limit)
   - Tests main content chunking (800 token limit)

4. **Phase 4: Ingestion Pipeline** (`test_ingestion_pipeline.py`)
   - Tests end-to-end document processing with dry-run mode
   - Tests metadata flow through pipeline
   - Tests section-aware chunking integration

5. **Phase 5: MongoDB Schema Validation** (`test_mongodb_schema_validation.py`)
   - **Read-only** tests against existing MongoDB data
   - Validates document metadata structure
   - Validates chunk metadata structure
   - Checks for section metadata in chunks

6. **Phase 6: Metadata Filtering** (`test_metadata_filtering.py`)
   - **Read-only** tests for search filtering
   - Tests semantic search with filters
   - Tests text search with filters
   - Tests hybrid search with filters

7. **Phase 7: Agent Integration** (`test_agent_metadata_queries.py`)
   - **Read-only** tests for agent with metadata queries
   - Tests agent's use of metadata filters
   - Tests citation metadata

## Test Utilities

- `test_utils.py` - Utility functions for test data creation and validation
- `prepare_test_data.py` - Script to prepare test fixtures from PDFs

## Running Tests

### Prerequisites

1. Install dependencies:
   ```bash
   uv sync
   ```

2. (Optional) Prepare test data:
   ```bash
   python test_scripts/prepare_test_data.py
   ```

### Phase 1-3: Unit Tests (No MongoDB Required)

These tests run independently and don't require MongoDB:

```bash
# Phase 1: Metadata extraction
python test_scripts/test_metadata_extractor.py

# Phase 2: Section identification
python test_scripts/test_section_identifier.py

# Phase 3: Section-aware chunking
python test_scripts/test_section_aware_chunking.py
```

### Phase 4: Integration Tests (Dry-Run Mode)

Tests the ingestion pipeline without modifying MongoDB:

```bash
# Test ingestion pipeline with dry-run
python -m src.ingestion.ingest -d documents --dry-run

# Or run the test script
python test_scripts/test_ingestion_pipeline.py
```

### Phase 5-7: Read-Only MongoDB Tests

These tests query existing MongoDB data but don't modify it:

```bash
# Phase 5: Schema validation
python test_scripts/test_mongodb_schema_validation.py

# Phase 6: Metadata filtering
python test_scripts/test_metadata_filtering.py

# Phase 7: Agent integration (requires LLM API)
python test_scripts/test_agent_metadata_queries.py
```

## Test Execution Order

Recommended execution order:

1. **Start with Phase 1-3** (unit tests, fast feedback)
   - Fix any issues before proceeding
   - No MongoDB connection required

2. **Then Phase 4** (integration tests)
   - Verify pipeline integration
   - Uses dry-run mode (no MongoDB writes)

3. **Finally Phase 5-7** (validation tests)
   - Validate against existing MongoDB data
   - All tests are read-only

## Expected Results

### Metadata Extraction
- ✅ All header fields extracted correctly
- ✅ Filename parsed correctly
- ✅ Title from `tytul_teza` (not filename)
- ✅ Keywords as array

### Section Identification
- ✅ All H2 headings detected
- ✅ Section types classified correctly
- ✅ Section count accurate

### Chunking
- ✅ Chunk count reduced (30-50 vs 88-112 per document)
- ✅ Section boundaries respected
- ✅ Section metadata in chunks
- ✅ Token limits enforced (200/400/800)

### Search
- ✅ Metadata filters work correctly
- ✅ Filters reduce results appropriately
- ✅ No false positives/negatives

### Agent
- ✅ Agent uses metadata filters when appropriate
- ✅ Citations include document IDs

## Troubleshooting

### No documents found in MongoDB
If Phase 5-7 tests report "No documents found":
- Run ingestion first: `python -m src.ingestion.ingest -d documents`
- Or use dry-run mode: `python -m src.ingestion.ingest -d documents --dry-run`

### Missing test fixtures
If tests fail due to missing fixtures:
- Run: `python test_scripts/prepare_test_data.py`
- Or ensure PDF files exist in `documents/` folder

### LLM API errors (Phase 7)
Phase 7 tests require LLM API access:
- Ensure `.env` file has valid API keys
- Some failures may be expected if agent doesn't use filters for certain queries

## Notes

- All MongoDB tests are **read-only** - no data modifications
- Unit tests (Phase 1-3) run independently (no MongoDB required)
- Integration tests (Phase 4) use dry-run mode or test database
- Validation tests (Phase 5-7) check existing MongoDB data structure
- Phase 7 tests may incur LLM API costs

