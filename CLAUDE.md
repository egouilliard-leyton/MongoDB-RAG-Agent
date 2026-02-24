# MongoDB RAG Agent Development Instructions

## Project Overview

Agentic RAG system combining MongoDB Atlas Vector Search with Pydantic AI for intelligent document retrieval. Uses Docling for multi-format ingestion, Motor for async MongoDB operations, and hybrid search via `$rankFusion`. Built with UV, type-safe Pydantic models, and conversational CLI.

## Core Principles

1. **TYPE SAFETY IS NON-NEGOTIABLE**
   - All functions, methods, and variables MUST have type annotations
   - Use Pydantic models for all data structures (documents, chunks, search results)
   - No `Any` types without explicit justification

2. **KISS** (Keep It Simple, Stupid)
   - Prefer simple, readable solutions over clever abstractions
   - Don't build fallback mechanisms unless absolutely necessary
   - Trust MongoDB `$rankFusion` - no manual score combination

3. **YAGNI** (You Aren't Gonna Need It)
   - Don't build features until they're actually needed
   - MVP first, enhancements later

4. **ASYNC ALL THE WAY**
   - All I/O operations MUST be async (MongoDB, embeddings, LLM calls)
   - Use `asyncio` for concurrent operations
   - Proper cleanup with `try/finally` or context managers

**Architecture:**

**Production code lives in `src/` — `examples/` is legacy PostgreSQL/pgvector CLI code.**

```
src/
├── agent.py, tools.py, dependencies.py, providers.py, prompts.py, settings.py
├── api/
│   ├── main.py        # FastAPI app, lifespan, middleware, router inclusion
│   ├── models.py      # Shared Pydantic request/response models
│   └── routes/        # One file per feature: questions, sessions, qa_pairs,
│                      # documents, projects, ingestion, export, dashboard,
│                      # settings, workflows, system, admin, tax_offices, regions, industries
├── services/          # Business logic: QAStorageService, ProjectStorageService,
│                      # SettingsService, WorkflowService, AnalyticsService, ExportService, ...
├── models/            # Feature-specific Pydantic models: settings_models.py, workflow_models.py
└── ingestion/         # chunker.py, embedder.py, ingest.py, metadata_extractor.py
```

**MongoDB Collections (all configured in `src/settings.py`):**
- `documents`, `chunks` — core RAG storage
- `qa_sessions`, `qa_pairs` — session management
- `projects`, `tax_offices`, `regions`, `industries` — reference data
- `app_settings` — global settings + version history
- `workflow_templates` — stage workflow templates

---

## Documentation Style

**Use Google-style docstrings** for all functions, classes, and modules:

```python
async def semantic_search(
    ctx: RunContext[AgentDependencies],
    query: str,
    match_count: Optional[int] = None
) -> list[SearchResult]:
    """
    Perform pure semantic search using vector similarity.

    Args:
        ctx: Agent runtime context with dependencies
        query: Search query text
        match_count: Number of results to return (default: 10)

    Returns:
        List of search results ordered by similarity

    Raises:
        ConnectionFailure: If MongoDB connection fails
        ValueError: If match_count exceeds maximum allowed
    """
```

---

## Development Workflow

**Setup environment:**
```bash
# Install UV (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment
uv venv

# Activate environment
source .venv/bin/activate  # Unix
.venv\Scripts\activate     # Windows

# Install dependencies
uv pip install -e .
```

**Run ingestion:**
```bash
uv run python -m examples.ingestion.ingest -d ./documents

# With options
uv run python -m examples.ingestion.ingest -d ./documents --chunk-size 1000 --no-clean
```

**Run CLI agent:**
```bash
uv run python -m examples.cli
```

**Common CLI commands:**
- `info` - Show system configuration
- `clear` - Clear screen
- `exit` / `quit` / `q` - Exit agent

**Run src/ layer (production):**
```bash
# Backend — ALWAYS use --reload so code changes are picked up immediately
uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend
cd frontend && npm run dev   # http://localhost:5173

# API E2E tests (requires running backend on :8000)
uv run pytest tests/e2e/ -v -m e2e

# Playwright browser tests (requires backend :8000 + frontend :5173)
cd frontend && npm run test:e2e
```

---

## Configuration Management

### Environment Variables

**ALL configuration in .env file:**
```bash
# MongoDB
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/
MONGODB_DATABASE=rag_db
MONGODB_COLLECTION_DOCUMENTS=documents
MONGODB_COLLECTION_CHUNKS=chunks
MONGODB_VECTOR_INDEX=vector_index
MONGODB_TEXT_INDEX=text_index

# LLM Provider
LLM_PROVIDER=openrouter
LLM_API_KEY=sk-or-v1-...
LLM_MODEL=anthropic/claude-haiku-4.5
LLM_BASE_URL=https://openrouter.ai/api/v1

# Embedding Provider
EMBEDDING_PROVIDER=openai
EMBEDDING_API_KEY=sk-...
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_BASE_URL=https://api.openai.com/v1
```

### Pydantic Settings

**Use Pydantic Settings for type-safe configuration:**
```python
from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict

class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )

    mongodb_uri: str = Field(..., description="MongoDB connection string")
    mongodb_database: str = Field(default="rag_db")
    llm_api_key: str = Field(..., description="LLM provider API key")
    embedding_model: str = Field(default="text-embedding-3-small")
```

---

## Error Handling

### General Pattern

```python
try:
    result = await operation()
except SpecificError as e:
    logger.exception("operation_failed", context="value", error=str(e))
    raise
```

### MongoDB Operations

```python
from pymongo.errors import ConnectionFailure, OperationFailure

try:
    results = await collection.aggregate(pipeline).to_list(length=limit)
except ConnectionFailure:
    logger.exception("mongodb_connection_failed")
    raise
except OperationFailure as e:
    if e.code == 291:  # Index not found
        logger.error("mongodb_index_missing", index="vector_index")
        raise ValueError("Vector search index not configured in Atlas")
    logger.exception("mongodb_operation_failed", code=e.code)
    raise
```

### API Calls (Embeddings, LLM)

```python
from openai import APIError, RateLimitError

try:
    result = await client.api_call(params)
except RateLimitError as e:
    logger.warning("api_rate_limited", retry_after=e.retry_after)
    await asyncio.sleep(e.retry_after or 5)
    # Retry logic here
except APIError as e:
    logger.exception("api_error", status_code=e.status_code)
    raise
```

### Document Processing

```python
try:
    result = converter.convert(file_path)
except Exception as e:
    logger.exception(
        "document_conversion_failed",
        file=file_path,
        format=os.path.splitext(file_path)[1]
    )
    # Continue processing other documents, don't crash pipeline
    return None
```

---

## Testing

**Tests mirror the examples directory structure:**

```
examples/agent.py        →  tests/test_agent.py
examples/tools.py        →  tests/test_tools.py
examples/ingestion/      →  tests/ingestion/
```

### Unit Tests

```python
import pytest
from examples.ingestion.chunker import DoclingHybridChunker, ChunkingConfig

@pytest.mark.unit
async def test_chunker_creates_valid_chunks():
    """Test that chunker creates properly formatted chunks."""
    config = ChunkingConfig(max_tokens=512)
    chunker = DoclingHybridChunker(config)

    content = "# Heading\n\nSome content here..."
    chunks = await chunker.chunk_document(
        content=content,
        title="Test Doc",
        source="test.md"
    )

    assert len(chunks) > 0
    assert all(chunk.token_count <= 512 for chunk in chunks)
    assert all(chunk.content for chunk in chunks)
```

### Integration Tests

```python
@pytest.mark.integration
async def test_mongodb_vector_search(mongo_client):
    """Test vector search against live MongoDB."""
    # Insert test data
    await mongo_client.chunks.insert_one({
        "content": "Test content",
        "embedding": [0.1] * 1536,
        "document_id": ObjectId()
    })

    # Perform search
    results = await semantic_search(
        ctx=test_context,
        query="test",
        match_count=5
    )

    assert len(results) > 0
```

**Run tests:**
```bash
uv run pytest tests/ -v

# Run specific markers
uv run pytest tests/ -m unit
uv run pytest tests/ -m integration
```

---

## Common Pitfalls

### 1. Embedding Format Confusion
```python
# ❌ WRONG - String formatting is for Postgres pgvector
embedding_str = '[' + ','.join(map(str, embedding)) + ']'

# ✅ CORRECT - Python list for MongoDB
embedding = [0.1, 0.2, 0.3, ...]
await collection.insert_one({"embedding": embedding})
```

### 2. Async/Await Mistakes
```python
# ❌ WRONG - Forgot await
result = collection.find_one({"_id": doc_id})

# ✅ CORRECT
result = await collection.find_one({"_id": doc_id})
```

### 3. Missing DoclingDocument for HybridChunker
```python
# ❌ WRONG - Passing raw text to HybridChunker
chunks = chunker.chunk(dl_doc=markdown_text)

# ✅ CORRECT - Pass DoclingDocument from converter
result = converter.convert(file_path)
chunks = chunker.chunk(dl_doc=result.document)
```

### 4. Creating Vector Indexes Programmatically
```python
# ❌ WRONG - Cannot create vector/search indexes via Motor
await collection.create_index([("embedding", "vector")])

# ✅ CORRECT - Must create in Atlas UI or via Atlas API
# See .claude/reference/mongodb-patterns.md for index setup
```

### 5. Missing $lookup for Document Metadata
```python
# ❌ WRONG - Search without document metadata
pipeline = [{"$vectorSearch": {...}}]

# ✅ CORRECT - Join with documents collection
pipeline = [
    {"$vectorSearch": {...}},
    {"$lookup": {
        "from": "documents",
        "localField": "document_id",
        "foreignField": "_id",
        "as": "document_info"
    }},
    {"$unwind": "$document_info"}
]
```

### 6. MongoDB Atlas TLSV1_ALERT_INTERNAL_ERROR
```python
# This error on port 27017 means your IP is NOT whitelisted in Atlas
# It is NOT an SSL version issue
# Fix: Atlas UI → Network Access → IP Access List → Add IP address
# Confirm IP: curl ifconfig.me
```

### 7. FastAPI Route Ordering (Static before Parameterized)
```python
# ❌ WRONG - FastAPI treats "seed-default" as a workflow_id value
router.get("/{workflow_id}")
router.post("/seed-default")

# ✅ CORRECT - Register static paths before parameterized paths
router.post("/seed-default")
router.get("/{workflow_id}")
```

### 8. Variable Shadowing in Lifespan Functions
```python
# ❌ WRONG - shadows the imported 'settings' module/function
async def lifespan(app):
    settings = load_settings()

# ✅ CORRECT - use a distinct name
async def lifespan(app):
    settings_obj = load_settings()
```

### 9. ruff E402 in main.py (intentional, suppress)
```python
# setup_logging() MUST be called before other imports — suppress E402 explicitly
from src.api.logging_config import setup_logging
setup_logging()
from src.api.routes import ...  # noqa: E402
```

### 10. pytest-asyncio Mode
```bash
# Async tests require explicit marker OR auto mode:
uv run pytest tests/ --asyncio-mode=auto  # recommended
# OR add @pytest.mark.asyncio to every async test function
```

### 11. pytest-asyncio Fixture Scoping in E2E Tests
```python
# ❌ WRONG - session-scoped async fixture causes "Event loop is closed" teardown errors
@pytest_asyncio.fixture(scope="session")
async def api_client(): ...

# ❌ WRONG - asyncio_default_fixture_loop_scope="session" in pyproject.toml silently
#   treats each test FILE as a separate pytest session → breaks cross-file shared state
#   (e2e_state dict appears empty in later test files)

# ✅ CORRECT - function-scoped async fixture + session-scoped SYNC fixture for shared state
@pytest_asyncio.fixture(scope="function")
async def api_client() -> httpx.AsyncClient:
    async with httpx.AsyncClient(...) as client:
        yield client

@pytest.fixture(scope="session")  # sync, not async
def e2e_state() -> dict:
    return {"qa_pair_ids": []}
```

---

## Quick Reference

**MongoDB Operations:**
```python
# Insert document
doc_id = await db.documents.insert_one(doc_dict).inserted_id

# Insert many chunks
await db.chunks.insert_many(chunk_dicts)

# Vector search with aggregation
results = await db.chunks.aggregate(pipeline).to_list(length=limit)

# Find by ID
doc = await db.documents.find_one({"_id": ObjectId(doc_id)})
```

**Embedding Generation:**
```python
# Single
embedding = await client.embeddings.create(model=model, input=text)

# Batch (ALWAYS prefer batching)
embeddings = await client.embeddings.create(model=model, input=texts)
```

**Docling Conversion:**
```python
# Convert any supported format
result = converter.convert(file_path)
markdown = result.document.export_to_markdown()
docling_doc = result.document  # Keep for HybridChunker

# Chunk with context preservation
chunks = list(chunker.chunk(dl_doc=docling_doc))
```

**Pydantic AI Agent:**
```python
# Define agent with StateDeps
agent = Agent(model, deps_type=StateDeps[State], system_prompt=prompt)

# Add tool
@agent.tool
async def tool_func(ctx: RunContext[StateDeps[State]], arg: str) -> str:
    """Tool description."""
    pass

# Run with streaming
async with agent.iter(input, deps=deps, message_history=history) as run:
    async for node in run:
        # Handle nodes (see .claude/reference/agent-tools.md)
        pass
```

---

## Implementation-Specific References

For detailed implementation patterns, see:

- **MongoDB patterns**: `.claude/reference/mongodb-patterns.md`
  - Collection design (two-collection pattern)
  - Aggregation pipelines ($vectorSearch, $rankFusion)
  - Connection management, index setup

- **Docling ingestion**: `.claude/reference/docling-ingestion.md`
  - Document conversion for all formats
  - HybridChunker usage and configuration
  - Audio transcription with Whisper ASR

- **Agent & tools**: `.claude/reference/agent-tools.md`
  - Pydantic AI agent patterns
  - Tool definitions and best practices
  - Streaming implementation details

These references are loaded on-demand when working on specific features.
