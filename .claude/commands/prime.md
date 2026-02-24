---
allowed-tools: Read, Glob, Bash
description: Prime agent with codebase context
---

## Architecture Overview

MongoDB RAG Agent is a Python agentic RAG system combining MongoDB Atlas Vector Search with Pydantic AI for intelligent document retrieval:

- **Agent** — Pydantic AI agent with `StateDeps` pattern, semantic and hybrid search tools via `$rankFusion`
- **Ingestion** — Docling multi-format pipeline (PDF, DOCX, audio) → HybridChunker → batch embeddings → MongoDB
- **Config** — Pydantic Settings reading from `.env`; supports any OpenAI-compatible LLM/embedding provider
- **Frontend** — React 18 + Vite + TypeScript dashboard in `frontend/` (separate from Python backend)

---

Read these files to understand the codebase before starting work:

1. `CLAUDE.md` - Project conventions, patterns, and common pitfalls (MongoDB vs pgvector, async rules)
2. `pyproject.toml` - Python dependencies, test markers, and dev tools (ruff, mypy, pytest)
3. `examples/settings.py` - Pydantic Settings for all environment variable configuration
4. `examples/agent.py` - Pydantic AI `rag_agent` with `StateDeps[RAGState]` and tool/instruction definitions
5. `examples/dependencies.py` - `AgentDependencies` dataclass: DB pool, OpenAI client, embedding helper
6. `examples/providers.py` - `get_llm_model()` and `get_embedding_model()` factory functions
7. `examples/tools.py` - `semantic_search` and `hybrid_search` tool implementations with `SearchResult` model
8. `examples/prompts.py` - `MAIN_SYSTEM_PROMPT` for the RAG agent
9. `examples/cli.py` - Rich-based conversational CLI entry point (`uv run python -m examples.cli`)
10. `examples/ingestion/ingest.py` - Multi-format document ingestion pipeline entry point
11. `examples/ingestion/chunker.py` - Docling `HybridChunker` wrapper with `ChunkingConfig`
12. `examples/ingestion/embedder.py` - Batch embedding generation helper
13. `tests/test_models.py` - Existing test patterns and fixtures

Then run:
```bash
uv run python -m examples.cli
```

Confirm the agent starts without errors before proceeding.
