@prd.md @activity.md

We are building a MongoDB RAG Agent project - a Q&A system with document ingestion, vector search, and an AI agent for answering questions.

First read activity.md to see what was recently accomplished.

## Start the Application

This project has two components that need to run simultaneously:

### Backend (FastAPI + Python)
```bash
./start_backend.sh
# Or manually:
uv run uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```
- API available at: http://localhost:8000
- API docs at: http://localhost:8000/docs

### Frontend (React + Vite + TypeScript)
```bash
./start_frontend.sh
# Or manually:
cd frontend && npm run dev
```
- UI available at: http://localhost:5173

If ports are taken, check for existing processes or use alternative ports.

## Work on Tasks

Open prd.md and find the single highest priority task where `"passes": false`.

Work on exactly ONE task:
1. Implement the change according to the task steps
2. Run available checks:
   - **Backend**: `uv run pytest` (if tests exist)
   - **Frontend**: `cd frontend && npm run lint && npm run build`

## Verify in Browser

After implementing, use agent-browser to verify your work:

1. Open the local server URL:
   ```
   agent-browser open http://localhost:5173
   ```

2. Take a snapshot to see the page structure:
   ```
   agent-browser snapshot -i -c
   ```

3. Take a screenshot for visual verification:
   ```
   agent-browser screenshot screenshots/[task-name].png
   ```

4. Check for any console errors or layout issues

5. If the task involves interactive elements, test them:
   ```
   agent-browser click "[selector]"
   agent-browser fill "[selector]" "test value"
   ```

## Log Progress

Append a dated progress entry to activity.md describing:
- What you changed
- What commands you ran
- The screenshot filename
- Any issues encountered and how you resolved them

## Update Task Status

When the task is confirmed working, update that task's `"passes"` field in prd.md from `false` to `true`.

## Commit Changes

Make one git commit for that task only with a clear, descriptive message:
```
git add .
git commit -m "feat: [brief description of what was implemented]"
```

Do NOT run `git init`, do NOT change git remotes, and do NOT push.

## Important Rules

- ONLY work on a SINGLE task per iteration
- Always verify in browser before marking a task as passing
- Always log your progress in activity.md
- Always commit after completing a task

## Completion

When ALL tasks have `"passes": true`, output:

<promise>COMPLETE</promise>
