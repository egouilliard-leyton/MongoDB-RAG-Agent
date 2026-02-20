# Quick Start Guide - Frontend UI Testing

This guide will help you get both the backend API and frontend UI running for testing.

## Prerequisites

- Python 3.11+ with `uv` installed
- Node.js 18+ and npm
- MongoDB Atlas connection configured in `.env`
- Documents already ingested (verified with `scripts/verify_ingestion.py`)

## Step 1: Start the Backend API Server

Open a terminal and run:

```bash
cd /Users/edouardgouilliard/Documents/Leyton/CAES/MongoDB-RAG-Agent
uv run uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

The backend will start on `http://localhost:8000`

You should see:
- ✅ Application started, background tasks initialized
- ✅ Server running on http://0.0.0.0:8000

**Verify backend is running:**
- Open `http://localhost:8000/health` in your browser
- You should see a JSON response with status "healthy"
- Check `http://localhost:8000/docs` for Swagger UI

## Step 2: Start the Frontend Development Server

Open a **new terminal** and run:

```bash
cd /Users/edouardgouilliard/Documents/Leyton/CAES/MongoDB-RAG-Agent/frontend
npm install --legacy-peer-deps
npm run dev
```

The frontend will start on `http://localhost:5173`

You should see:
- ✅ VITE server running
- ✅ Local: http://localhost:5173

## Step 3: Test the Frontend UI

1. **Open your browser** and navigate to `http://localhost:5173`

2. **Create a Session:**
   - Click "New Session" or "Create Session"
   - Enter a session name (e.g., "Test Session")
   - Select user role: "Junior" or "Senior"
   - Optionally add company information
   - Click "Create"

3. **Process Questions:**
   - Enter one or more questions in the question input area
   - Click "Generate Answers" or "Process Questions"
   - Wait for answers to be generated (with citations)

4. **Test Features:**
   - **Junior User**: Answers are read-only, Q&A pairs are NOT saved to database
   - **Senior User**: Answers are editable, Q&A pairs ARE saved to database
   - Edit answers (senior users only)
   - View citations
   - Mark outcome status
   - Export session (markdown, PDF, Word)

## Troubleshooting

### Backend Issues

**Port 8000 already in use:**
```bash
# Find and kill the process
lsof -ti:8000 | xargs kill -9
# Or use a different port
uv run uvicorn src.api.main:app --reload --port 8001
```

**MongoDB connection errors:**
- Check `.env` file has correct `MONGODB_URI`
- Verify MongoDB Atlas connection is working
- Run `uv run python scripts/verify_ingestion.py` to check database status

**No documents found:**
- Run ingestion: `uv run python -m src.ingestion.ingest -d ./documents`
- Verify with: `uv run python scripts/verify_ingestion.py`

### Frontend Issues

**npm install fails:**
```bash
# Use legacy peer deps flag
npm install --legacy-peer-deps
```

**CORS errors:**
- Backend CORS is already configured to allow `*` origins
- Make sure backend is running on port 8000

**API connection errors:**
- Verify backend is running: `curl http://localhost:8000/health`
- Check browser console for detailed error messages
- Verify `VITE_API_BASE_URL` in frontend `.env.local` (if exists)

**Port 5173 already in use:**
```bash
# Find and kill the process
lsof -ti:5173 | xargs kill -9
# Or Vite will automatically use next available port
```

## Testing Checklist

- [ ] Backend API starts without errors
- [ ] Health endpoint returns "healthy" status
- [ ] Frontend loads without errors
- [ ] Can create a new session
- [ ] Can process questions and get answers
- [ ] Citations are displayed
- [ ] Junior user: Q&A pairs NOT saved (check database)
- [ ] Senior user: Q&A pairs ARE saved (check database)
- [ ] Can edit answers (senior users only)
- [ ] Can mark outcome status
- [ ] Can export session (all formats)

## API Endpoints Available

- `GET /health` - Health check with dependency status
- `GET /docs` - Swagger UI documentation
- `POST /api/sessions` - Create session
- `GET /api/sessions` - List sessions
- `GET /api/sessions/{id}` - Get session
- `POST /api/sessions/{id}/questions` - Process questions
- `GET /api/sessions/{id}/qa-pairs` - Get Q&A pairs
- `PUT /api/qa-pairs/{id}` - Update answer
- `PUT /api/sessions/{id}/outcome` - Mark outcome
- `POST /api/sessions/{id}/export` - Export session
- `POST /api/sessions/{id}/follow-up` - Create follow-up session

## Next Steps

Once everything is working:
1. Test all user workflows (junior and senior)
2. Test follow-up session creation
3. Test export functionality
4. Test Q&A history search (requires vector index on qa_pairs.question_embedding)


