#!/bin/bash
# Start the backend API server

echo "🚀 Starting MongoDB RAG Q&A Backend API..."
echo "📍 Server will be available at: http://localhost:8000"
echo "📚 API docs available at: http://localhost:8000/docs"
echo ""

cd "$(dirname "$0")"
uv run uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

