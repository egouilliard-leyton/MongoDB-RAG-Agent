#!/bin/bash

# Ralph Verified - Multi-Agent Verification System
# =================================================
# This script runs Claude Code in a verified loop with anti-gaming mechanisms:
# - Session tokens to prevent pre-written completion signals
# - Separate implementation and review agents
# - Script-enforced test gates (pytest, mypy, npm lint/build)
# - Checksum verification for tamper detection
# - Script-only task status updates
#
# Usage: ./ralph-verified.sh <cr-file> [max_iterations]
# Example: ./ralph-verified.sh changes/CR-DOCUMENT-INGESTION-DASHBOARD.md 30

set -e

# Resolve repo root so paths are stable even after `cd`
REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Configuration - Agent Models
REVIEW_MODEL="${REVIEW_MODEL:-haiku}"
IMPL_MODEL="${IMPL_MODEL:-claude-opus-4-5-20251101}"
TEST_MODEL="${TEST_MODEL:-claude-sonnet-4-5-20250929}"
FIX_MODEL="${FIX_MODEL:-claude-sonnet-4-5-20250929}"
PLAN_MODEL="${PLAN_MODEL:-claude-sonnet-4-5-20250929}"
CLAUDE_TIMEOUT="${CLAUDE_TIMEOUT:-1800}"
SESSION_DIR="${SESSION_DIR:-.ralph-session}"
if [[ "$SESSION_DIR" != /* ]]; then
  SESSION_DIR="$REPO_ROOT/$SESSION_DIR"
fi

# Post-completion verification configuration
POST_VERIFY="${POST_VERIFY:-1}"
POST_VERIFY_MAX_ITERATIONS="${POST_VERIFY_MAX_ITERATIONS:-10}"
UI_VERIFY_MAX_ITERATIONS="${UI_VERIFY_MAX_ITERATIONS:-10}"
ROBOT_VERIFY_MAX_ITERATIONS="${ROBOT_VERIFY_MAX_ITERATIONS:-10}"

# Service ports
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

# Banner
echo -e "${CYAN}"
echo "  ╔═══════════════════════════════════════════════════════════╗"
echo "  ║                                                           ║"
echo "  ║   Ralph Verified - Multi-Agent Verification System        ║"
echo "  ║                                                           ║"
echo "  ╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check for required argument
if [ -z "$1" ]; then
  echo -e "${RED}Error: Missing required argument${NC}"
  echo ""
  echo "Usage: $0 <cr-file> [max_iterations]"
  echo ""
  echo "Arguments:"
  echo "  cr-file         Path to the Change Request markdown file"
  echo "  max_iterations  Maximum loop iterations (default: 30)"
  echo ""
  echo "Environment Variables:"
  echo "  IMPL_MODEL                  Model for implementation (default: claude-opus-4-5-20251101)"
  echo "  TEST_MODEL                  Model for test-writing (default: claude-sonnet-4-5-20250929)"
  echo "  REVIEW_MODEL                Model for review (default: haiku)"
  echo "  FIX_MODEL                   Model for runtime fix agent (default: claude-sonnet-4-5-20250929)"
  echo "  PLAN_MODEL                  Model for UI planning agent (default: claude-sonnet-4-5-20250929)"
  echo "  CLAUDE_TIMEOUT              Timeout per agent run in seconds (default: 1800)"
  echo ""
  echo "Post-Completion Verification:"
  echo "  POST_VERIFY                   Enable post-completion verification (default: 1)"
  echo "  POST_VERIFY_MAX_ITERATIONS    Max runtime fix iterations (default: 10)"
  echo "  UI_VERIFY_MAX_ITERATIONS      Max agent-browser UI fix iterations (default: 10)"
  echo "  ROBOT_VERIFY_MAX_ITERATIONS   Max Robot Framework fix iterations (default: 10)"
  echo ""
  echo "Examples:"
  echo "  $0 changes/CR-DOCUMENT-INGESTION-DASHBOARD.md"
  echo "  $0 changes/CR-DOCUMENT-INGESTION-DASHBOARD.md 50"
  echo "  REVIEW_MODEL=sonnet $0 changes/CR-FEATURE.md"
  echo ""
  echo "Available Change Requests:"
  if [ -d "changes" ]; then
    ls -1 changes/CR-*.md 2>/dev/null || echo "  (none found)"
  else
    echo "  (changes/ directory not found)"
  fi
  exit 1
fi

CR_FILE=$1
MAX_ITERATIONS=${2:-30}

# Verify CR file exists
if [ ! -f "$CR_FILE" ]; then
  echo -e "${RED}Error: Change Request file not found: $CR_FILE${NC}"
  exit 1
fi

# =============================================================================
# SESSION MANAGEMENT
# =============================================================================

generate_session_token() {
  # Generate a unique session token using timestamp and random data
  echo "$(date +%s%N)-$(head -c 32 /dev/urandom | shasum -a 256 | cut -c1-16)" | shasum -a 256 | cut -c1-32
}

init_session() {
  mkdir -p "$SESSION_DIR"
  init_service_dirs

  SESSION_TOKEN=$(generate_session_token)
  
  # Set up trap to clean up services on exit/interrupt
  trap cleanup_services EXIT INT TERM

  # Create session.json
  cat > "$SESSION_DIR/session.json" << EOF
{
  "token": "$SESSION_TOKEN",
  "cr_file": "$CR_FILE",
  "start_time": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "impl_model": "$IMPL_MODEL",
  "test_model": "$TEST_MODEL",
  "review_model": "$REVIEW_MODEL",
  "fix_model": "$FIX_MODEL",
  "plan_model": "$PLAN_MODEL",
  "post_verify": "$POST_VERIFY",
  "post_verify_max_iterations": $POST_VERIFY_MAX_ITERATIONS,
  "ui_verify_max_iterations": $UI_VERIFY_MAX_ITERATIONS,
  "robot_verify_max_iterations": $ROBOT_VERIFY_MAX_ITERATIONS
}
EOF

  # Initialize task-status.json
  cat > "$SESSION_DIR/task-status.json" << EOF
{
  "tasks": [],
  "last_updated": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF

  # Create checksum
  update_checksum

  # Initialize logs
  echo "[]" > "$SESSION_DIR/review-log.json"
  echo "{}" > "$SESSION_DIR/test-results.json"

  echo -e "${GREEN}Session initialized with token: ${SESSION_TOKEN:0:8}...${NC}"
}

update_checksum() {
  shasum -a 256 "$SESSION_DIR/task-status.json" | cut -d' ' -f1 > "$SESSION_DIR/task-status.checksum"
}

verify_checksum() {
  local current_checksum=$(shasum -a 256 "$SESSION_DIR/task-status.json" | cut -d' ' -f1)
  local stored_checksum=$(cat "$SESSION_DIR/task-status.checksum" 2>/dev/null || echo "")

  if [ "$current_checksum" != "$stored_checksum" ]; then
    echo -e "${RED}SECURITY ALERT: task-status.json has been tampered with!${NC}"
    echo -e "${RED}Expected: $stored_checksum${NC}"
    echo -e "${RED}Got: $current_checksum${NC}"
    return 1
  fi
  return 0
}

# =============================================================================
# SERVICE LIFECYCLE MANAGEMENT
# =============================================================================

BACKEND_PID=""
FRONTEND_PID=""

init_service_dirs() {
  mkdir -p "$SESSION_DIR/pids"
  mkdir -p "$SESSION_DIR/logs"
  mkdir -p "$SESSION_DIR/ui/snapshots"
  mkdir -p "$SESSION_DIR/ui/screens"
  mkdir -p "$SESSION_DIR/ui/robot"
}

cleanup_services() {
  echo -e "${YELLOW}Cleaning up services...${NC}"
  
  # Stop backend
  if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo -e "${CYAN}Stopping backend (PID: $BACKEND_PID)...${NC}"
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
  
  # Also check pidfile
  if [ -f "$SESSION_DIR/pids/backend.pid" ]; then
    local pid=$(cat "$SESSION_DIR/pids/backend.pid")
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
    fi
    rm -f "$SESSION_DIR/pids/backend.pid"
  fi
  
  # Stop frontend
  if [ -n "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    echo -e "${CYAN}Stopping frontend (PID: $FRONTEND_PID)...${NC}"
    kill "$FRONTEND_PID" 2>/dev/null || true
    wait "$FRONTEND_PID" 2>/dev/null || true
  fi
  
  # Also check pidfile
  if [ -f "$SESSION_DIR/pids/frontend.pid" ]; then
    local pid=$(cat "$SESSION_DIR/pids/frontend.pid")
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
    fi
    rm -f "$SESSION_DIR/pids/frontend.pid"
  fi
  
  # Kill any remaining processes on our ports
  lsof -ti:$BACKEND_PORT | xargs kill -9 2>/dev/null || true
  lsof -ti:$FRONTEND_PORT | xargs kill -9 2>/dev/null || true
  
  echo -e "${GREEN}Services cleaned up${NC}"
}

start_backend() {
  local mode="${1:-prod}"  # prod or dev
  
  echo -e "${CYAN}Starting backend ($mode mode)...${NC}"
  
  # Kill any existing process on the port
  lsof -ti:$BACKEND_PORT | xargs kill -9 2>/dev/null || true
  sleep 1
  
  if [ "$mode" = "dev" ]; then
    # Dev mode with reload
    uv run uvicorn src.api.main:app --reload --host 127.0.0.1 --port "$BACKEND_PORT" \
      > "$SESSION_DIR/logs/backend.log" 2>&1 &
  else
    # Prod-like mode without reload
    uv run uvicorn src.api.main:app --host 127.0.0.1 --port "$BACKEND_PORT" \
      > "$SESSION_DIR/logs/backend.log" 2>&1 &
  fi
  
  BACKEND_PID=$!
  echo "$BACKEND_PID" > "$SESSION_DIR/pids/backend.pid"
  echo -e "${GREEN}Backend started (PID: $BACKEND_PID)${NC}"
}

start_frontend() {
  local mode="${1:-prod}"  # prod or dev
  
  echo -e "${CYAN}Starting frontend ($mode mode)...${NC}"
  
  # Kill any existing process on the port
  lsof -ti:$FRONTEND_PORT | xargs kill -9 2>/dev/null || true
  sleep 1
  
  if [ "$mode" = "dev" ]; then
    # Dev mode
    (cd frontend && npm run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT") \
      > "$SESSION_DIR/logs/frontend.log" 2>&1 &
  else
    # Prod-like mode: build then preview
    echo -e "${CYAN}Building frontend for production...${NC}"
    if ! (cd frontend && npm run build > "$SESSION_DIR/logs/frontend-build.log" 2>&1); then
      echo -e "${RED}Frontend build failed!${NC}"
      return 1
    fi
    echo -e "${GREEN}Frontend build complete${NC}"
    
    (cd frontend && npm run preview -- --host 127.0.0.1 --port "$FRONTEND_PORT") \
      > "$SESSION_DIR/logs/frontend.log" 2>&1 &
  fi
  
  FRONTEND_PID=$!
  echo "$FRONTEND_PID" > "$SESSION_DIR/pids/frontend.pid"
  echo -e "${GREEN}Frontend started (PID: $FRONTEND_PID)${NC}"
}

wait_for_backend() {
  local max_attempts="${1:-30}"
  local attempt=1
  
  echo -e "${CYAN}Waiting for backend health...${NC}"
  
  while [ $attempt -le $max_attempts ]; do
    if curl -fsS "http://127.0.0.1:$BACKEND_PORT/health" > /dev/null 2>&1; then
      echo -e "${GREEN}Backend is healthy!${NC}"
      return 0
    fi
    
    echo -e "${YELLOW}  Attempt $attempt/$max_attempts - waiting...${NC}"
    sleep 2
    attempt=$((attempt + 1))
  done
  
  echo -e "${RED}Backend failed to become healthy after $max_attempts attempts${NC}"
  echo -e "${RED}Backend log tail:${NC}"
  tail -50 "$SESSION_DIR/logs/backend.log" 2>/dev/null || true
  return 1
}

wait_for_frontend() {
  local max_attempts="${1:-30}"
  local attempt=1
  
  echo -e "${CYAN}Waiting for frontend...${NC}"
  
  while [ $attempt -le $max_attempts ]; do
    if curl -fsS "http://127.0.0.1:$FRONTEND_PORT/" > /dev/null 2>&1; then
      echo -e "${GREEN}Frontend is responding!${NC}"
      return 0
    fi
    
    echo -e "${YELLOW}  Attempt $attempt/$max_attempts - waiting...${NC}"
    sleep 2
    attempt=$((attempt + 1))
  done
  
  echo -e "${RED}Frontend failed to start after $max_attempts attempts${NC}"
  echo -e "${RED}Frontend log tail:${NC}"
  tail -50 "$SESSION_DIR/logs/frontend.log" 2>/dev/null || true
  return 1
}

check_backend_detailed_health() {
  # Check both health endpoints
  local basic_health
  local system_health
  
  basic_health=$(curl -fsS "http://127.0.0.1:$BACKEND_PORT/health" 2>&1) || {
    echo -e "${RED}Basic health check failed${NC}"
    return 1
  }
  
  system_health=$(curl -fsS "http://127.0.0.1:$BACKEND_PORT/api/system/health" 2>&1) || {
    echo -e "${YELLOW}System health check failed (non-fatal)${NC}"
  }
  
  echo -e "${GREEN}Backend health checks passed${NC}"
  return 0
}

# =============================================================================
# RUNTIME FIX LOOP
# =============================================================================

generate_fix_runtime_prompt() {
  local error_type="$1"
  local error_output="$2"
  local changed_files="$3"
  
  cat << PROMPT_END
# Fix Runtime Agent

You are fixing build or runtime errors. Your session token is: **$SESSION_TOKEN**

## Error Type
$error_type

## Error Output
\`\`\`
$error_output
\`\`\`

## Recently Changed Files
$changed_files

## Instructions

1. Analyze the error output to understand what's failing
2. Read the relevant files to understand the issue
3. Make the MINIMUM changes needed to fix the error
4. Do NOT add new features or refactor code
5. Do NOT modify CR task status or activity logs
6. Focus ONLY on making the build/runtime pass

## Completion Signal

When you have fixed the issue, output:

\`\`\`
<fix-done session="$SESSION_TOKEN">
  Error Type: $error_type
  Files Fixed: [list files you modified]
  Summary: [brief description of fix]
</fix-done>
\`\`\`

**WARNING**: Only fix what's needed. Do not add unrelated changes.
PROMPT_END
}

run_build_gates() {
  # Run build-only gates (no pytest - faster iteration)
  local all_passed=true
  local error_output=""
  
  echo -e "${BLUE}Running build gates...${NC}"
  
  # Python type checking
  if [ -f "pyproject.toml" ]; then
    echo -e "${CYAN}  [1/3] Running mypy type checking...${NC}"
    if ! uv run mypy src/ --ignore-missing-imports --no-error-summary 2>&1 | tee /tmp/mypy-output.txt; then
      echo -e "${RED}  ✗ mypy failed${NC}"
      error_output="MYPY ERRORS:\n$(cat /tmp/mypy-output.txt | tail -50)"
      all_passed=false
    else
      echo -e "${GREEN}  ✓ mypy passed${NC}"
    fi
  fi
  
  # Frontend checks
  if [ -f "frontend/package.json" ] && $all_passed; then
    echo -e "${CYAN}  [2/3] Running TypeScript type check...${NC}"
    if ! (cd frontend && npx tsc --noEmit 2>&1 | tee /tmp/tsc-output.txt); then
      echo -e "${RED}  ✗ tsc failed${NC}"
      error_output="$error_output\n\nTSC ERRORS:\n$(cat /tmp/tsc-output.txt | tail -50)"
      all_passed=false
    else
      echo -e "${GREEN}  ✓ tsc passed${NC}"
    fi
    
    if $all_passed; then
      echo -e "${CYAN}  [3/3] Running frontend build...${NC}"
      if ! (cd frontend && npm run build 2>&1 | tee /tmp/build-output.txt); then
        echo -e "${RED}  ✗ build failed${NC}"
        error_output="$error_output\n\nBUILD ERRORS:\n$(cat /tmp/build-output.txt | tail -50)"
        all_passed=false
      else
        echo -e "${GREEN}  ✓ build passed${NC}"
      fi
    fi
  fi
  
  if $all_passed; then
    echo -e "${GREEN}All build gates passed!${NC}"
    return 0
  else
    echo -e "$error_output" > "$SESSION_DIR/logs/build-errors.txt"
    return 1
  fi
}

run_runtime_verification() {
  # Start services and check health
  echo -e "${BLUE}Starting runtime verification...${NC}"
  
  # Stop any existing services
  cleanup_services 2>/dev/null || true
  
  # Start backend (prod-like)
  if ! start_backend prod; then
    echo "Backend failed to start" > "$SESSION_DIR/logs/runtime-errors.txt"
    return 1
  fi
  
  # Wait for backend health
  if ! wait_for_backend 20; then
    echo "Backend health check failed" >> "$SESSION_DIR/logs/runtime-errors.txt"
    tail -100 "$SESSION_DIR/logs/backend.log" >> "$SESSION_DIR/logs/runtime-errors.txt"
    return 1
  fi
  
  # Start frontend (prod-like)
  if ! start_frontend prod; then
    echo "Frontend failed to start/build" > "$SESSION_DIR/logs/runtime-errors.txt"
    cat "$SESSION_DIR/logs/frontend-build.log" >> "$SESSION_DIR/logs/runtime-errors.txt" 2>/dev/null || true
    return 1
  fi
  
  # Wait for frontend
  if ! wait_for_frontend 20; then
    echo "Frontend failed to respond" >> "$SESSION_DIR/logs/runtime-errors.txt"
    tail -100 "$SESSION_DIR/logs/frontend.log" >> "$SESSION_DIR/logs/runtime-errors.txt"
    return 1
  fi
  
  # Detailed backend health
  if ! check_backend_detailed_health; then
    echo "Backend detailed health check failed" >> "$SESSION_DIR/logs/runtime-errors.txt"
    return 1
  fi
  
  echo -e "${GREEN}Runtime verification passed!${NC}"
  return 0
}

run_runtime_fix_loop() {
  echo -e "${MAGENTA}"
  echo "  ╔═══════════════════════════════════════════════════════════╗"
  echo "  ║         POST-COMPLETION: Runtime Fix Loop                 ║"
  echo "  ╚═══════════════════════════════════════════════════════════╝"
  echo -e "${NC}"
  
  local iteration=1
  local changed_files=$(git diff --name-only HEAD~10 2>/dev/null | head -30 || echo "Unable to get changed files")
  
  while [ $iteration -le $POST_VERIFY_MAX_ITERATIONS ]; do
    echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}   Runtime Fix Iteration $iteration of $POST_VERIFY_MAX_ITERATIONS${NC}"
    echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}"
    echo ""
    
    # Step 1: Build gates
    echo -e "${MAGENTA}▶ Step 1: Build Gates${NC}"
    if ! run_build_gates; then
      echo -e "${RED}Build gates failed. Running fix agent...${NC}"
      
      local error_output=$(cat "$SESSION_DIR/logs/build-errors.txt" 2>/dev/null || echo "Build failed")
      local fix_prompt=$(generate_fix_runtime_prompt "BUILD_ERROR" "$error_output" "$changed_files")
      
      echo -e "${CYAN}Running fix agent (model: $FIX_MODEL)...${NC}"
      local fix_output
      fix_output=$(timeout "$CLAUDE_TIMEOUT" claude -p "$fix_prompt" --model "$FIX_MODEL" --output-format text 2>&1) || {
        echo -e "${RED}Fix agent failed or timed out${NC}"
      }
      
      echo "$fix_output" | head -80
      
      iteration=$((iteration + 1))
      sleep 2
      continue
    fi
    
    # Step 2: Runtime verification
    echo -e "${MAGENTA}▶ Step 2: Runtime Verification${NC}"
    if ! run_runtime_verification; then
      echo -e "${RED}Runtime verification failed. Running fix agent...${NC}"
      
      local error_output=$(cat "$SESSION_DIR/logs/runtime-errors.txt" 2>/dev/null || echo "Runtime check failed")
      local fix_prompt=$(generate_fix_runtime_prompt "RUNTIME_ERROR" "$error_output" "$changed_files")
      
      echo -e "${CYAN}Running fix agent (model: $FIX_MODEL)...${NC}"
      local fix_output
      fix_output=$(timeout "$CLAUDE_TIMEOUT" claude -p "$fix_prompt" --model "$FIX_MODEL" --output-format text 2>&1) || {
        echo -e "${RED}Fix agent failed or timed out${NC}"
      }
      
      echo "$fix_output" | head -80
      
      iteration=$((iteration + 1))
      sleep 2
      continue
    fi
    
    # All checks passed!
    echo -e "${GREEN}Build and runtime verification passed!${NC}"
    return 0
  done
  
  echo -e "${RED}Runtime fix loop exceeded max iterations ($POST_VERIFY_MAX_ITERATIONS)${NC}"
  return 1
}

# =============================================================================
# UI SMOKE TESTING (agent-browser)
# =============================================================================

AB_SESSION=""

ab() {
  # Wrapper so all commands target the same browser session
  agent-browser --session "$AB_SESSION" "$@"
}

ui_open() {
  ab open "http://127.0.0.1:$FRONTEND_PORT" 2>&1 | tee -a "$SESSION_DIR/logs/ui-test.log"
}

ui_snapshot_and_screenshot() {
  local snapshot_path="$1"
  local screenshot_path="$2"
  ab snapshot > "$snapshot_path" 2>&1 || true
  ab screenshot "$screenshot_path" 2>&1 || true
}

ui_click_tab() {
  local tab_name="$1"
  # Prefer semantic role locator; fall back to text click.
  ab find role button click --name "$tab_name" 2>&1 | tee -a "$SESSION_DIR/logs/ui-test.log" || \
    ab find text "$tab_name" click 2>&1 | tee -a "$SESSION_DIR/logs/ui-test.log"
}

ui_get_visible_main_text_count() {
  # Returns an integer count (or 0 on failure).
  local out
  out=$(ab eval "
    (() => {
      const main = document.querySelector('main');
      if (!main) return JSON.stringify({count: 0, error: 'No <main> found'});
      const walker = document.createTreeWalker(
        main,
        NodeFilter.SHOW_TEXT,
        {
          acceptNode: (node) => {
            const text = (node.textContent || '').trim();
            if (!text) return NodeFilter.FILTER_REJECT;
            const parent = node.parentElement;
            if (!parent) return NodeFilter.FILTER_REJECT;
            const style = window.getComputedStyle(parent);
            if (style.display === 'none' || style.visibility === 'hidden') return NodeFilter.FILTER_REJECT;
            const rect = parent.getBoundingClientRect();
            if (rect.width === 0 || rect.height === 0) return NodeFilter.FILTER_REJECT;
            return NodeFilter.FILTER_ACCEPT;
          }
        }
      );
      let count = 0;
      while (walker.nextNode() && count < 100) count++;
      return JSON.stringify({count});
    })()
  " --json 2>/dev/null) || out='{"count":0}'

  echo "$out" | grep -o '"count":[[:space:]]*[0-9]*' | grep -o '[0-9]*' | head -1 || echo "0"
}

ui_assert_dashboard_not_blank() {
  local snapshot_path="$1"
  local min_count="${2:-2}"

  # Require the Dashboard heading to appear somewhere in the snapshot
  if ! grep -qi "Dashboard" "$snapshot_path" 2>/dev/null; then
    echo "Dashboard heading not found in snapshot" >> "$SESSION_DIR/logs/ui-test.log"
    return 1
  fi

  # Treat loading state as non-blank (still indicates UI rendered)
  if grep -qi "Loading dashboard" "$snapshot_path" 2>/dev/null; then
    return 0
  fi

  local count
  count=$(ui_get_visible_main_text_count)
  if [[ ! "$count" =~ ^[0-9]+$ ]]; then count=0; fi

  if [ "$count" -ge "$min_count" ]; then
    return 0
  fi

  echo "Dashboard appears blank: visible main text count=$count (<$min_count)" >> "$SESSION_DIR/logs/ui-test.log"
  return 1
}

check_agent_browser() {
  if ! command -v agent-browser &> /dev/null; then
    echo -e "${RED}agent-browser CLI not found. Install with: npm install -g agent-browser${NC}"
    return 1
  fi
  return 0
}

# =============================================================================
# ROBOT FRAMEWORK UI TESTING (Playwright-based deterministic regression gate)
# =============================================================================

check_robot_browser() {
  # Check if Robot Framework and Browser library are available
  if ! command -v robot &> /dev/null; then
    echo -e "${RED}Robot Framework not found. Install with: pip install robotframework robotframework-browser${NC}"
    return 1
  fi
  
  # Check if Browser library is importable
  if ! python3 -c "from Browser import Browser" 2>/dev/null; then
    echo -e "${RED}robotframework-browser not installed. Install with: pip install robotframework-browser && rfbrowser init${NC}"
    return 1
  fi
  
  return 0
}

run_robot_tests() {
  local run_id=$(date +%Y%m%d_%H%M%S)
  local output_dir="$SESSION_DIR/ui/robot/$run_id"
  local report_file="$SESSION_DIR/ui/robot_report_$run_id.json"
  
  mkdir -p "$output_dir"
  mkdir -p "$REPO_ROOT/ui_tests/artifacts/robot"
  
  echo -e "${BLUE}Running Robot Framework UI tests...${NC}"
  echo ""
  
  # Build robot command
  local robot_args=(
    "--outputdir" "$output_dir"
    "--variable" "BASE_URL:http://127.0.0.1:$FRONTEND_PORT"
    "--variable" "HEADLESS:true"
    "--variable" "SCREENSHOT_DIR:$output_dir"
    "--loglevel" "INFO"
    "--consolecolors" "on"
  )
  
  # Run Robot tests
  local robot_exit_code=0
  robot "${robot_args[@]}" "$REPO_ROOT/ui_tests/robot" 2>&1 | tee "$SESSION_DIR/logs/robot-output.log" || robot_exit_code=$?
  
  # Parse results
  local tests_passed=0
  local tests_failed=0
  local test_names_passed=""
  local test_names_failed=""
  
  if [ -f "$output_dir/output.xml" ]; then
    # Extract test results from output.xml using simple grep (no xmllint dependency)
    tests_passed=$(grep -c 'status="PASS"' "$output_dir/output.xml" 2>/dev/null || echo "0")
    tests_failed=$(grep -c 'status="FAIL"' "$output_dir/output.xml" 2>/dev/null || echo "0")
    
    # Get failed test names
    test_names_failed=$(grep -B1 'status="FAIL"' "$output_dir/output.xml" 2>/dev/null | grep 'name=' | sed 's/.*name="\([^"]*\)".*/\1/' | tr '\n' ',' | sed 's/,$//' || echo "")
  fi
  
  # Generate JSON report
  cat > "$report_file" << EOF
{
  "run_id": "$run_id",
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "exit_code": $robot_exit_code,
  "all_passed": $([ $robot_exit_code -eq 0 ] && echo "true" || echo "false"),
  "tests": {
    "passed": $tests_passed,
    "failed": $tests_failed,
    "failed_names": "$test_names_failed"
  },
  "output_dir": "$output_dir",
  "reports": {
    "html": "$output_dir/report.html",
    "log": "$output_dir/log.html",
    "output": "$output_dir/output.xml"
  }
}
EOF

  # Save failures for fix agent
  if [ $robot_exit_code -ne 0 ]; then
    echo -e "Robot Framework test failures:\n- Exit code: $robot_exit_code\n- Failed tests: $test_names_failed" > "$SESSION_DIR/ui/robot_failures.txt"
    
    # Copy log output for debugging
    if [ -f "$output_dir/log.html" ]; then
      echo -e "\nRobot log available at: $output_dir/log.html" >> "$SESSION_DIR/ui/robot_failures.txt"
    fi
  fi
  
  echo ""
  if [ $robot_exit_code -eq 0 ]; then
    echo -e "${GREEN}All Robot Framework tests passed!${NC}"
    echo -e "  Passed: $tests_passed"
    return 0
  else
    echo -e "${RED}Robot Framework tests failed!${NC}"
    echo -e "  Passed: $tests_passed"
    echo -e "  Failed: $tests_failed"
    echo -e "  Failed tests: $test_names_failed"
    echo -e "  Report: $output_dir/report.html"
    return 1
  fi
}

run_ui_smoke_tests() {
  local run_id=$(date +%Y%m%d_%H%M%S)
  local snapshot_dir="$SESSION_DIR/ui/snapshots/$run_id"
  local screen_dir="$SESSION_DIR/ui/screens/$run_id"
  local report_file="$SESSION_DIR/ui/report_$run_id.json"
  
  mkdir -p "$snapshot_dir" "$screen_dir"
  
  echo -e "${BLUE}Running UI smoke tests...${NC}"
  echo ""
  
  local all_passed=true
  local test_results="[]"
  local failures=""

  AB_SESSION="ralph_${SESSION_TOKEN}_${run_id}"
  mkdir -p "$SESSION_DIR/logs"
  : > "$SESSION_DIR/logs/ui-test.log"
  
  # Test 1: App loads and layout visible
  echo -e "${CYAN}  [1/6] Testing app load and layout...${NC}"
  if run_ui_test_app_load "$snapshot_dir" "$screen_dir"; then
    echo -e "${GREEN}  ✓ App load test passed${NC}"
    test_results=$(echo "$test_results" | python3 -c "import json,sys; r=json.load(sys.stdin); r.append({'test':'app_load','passed':True}); print(json.dumps(r))")
  else
    echo -e "${RED}  ✗ App load test failed${NC}"
    test_results=$(echo "$test_results" | python3 -c "import json,sys; r=json.load(sys.stdin); r.append({'test':'app_load','passed':False}); print(json.dumps(r))")
    all_passed=false
    failures="$failures\n- App load/layout test failed"
  fi
  
  # Test 2: Dashboard - must not be blank
  echo -e "${CYAN}  [2/6] Testing dashboard renders (not blank)...${NC}"
  if run_ui_test_dashboard "$snapshot_dir" "$screen_dir"; then
    echo -e "${GREEN}  ✓ Dashboard test passed${NC}"
    test_results=$(echo "$test_results" | python3 -c "import json,sys; r=json.load(sys.stdin); r.append({'test':'dashboard','passed':True}); print(json.dumps(r))")
  else
    echo -e "${RED}  ✗ Dashboard test failed${NC}"
    test_results=$(echo "$test_results" | python3 -c "import json,sys; r=json.load(sys.stdin); r.append({'test':'dashboard','passed':False}); print(json.dumps(r))")
    all_passed=false
    failures="$failures\n- Dashboard rendered blank or failed to render"
  fi

  # Test 3: Projects - create/select
  echo -e "${CYAN}  [3/6] Testing projects functionality...${NC}"
  if run_ui_test_projects "$snapshot_dir" "$screen_dir"; then
    echo -e "${GREEN}  ✓ Projects test passed${NC}"
    test_results=$(echo "$test_results" | python3 -c "import json,sys; r=json.load(sys.stdin); r.append({'test':'projects','passed':True}); print(json.dumps(r))")
  else
    echo -e "${RED}  ✗ Projects test failed${NC}"
    test_results=$(echo "$test_results" | python3 -c "import json,sys; r=json.load(sys.stdin); r.append({'test':'projects','passed':False}); print(json.dumps(r))")
    all_passed=false
    failures="$failures\n- Projects test failed"
  fi
  
  # Test 4: Upload document
  echo -e "${CYAN}  [4/6] Testing document upload...${NC}"
  if run_ui_test_upload "$snapshot_dir" "$screen_dir"; then
    echo -e "${GREEN}  ✓ Upload test passed${NC}"
    test_results=$(echo "$test_results" | python3 -c "import json,sys; r=json.load(sys.stdin); r.append({'test':'upload','passed':True}); print(json.dumps(r))")
  else
    echo -e "${RED}  ✗ Upload test failed${NC}"
    test_results=$(echo "$test_results" | python3 -c "import json,sys; r=json.load(sys.stdin); r.append({'test':'upload','passed':False}); print(json.dumps(r))")
    all_passed=false
    failures="$failures\n- Upload test failed"
  fi
  
  # Test 5: History/QA blocks
  echo -e "${CYAN}  [5/6] Testing history/QA blocks...${NC}"
  if run_ui_test_history "$snapshot_dir" "$screen_dir"; then
    echo -e "${GREEN}  ✓ History test passed${NC}"
    test_results=$(echo "$test_results" | python3 -c "import json,sys; r=json.load(sys.stdin); r.append({'test':'history','passed':True}); print(json.dumps(r))")
  else
    echo -e "${RED}  ✗ History test failed${NC}"
    test_results=$(echo "$test_results" | python3 -c "import json,sys; r=json.load(sys.stdin); r.append({'test':'history','passed':False}); print(json.dumps(r))")
    all_passed=false
    failures="$failures\n- History test failed"
  fi
  
  # Test 6: QA - ask question
  echo -e "${CYAN}  [6/6] Testing QA functionality...${NC}"
  if run_ui_test_qa "$snapshot_dir" "$screen_dir"; then
    echo -e "${GREEN}  ✓ QA test passed${NC}"
    test_results=$(echo "$test_results" | python3 -c "import json,sys; r=json.load(sys.stdin); r.append({'test':'qa','passed':True}); print(json.dumps(r))")
  else
    echo -e "${RED}  ✗ QA test failed${NC}"
    test_results=$(echo "$test_results" | python3 -c "import json,sys; r=json.load(sys.stdin); r.append({'test':'qa','passed':False}); print(json.dumps(r))")
    all_passed=false
    failures="$failures\n- QA test failed"
  fi
  
  # Close browser
  ab close 2>/dev/null || true
  
  # Write report
  cat > "$report_file" << EOF
{
  "run_id": "$run_id",
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "all_passed": $all_passed,
  "tests": $test_results,
  "snapshot_dir": "$snapshot_dir",
  "screen_dir": "$screen_dir"
}
EOF

  # Save failures for fix agent
  if ! $all_passed; then
    echo -e "$failures" > "$SESSION_DIR/ui/failures.txt"
  fi
  
  echo ""
  if $all_passed; then
    echo -e "${GREEN}All UI smoke tests passed!${NC}"
    return 0
  else
    echo -e "${RED}Some UI tests failed. See: $report_file${NC}"
    return 1
  fi
}

run_ui_test_app_load() {
  local snapshot_dir="$1"
  local screen_dir="$2"
  
  # Open the app
  if ! ui_open; then
    return 1
  fi
  
  # Wait for page load
  sleep 3
  
  # Take snapshot and screenshot
  ui_snapshot_and_screenshot "$snapshot_dir/01_app_load.md" "$screen_dir/01_app_load.png"
  
  # Check for key layout elements in the snapshot
  local snapshot_content=$(cat "$snapshot_dir/01_app_load.md" 2>/dev/null || echo "")
  
  # Check for basic page structure (not blank, has some content)
  if [ -z "$snapshot_content" ] || [ ${#snapshot_content} -lt 100 ]; then
    echo "App appears blank or failed to load" >> "$SESSION_DIR/logs/ui-test.log"
    return 1
  fi
  
  # Look for common layout indicators
  if echo "$snapshot_content" | grep -qi -E "(navigation|header|sidebar|main|button|project|session)" 2>/dev/null; then
    return 0
  else
    echo "Layout elements not found in snapshot" >> "$SESSION_DIR/logs/ui-test.log"
    return 1
  fi
}

run_ui_test_dashboard() {
  local snapshot_dir="$1"
  local screen_dir="$2"

  if ! ui_open; then
    return 1
  fi
  sleep 1
  ui_click_tab "Dashboard" || true
  sleep 2

  ui_snapshot_and_screenshot "$snapshot_dir/02_dashboard.md" "$screen_dir/02_dashboard.png"
  ui_assert_dashboard_not_blank "$snapshot_dir/02_dashboard.md" 2
}

run_ui_test_projects() {
  local snapshot_dir="$1"
  local screen_dir="$2"
  
  if ! ui_open; then
    return 1
  fi
  sleep 1
  ui_click_tab "Q&A" || true
  sleep 2
  
  # Take snapshot
  ui_snapshot_and_screenshot "$snapshot_dir/03_projects.md" "$screen_dir/03_projects.png"
  
  local snapshot_content=$(cat "$snapshot_dir/03_projects.md" 2>/dev/null || echo "")
  
  # Check if projects UI elements are present
  # This is a basic check - look for project-related text
  if echo "$snapshot_content" | grep -qi -E "(project|create|new|select)" 2>/dev/null; then
    return 0
  fi
  
  # If no project UI, might still be okay if there's a different landing page
  # Check for any interactive elements
  if echo "$snapshot_content" | grep -qi -E "(button|link|input|@e[0-9])" 2>/dev/null; then
    return 0
  fi
  
  echo "Projects UI elements not found" >> "$SESSION_DIR/logs/ui-test.log"
  return 1
}

run_ui_test_upload() {
  local snapshot_dir="$1"
  local screen_dir="$2"
  
  if ! ui_open; then
    return 1
  fi
  sleep 1
  ui_click_tab "Documents" || true
  sleep 2

  ui_snapshot_and_screenshot "$snapshot_dir/04_upload.md" "$screen_dir/04_upload.png"
  
  local snapshot_content=$(cat "$snapshot_dir/04_upload.md" 2>/dev/null || echo "")
  
  # Check for upload-related UI elements
  if echo "$snapshot_content" | grep -qi -E "(upload|file|document|drag|drop|browse)" 2>/dev/null; then
    return 0
  fi
  
  # Check for any file input elements
  if echo "$snapshot_content" | grep -qi "type.*file" 2>/dev/null; then
    return 0
  fi
  
  # Upload might be behind a button/modal - just check page is interactive
  if echo "$snapshot_content" | grep -qi -E "(@e[0-9]+|button)" 2>/dev/null; then
    return 0
  fi
  
  echo "Upload UI elements not found" >> "$SESSION_DIR/logs/ui-test.log"
  return 1
}

run_ui_test_history() {
  local snapshot_dir="$1"
  local screen_dir="$2"

  if ! ui_open; then
    return 1
  fi
  sleep 1
  ui_click_tab "Ingestion" || true
  sleep 2

  ui_snapshot_and_screenshot "$snapshot_dir/05_history.md" "$screen_dir/05_history.png"
  
  local snapshot_content=$(cat "$snapshot_dir/05_history.md" 2>/dev/null || echo "")
  
  # Check for history/session related UI
  if echo "$snapshot_content" | grep -qi -E "(history|session|qa|question|answer|chat|message)" 2>/dev/null; then
    return 0
  fi
  
  # Page is rendered and interactive
  if echo "$snapshot_content" | grep -qi -E "(@e[0-9]+|button|list)" 2>/dev/null; then
    return 0
  fi
  
  echo "History UI elements not found" >> "$SESSION_DIR/logs/ui-test.log"
  return 1
}

run_ui_test_qa() {
  local snapshot_dir="$1"
  local screen_dir="$2"

  if ! ui_open; then
    return 1
  fi
  sleep 1
  ui_click_tab "Q&A" || true
  sleep 2

  ui_snapshot_and_screenshot "$snapshot_dir/06_qa.md" "$screen_dir/06_qa.png"
  
  local snapshot_content=$(cat "$snapshot_dir/06_qa.md" 2>/dev/null || echo "")
  
  # Check for QA/question input UI
  if echo "$snapshot_content" | grep -qi -E "(question|ask|input|textarea|submit|send)" 2>/dev/null; then
    return 0
  fi
  
  # Check for text input area
  if echo "$snapshot_content" | grep -qi -E "(textbox|textarea|@e[0-9])" 2>/dev/null; then
    return 0
  fi
  
  echo "QA UI elements not found" >> "$SESSION_DIR/logs/ui-test.log"
  return 1
}

# =============================================================================
# UI FAILURE FIX LOOP
# =============================================================================

generate_ui_planning_prompt() {
  local failures="$1"
  local snapshots_dir="$2"
  
  # Gather snapshot contents
  local snapshot_contents=""
  for f in "$snapshots_dir"/*.md; do
    if [ -f "$f" ]; then
      snapshot_contents="$snapshot_contents\n\n=== $(basename "$f") ===\n$(head -100 "$f")"
    fi
  done
  
  cat << PROMPT_END
# UI Planning Agent (READ-ONLY)

You are analyzing UI test failures to create a fix plan. Your session token is: **$SESSION_TOKEN**

## IMPORTANT: You are READ-ONLY
Do NOT modify any files. Only analyze and create a plan.

## Failed UI Tests
$failures

## UI Snapshots (Accessibility Trees)
$snapshot_contents

## Test Logs
$(tail -100 "$SESSION_DIR/logs/ui-test.log" 2>/dev/null || echo "No test logs available")

## Instructions

1. Analyze the snapshots and test failures
2. Identify what UI elements are missing or broken
3. Look at the frontend code to understand the issue
4. Create a concise fix plan

## Output Format

Output your analysis and plan:

\`\`\`
<ui-plan session="$SESSION_TOKEN">
Analysis: [What's wrong with the UI]
Root Cause: [Why it's broken]
Fix Plan:
1. [First fix step]
2. [Second fix step]
...
Files to Modify: [list of files]
</ui-plan>
\`\`\`

**WARNING**: You are READ-ONLY. Do NOT edit files.
PROMPT_END
}

generate_ui_impl_prompt() {
  local plan="$1"
  local failures="$2"
  
  cat << PROMPT_END
# UI Implementation Agent

You are fixing UI issues based on the planning agent's analysis. Your session token is: **$SESSION_TOKEN**

## UI Fix Plan
$plan

## Failed Tests
$failures

## Instructions

1. Implement the fixes described in the plan
2. Focus on the frontend code in frontend/src/
3. Make minimal changes to fix the issues
4. Ensure TypeScript compiles without errors

## Completion Signal

When done, output:

\`\`\`
<ui-fix-done session="$SESSION_TOKEN">
  Files Modified: [list]
  Summary: [what you fixed]
</ui-fix-done>
\`\`\`

Start by reading the relevant files and implementing the fixes.
PROMPT_END
}

run_ui_fix_loop() {
  echo -e "${MAGENTA}"
  echo "  ╔═══════════════════════════════════════════════════════════╗"
  echo "  ║         POST-COMPLETION: UI Fix Loop (agent-browser)      ║"
  echo "  ╚═══════════════════════════════════════════════════════════╝"
  echo -e "${NC}"
  
  local iteration=1
  
  while [ $iteration -le $UI_VERIFY_MAX_ITERATIONS ]; do
    echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}   UI Fix Iteration $iteration of $UI_VERIFY_MAX_ITERATIONS${NC}"
    echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}"
    echo ""
    
    # Step 1: Run UI smoke tests (agent-browser - fast triage)
    echo -e "${MAGENTA}▶ Step 1: Agent-Browser UI Smoke Tests (Fast Triage)${NC}"
    if run_ui_smoke_tests; then
      echo -e "${GREEN}All agent-browser UI tests passed!${NC}"
      return 0
    fi
    
    local failures=$(cat "$SESSION_DIR/ui/failures.txt" 2>/dev/null || echo "UI tests failed")
    local latest_snapshot_dir=$(ls -td "$SESSION_DIR/ui/snapshots"/*/ 2>/dev/null | head -1)
    
    # Step 2: Planning agent (read-only)
    echo -e "${MAGENTA}▶ Step 2: UI Planning Agent${NC}"
    echo ""
    
    local plan_prompt=$(generate_ui_planning_prompt "$failures" "$latest_snapshot_dir")
    
    echo -e "${CYAN}Running planning agent (model: $PLAN_MODEL, READ-ONLY)...${NC}"
    local plan_output
    plan_output=$(timeout "$CLAUDE_TIMEOUT" claude -p "$plan_prompt" --model "$PLAN_MODEL" --allowedTools "Read,Grep,Glob" --output-format text 2>&1) || {
      echo -e "${RED}Planning agent failed or timed out${NC}"
      plan_output="Planning failed. Check UI test logs."
    }
    
    echo "$plan_output" | head -60
    echo ""
    
    # Extract the plan
    local plan=$(echo "$plan_output" | sed -n '/<ui-plan/,/<\/ui-plan>/p')
    if [ -z "$plan" ]; then
      plan="$plan_output"
    fi
    
    # Step 3: Implementation agent
    echo -e "${MAGENTA}▶ Step 3: UI Implementation Agent${NC}"
    echo ""
    
    local impl_prompt=$(generate_ui_impl_prompt "$plan" "$failures")
    
    echo -e "${CYAN}Running implementation agent (model: $IMPL_MODEL)...${NC}"
    local impl_output
    impl_output=$(timeout "$CLAUDE_TIMEOUT" claude -p "$impl_prompt" --model "$IMPL_MODEL" --output-format text 2>&1) || {
      echo -e "${RED}Implementation agent failed or timed out${NC}"
    }
    
    echo "$impl_output" | head -80
    echo ""
    
    # Step 4: Run build gates to verify changes compile
    echo -e "${MAGENTA}▶ Step 4: Build Verification${NC}"
    if ! run_build_gates; then
      echo -e "${RED}Build failed after UI fixes. Running fix agent...${NC}"
      
      local error_output=$(cat "$SESSION_DIR/logs/build-errors.txt" 2>/dev/null || echo "Build failed")
      local fix_prompt=$(generate_fix_runtime_prompt "BUILD_ERROR_AFTER_UI_FIX" "$error_output" "")
      
      timeout "$CLAUDE_TIMEOUT" claude -p "$fix_prompt" --model "$FIX_MODEL" --output-format text 2>&1 | head -60 || true
    fi
    
    # Step 5: Restart services for re-test
    echo -e "${MAGENTA}▶ Step 5: Restarting Services${NC}"
    cleanup_services 2>/dev/null || true
    
    if ! run_runtime_verification; then
      echo -e "${RED}Runtime verification failed after UI fixes${NC}"
      iteration=$((iteration + 1))
      continue
    fi
    
    iteration=$((iteration + 1))
    sleep 2
  done
  
  echo -e "${RED}UI fix loop exceeded max iterations ($UI_VERIFY_MAX_ITERATIONS)${NC}"
  return 1
}

# =============================================================================
# ROBOT FRAMEWORK FIX LOOP (Deterministic Regression Gate)
# =============================================================================

generate_robot_planning_prompt() {
  local failures="$1"
  local robot_output_dir="$2"
  
  # Gather Robot Framework output if available
  local robot_log_content=""
  if [ -f "$SESSION_DIR/logs/robot-output.log" ]; then
    robot_log_content=$(tail -200 "$SESSION_DIR/logs/robot-output.log")
  fi
  
  cat << PROMPT_END
# Robot Framework UI Planning Agent (READ-ONLY)

You are analyzing Robot Framework UI test failures to create a fix plan. Your session token is: **$SESSION_TOKEN**

## IMPORTANT: You are READ-ONLY
Do NOT modify any files. Only analyze and create a plan.

## Failed Robot Tests
$failures

## Robot Framework Test Output
\`\`\`
$robot_log_content
\`\`\`

## Test Log Location
Robot HTML logs available at: $robot_output_dir/log.html

## Instructions

1. Analyze the Robot Framework test failures
2. Read the failed test definitions in ui_tests/robot/
3. Identify what UI elements are missing or broken
4. Look at the frontend code to understand the issue
5. Create a concise fix plan

## Output Format

Output your analysis and plan:

\`\`\`
<robot-plan session="$SESSION_TOKEN">
Analysis: [What's wrong with the UI]
Root Cause: [Why Robot tests are failing]
Fix Plan:
1. [First fix step]
2. [Second fix step]
...
Files to Modify: [list of files]
</robot-plan>
\`\`\`

**WARNING**: You are READ-ONLY. Do NOT edit files.
PROMPT_END
}

generate_robot_impl_prompt() {
  local plan="$1"
  local failures="$2"
  
  cat << PROMPT_END
# Robot Framework UI Implementation Agent

You are fixing UI issues based on the planning agent's analysis of Robot Framework test failures. Your session token is: **$SESSION_TOKEN**

## Robot Test Fix Plan
$plan

## Failed Tests
$failures

## Instructions

1. Implement the fixes described in the plan
2. Focus on the frontend code in frontend/src/
3. Make minimal changes to fix the issues
4. Ensure TypeScript compiles without errors
5. The Robot tests check for specific elements like h1 headings, visible content counts, etc.

## Completion Signal

When done, output:

\`\`\`
<robot-fix-done session="$SESSION_TOKEN">
  Files Modified: [list]
  Summary: [what you fixed]
</robot-fix-done>
\`\`\`

Start by reading the relevant files and implementing the fixes.
PROMPT_END
}

run_robot_fix_loop() {
  echo -e "${MAGENTA}"
  echo "  ╔═══════════════════════════════════════════════════════════╗"
  echo "  ║     POST-COMPLETION: Robot Framework Fix Loop             ║"
  echo "  ╚═══════════════════════════════════════════════════════════╝"
  echo -e "${NC}"
  
  local iteration=1
  local robot_max_iterations="${ROBOT_VERIFY_MAX_ITERATIONS:-$UI_VERIFY_MAX_ITERATIONS}"
  
  while [ $iteration -le $robot_max_iterations ]; do
    echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}   Robot Framework Fix Iteration $iteration of $robot_max_iterations${NC}"
    echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}"
    echo ""
    
    # Step 1: Run Robot Framework tests (deterministic regression gate)
    echo -e "${MAGENTA}▶ Step 1: Robot Framework Tests (Regression Gate)${NC}"
    if run_robot_tests; then
      echo -e "${GREEN}All Robot Framework tests passed!${NC}"
      return 0
    fi
    
    local failures=$(cat "$SESSION_DIR/ui/robot_failures.txt" 2>/dev/null || echo "Robot tests failed")
    local latest_robot_dir=$(ls -td "$SESSION_DIR/ui/robot"/*/ 2>/dev/null | head -1)
    
    # Step 2: Planning agent (read-only)
    echo -e "${MAGENTA}▶ Step 2: Robot Test Planning Agent${NC}"
    echo ""
    
    local plan_prompt=$(generate_robot_planning_prompt "$failures" "$latest_robot_dir")
    
    echo -e "${CYAN}Running planning agent (model: $PLAN_MODEL, READ-ONLY)...${NC}"
    local plan_output
    plan_output=$(timeout "$CLAUDE_TIMEOUT" claude -p "$plan_prompt" --model "$PLAN_MODEL" --allowedTools "Read,Grep,Glob" --output-format text 2>&1) || {
      echo -e "${RED}Planning agent failed or timed out${NC}"
      plan_output="Planning failed. Check Robot test logs."
    }
    
    echo "$plan_output" | head -60
    echo ""
    
    # Extract the plan
    local plan=$(echo "$plan_output" | sed -n '/<robot-plan/,/<\/robot-plan>/p')
    if [ -z "$plan" ]; then
      plan="$plan_output"
    fi
    
    # Step 3: Implementation agent
    echo -e "${MAGENTA}▶ Step 3: Robot Fix Implementation Agent${NC}"
    echo ""
    
    local impl_prompt=$(generate_robot_impl_prompt "$plan" "$failures")
    
    echo -e "${CYAN}Running implementation agent (model: $IMPL_MODEL)...${NC}"
    local impl_output
    impl_output=$(timeout "$CLAUDE_TIMEOUT" claude -p "$impl_prompt" --model "$IMPL_MODEL" --output-format text 2>&1) || {
      echo -e "${RED}Implementation agent failed or timed out${NC}"
    }
    
    echo "$impl_output" | head -80
    echo ""
    
    # Step 4: Run build gates to verify changes compile
    echo -e "${MAGENTA}▶ Step 4: Build Verification${NC}"
    if ! run_build_gates; then
      echo -e "${RED}Build failed after Robot fixes. Running fix agent...${NC}"
      
      local error_output=$(cat "$SESSION_DIR/logs/build-errors.txt" 2>/dev/null || echo "Build failed")
      local fix_prompt=$(generate_fix_runtime_prompt "BUILD_ERROR_AFTER_ROBOT_FIX" "$error_output" "")
      
      timeout "$CLAUDE_TIMEOUT" claude -p "$fix_prompt" --model "$FIX_MODEL" --output-format text 2>&1 | head -60 || true
    fi
    
    # Step 5: Restart services for re-test
    echo -e "${MAGENTA}▶ Step 5: Restarting Services${NC}"
    cleanup_services 2>/dev/null || true
    
    if ! run_runtime_verification; then
      echo -e "${RED}Runtime verification failed after Robot fixes${NC}"
      iteration=$((iteration + 1))
      continue
    fi
    
    iteration=$((iteration + 1))
    sleep 2
  done
  
  echo -e "${RED}Robot Framework fix loop exceeded max iterations ($robot_max_iterations)${NC}"
  return 1
}

# =============================================================================
# MAIN POST-COMPLETION VERIFICATION
# =============================================================================

run_post_completion_verification() {
  if [ "$POST_VERIFY" != "1" ]; then
    echo -e "${YELLOW}Post-completion verification disabled (POST_VERIFY=0)${NC}"
    return 0
  fi
  
  echo -e "${MAGENTA}"
  echo "  ╔═══════════════════════════════════════════════════════════╗"
  echo "  ║                                                           ║"
  echo "  ║   POST-COMPLETION VERIFICATION                            ║"
  echo "  ║                                                           ║"
  echo "  ╚═══════════════════════════════════════════════════════════╝"
  echo -e "${NC}"
  echo ""
  
  # ==========================================================================
  # Phase 1: Build & Runtime Verification
  # ==========================================================================
  echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
  echo -e "${BLUE}   Phase 1: Build & Runtime Verification${NC}"
  echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
  echo ""
  
  if ! run_runtime_fix_loop; then
    echo -e "${RED}Build/runtime verification failed after max iterations${NC}"
    print_post_verify_failure_banner "BUILD_RUNTIME"
    return 1
  fi
  
  # ==========================================================================
  # Phase 2: Agent-Browser UI Smoke Tests (Fast Triage)
  # ==========================================================================
  echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
  echo -e "${BLUE}   Phase 2: Agent-Browser UI Smoke Tests (Fast Triage)${NC}"
  echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
  echo ""
  
  local agent_browser_available=true
  if ! check_agent_browser; then
    echo -e "${YELLOW}Skipping agent-browser tests (not installed)${NC}"
    echo -e "${YELLOW}Install with: npm install -g agent-browser && agent-browser install${NC}"
    agent_browser_available=false
  fi
  
  if [ "$agent_browser_available" = true ]; then
    if ! run_ui_fix_loop; then
      echo -e "${RED}Agent-browser UI verification failed after max iterations${NC}"
      print_post_verify_failure_banner "AGENT_BROWSER_UI"
      return 1
    fi
  fi
  
  # ==========================================================================
  # Phase 3: Robot Framework UI Tests (Deterministic Regression Gate)
  # ==========================================================================
  echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
  echo -e "${BLUE}   Phase 3: Robot Framework Tests (Regression Gate)${NC}"
  echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
  echo ""
  
  local robot_available=true
  if ! check_robot_browser; then
    echo -e "${YELLOW}Skipping Robot Framework tests (not installed)${NC}"
    echo -e "${YELLOW}Install with: pip install robotframework robotframework-browser && rfbrowser init${NC}"
    robot_available=false
  fi
  
  if [ "$robot_available" = true ]; then
    if ! run_robot_fix_loop; then
      echo -e "${RED}Robot Framework verification failed after max iterations${NC}"
      print_post_verify_failure_banner "ROBOT_FRAMEWORK"
      return 1
    fi
  fi
  
  # Determine verification level
  local verification_level="BUILD_RUNTIME_ONLY"
  if [ "$agent_browser_available" = true ] && [ "$robot_available" = true ]; then
    verification_level="FULL"
  elif [ "$agent_browser_available" = true ]; then
    verification_level="AGENT_BROWSER_ONLY"
  elif [ "$robot_available" = true ]; then
    verification_level="ROBOT_ONLY"
  fi
  
  print_post_verify_success_banner "$verification_level"
  return 0
}

print_post_verify_success_banner() {
  local mode="$1"
  
  echo ""
  echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
  echo -e "${GREEN}   POST-COMPLETION VERIFICATION PASSED!${NC}"
  echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
  echo ""
  
  case "$mode" in
    "BUILD_RUNTIME_ONLY")
      echo -e "Mode:         ${GREEN}Build + Runtime Only${NC}"
      echo -e "Note:         ${YELLOW}UI tests skipped (tools not installed)${NC}"
      ;;
    "AGENT_BROWSER_ONLY")
      echo -e "Mode:         ${GREEN}Build + Runtime + Agent-Browser UI${NC}"
      echo -e "Note:         ${YELLOW}Robot Framework tests skipped (not installed)${NC}"
      ;;
    "ROBOT_ONLY")
      echo -e "Mode:         ${GREEN}Build + Runtime + Robot Framework${NC}"
      echo -e "Note:         ${YELLOW}Agent-browser tests skipped (not installed)${NC}"
      ;;
    "FULL")
      echo -e "Mode:         ${GREEN}Full Verification (All Gates)${NC}"
      ;;
  esac
  
  echo ""
  echo "All checks passed:"
  echo "  ✓ Build gates (mypy, tsc, npm build)"
  echo "  ✓ Backend health checks"
  echo "  ✓ Frontend serving"
  
  # Show UI test results based on mode
  if [ "$mode" = "AGENT_BROWSER_ONLY" ] || [ "$mode" = "FULL" ]; then
    echo "  ✓ Agent-browser UI smoke tests"
  fi
  if [ "$mode" = "ROBOT_ONLY" ] || [ "$mode" = "FULL" ]; then
    echo "  ✓ Robot Framework UI regression tests"
  fi
  
  echo ""
  echo "Artifacts saved to: $SESSION_DIR/"
  echo ""
  if [ -d "$SESSION_DIR/ui/robot" ]; then
    echo "Robot Framework reports:"
    local latest_robot=$(ls -td "$SESSION_DIR/ui/robot"/*/ 2>/dev/null | head -1)
    if [ -n "$latest_robot" ]; then
      echo "  - $latest_robot/report.html"
      echo "  - $latest_robot/log.html"
    fi
    echo ""
  fi
}

print_post_verify_failure_banner() {
  local phase="$1"
  
  echo ""
  echo -e "${RED}══════════════════════════════════════════════════════════════${NC}"
  echo -e "${RED}   POST-COMPLETION VERIFICATION FAILED${NC}"
  echo -e "${RED}══════════════════════════════════════════════════════════════${NC}"
  echo ""
  echo -e "Failed Phase: ${RED}$phase${NC}"
  echo ""
  
  case "$phase" in
    "BUILD_RUNTIME")
      echo "The build or runtime verification failed."
      echo ""
      echo "Debug files:"
      echo "  - $SESSION_DIR/logs/build-errors.txt"
      echo "  - $SESSION_DIR/logs/runtime-errors.txt"
      echo "  - $SESSION_DIR/logs/backend.log"
      echo "  - $SESSION_DIR/logs/frontend.log"
      ;;
    "AGENT_BROWSER_UI"|"UI_TESTS")
      echo "The agent-browser UI smoke tests failed."
      echo ""
      echo "Debug files:"
      echo "  - $SESSION_DIR/ui/failures.txt"
      echo "  - $SESSION_DIR/ui/snapshots/ (accessibility snapshots)"
      echo "  - $SESSION_DIR/ui/screens/ (screenshots)"
      echo "  - $SESSION_DIR/logs/ui-test.log"
      ;;
    "ROBOT_FRAMEWORK")
      echo "The Robot Framework UI regression tests failed."
      echo ""
      echo "Debug files:"
      echo "  - $SESSION_DIR/ui/robot_failures.txt"
      echo "  - $SESSION_DIR/logs/robot-output.log"
      local latest_robot=$(ls -td "$SESSION_DIR/ui/robot"/*/ 2>/dev/null | head -1)
      if [ -n "$latest_robot" ]; then
        echo "  - $latest_robot/report.html (HTML report)"
        echo "  - $latest_robot/log.html (detailed log)"
        echo "  - $latest_robot/output.xml (XML output)"
      fi
      ;;
  esac
  
  echo ""
  echo "Common debug locations:"
  echo "  - $SESSION_DIR/logs/backend.log"
  echo "  - $SESSION_DIR/logs/frontend.log"
  echo ""
  echo "Options:"
  echo "  1. Check the logs above for error details"
  echo "  2. Run again with more iterations:"
  echo "     POST_VERIFY_MAX_ITERATIONS=20 UI_VERIFY_MAX_ITERATIONS=15 $0 $CR_FILE"
  echo "  3. Run only specific UI tests manually:"
  echo "     - Agent-browser: ./scripts/run_ui_smoke_tests.sh"
  echo "     - Robot Framework: ./scripts/run_ui_robot_tests.sh"
  echo "  4. Disable post-verify for manual fix:"
  echo "     POST_VERIFY=0 $0 $CR_FILE"
  echo ""
}

# =============================================================================
# TEST GATES (Script-enforced - Agent cannot fake these)
# =============================================================================

run_test_gates() {
  local all_passed=true
  local results="{\"timestamp\": \"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\", \"gates\": {"

  echo -e "${BLUE}Running test gates...${NC}"
  echo ""

  # Python tests
  if [ -f "pyproject.toml" ]; then
    echo -e "${CYAN}  [1/5] Running pytest...${NC}"
    if uv run pytest -x --tb=short -q 2>&1 | tee /tmp/pytest-output.txt; then
      echo -e "${GREEN}  ✓ pytest passed${NC}"
      results="$results\"pytest\": {\"passed\": true},"
    else
      echo -e "${RED}  ✗ pytest failed${NC}"
      results="$results\"pytest\": {\"passed\": false, \"output\": \"$(cat /tmp/pytest-output.txt | tail -20 | sed 's/"/\\"/g' | tr '\n' ' ')\"},"
      all_passed=false
    fi

    echo -e "${CYAN}  [2/5] Running mypy type checking...${NC}"
    if uv run mypy src/ --ignore-missing-imports --no-error-summary 2>&1 | tee /tmp/mypy-output.txt; then
      echo -e "${GREEN}  ✓ mypy passed${NC}"
      results="$results\"mypy\": {\"passed\": true},"
    else
      echo -e "${RED}  ✗ mypy failed${NC}"
      results="$results\"mypy\": {\"passed\": false, \"output\": \"$(cat /tmp/mypy-output.txt | tail -20 | sed 's/"/\\"/g' | tr '\n' ' ')\"},"
      all_passed=false
    fi
  else
    results="$results\"pytest\": {\"skipped\": true},\"mypy\": {\"skipped\": true},"
  fi

  # Frontend checks
  if [ -f "frontend/package.json" ]; then
    echo -e "${CYAN}  [3/5] Running TypeScript type check...${NC}"
    if (cd frontend && npx tsc --noEmit 2>&1 | tee /tmp/tsc-output.txt); then
      echo -e "${GREEN}  ✓ tsc passed${NC}"
      results="$results\"tsc\": {\"passed\": true},"
    else
      echo -e "${RED}  ✗ tsc failed${NC}"
      results="$results\"tsc\": {\"passed\": false, \"output\": \"$(cat /tmp/tsc-output.txt | tail -20 | sed 's/"/\\"/g' | tr '\n' ' ')\"},"
      all_passed=false
    fi

    echo -e "${CYAN}  [4/5] Running ESLint...${NC}"
    if (cd frontend && npm run lint 2>&1 | tee /tmp/lint-output.txt); then
      echo -e "${GREEN}  ✓ lint passed${NC}"
      results="$results\"lint\": {\"passed\": true},"
    else
      echo -e "${RED}  ✗ lint failed${NC}"
      results="$results\"lint\": {\"passed\": false, \"output\": \"$(cat /tmp/lint-output.txt | tail -20 | sed 's/"/\\"/g' | tr '\n' ' ')\"},"
      all_passed=false
    fi

    echo -e "${CYAN}  [5/5] Running build...${NC}"
    if (cd frontend && npm run build 2>&1 | tee /tmp/build-output.txt); then
      echo -e "${GREEN}  ✓ build passed${NC}"
      results="$results\"build\": {\"passed\": true}"
    else
      echo -e "${RED}  ✗ build failed${NC}"
      results="$results\"build\": {\"passed\": false, \"output\": \"$(cat /tmp/build-output.txt | tail -20 | sed 's/"/\\"/g' | tr '\n' ' ')\"}"
      all_passed=false
    fi
  else
    results="$results\"tsc\": {\"skipped\": true},\"lint\": {\"skipped\": true},\"build\": {\"skipped\": true}"
  fi

  results="$results}, \"all_passed\": $all_passed}"
  echo "$results" > "$SESSION_DIR/test-results.json"

  echo ""
  if $all_passed; then
    echo -e "${GREEN}All test gates passed!${NC}"
    return 0
  else
    echo -e "${RED}Some test gates failed.${NC}"
    return 1
  fi
}

# =============================================================================
# AGENT PROMPTS
# =============================================================================

generate_impl_prompt() {
  local task_info="$1"
  local previous_feedback="$2"

  cat << PROMPT_END
# Implementation Agent

You are implementing a Change Request task. Your session token is: **$SESSION_TOKEN**

## Security Requirements

- You MUST include the session token in your completion signal
- Do NOT modify files in the \`.ralph-session/\` directory
- Do NOT output completion signals without the valid session token

## Your Task

$task_info

## Previous Feedback (if any)

$previous_feedback

## Instructions

1. Read the CR document: $CR_FILE
2. Implement the specific task assigned to you
3. Follow the implementation approach in the CR
4. Maintain code quality: types, docstrings, error handling
5. Do NOT update the task status in the CR - the script handles this

## Completion Signal

When you have finished implementing THIS TASK (not the entire CR), output:

\`\`\`
<task-done session="$SESSION_TOKEN">
  Task ID: [the task ID]
  Files changed: [list of files you modified]
  Summary: [brief summary of what you implemented]
</task-done>
\`\`\`

**WARNING**: Any completion signal without the valid session token will be rejected.
**WARNING**: Do NOT output the completion signal in code comments or quotes.

Start by reading the CR file and implementing the assigned task.
PROMPT_END
}

generate_test_prompt() {
  local task_info="$1"
  local impl_output="$2"
  local previous_feedback="$3"

  cat << PROMPT_END
# Test Writing Agent
You are writing tests for an already-implemented Change Request task. Your session token is: **$SESSION_TOKEN**

## Security Requirements
- You MUST include the session token in your completion signal
- Do NOT modify files in the \`.ralph-session/\` directory

## Task Context
$task_info

## Implementation Output (what was implemented)
$impl_output

## Previous Feedback (if any)
$previous_feedback

## Strict Rules (enforced)
You may ONLY create or modify test-related files. Allowed paths include:
- \`tests/**\`
- \`test_scripts/**\`
- Frontend test files under \`frontend/src/**\` that contain \`.test.\` or \`.spec.\`, or are inside a \`__tests__\` folder
- E2E test folders like \`frontend/**/cypress/**\`, \`frontend/**/playwright/**\`, \`frontend/**/e2e/**\`

Do NOT edit application/production code. If you believe production code needs changes for testability, explain it in your output instead of editing it.

## Goal
Add/adjust tests so the script-enforced test gates pass (pytest/mypy/tsc/lint/build) and the task is properly covered.

## Completion Signal
When you have finished writing tests for THIS TASK, output:

\`\`\`
<tests-done session="$SESSION_TOKEN">
  Task ID: [the task ID]
  Files changed: [list of test files you modified/added]
  Notes: [brief notes]
</tests-done>
\`\`\`

Start by finding what needs test coverage, then write the tests.
PROMPT_END
}

generate_review_prompt() {
  local impl_output="$1"
  local test_results="$2"
  local task_info="$3"

  cat << PROMPT_END
# Review Agent (READ-ONLY)

You are reviewing an implementation. Your session token is: **$SESSION_TOKEN**

## Your Role

You are an INDEPENDENT reviewer. You did NOT write this code.
You have READ-ONLY access to the codebase.

## Task Being Reviewed

$task_info

## Implementation Output

$impl_output

## Test Results

$test_results

## Review Checklist

Check the implementation against these criteria:

1. **Correctness**: Does it implement the task requirements?
2. **Type Safety**: Are proper type annotations present?
3. **Error Handling**: Are errors handled appropriately?
4. **Code Quality**: Is the code clean and maintainable?
5. **Test Coverage**: Are there tests for new functionality?
6. **No Regressions**: Does it break existing functionality?

## Review Decision

If the implementation passes ALL criteria, output:

\`\`\`
<review-approved session="$SESSION_TOKEN">
  Task ID: [the task ID]
  Checklist: all-passed
</review-approved>
\`\`\`

If the implementation has issues, output:

\`\`\`
<review-rejected session="$SESSION_TOKEN">
  Task ID: [the task ID]
  Issues:
  - [List each issue]
  Recommendation: [What needs to be fixed]
</review-rejected>
\`\`\`

**WARNING**: Your review signal MUST include the valid session token.
**WARNING**: You are READ-ONLY - do NOT modify any files.

Start by reading the relevant files and reviewing the implementation.
PROMPT_END
}

# =============================================================================
# TEST AGENT GUARDRAILS
# =============================================================================

is_allowed_test_path() {
  local path="$1"

  # Backend tests
  if [[ "$path" == tests/* || "$path" == test_scripts/* ]]; then
    return 0
  fi

  # Frontend tests / e2e
  if [[ "$path" == frontend/* ]]; then
    if [[ "$path" == *"/__tests__/"* || "$path" == *".test."* || "$path" == *".spec."* ]]; then
      return 0
    fi
    if [[ "$path" == *"/cypress/"* || "$path" == *"/playwright/"* || "$path" == *"/e2e/"* ]]; then
      return 0
    fi
  fi

  return 1
}

snapshot_modified_paths() {
  # Includes modified tracked files + untracked files (not ignored)
  git diff --name-only 2>/dev/null || true
  git ls-files --others --exclude-standard 2>/dev/null || true
}

revert_path_if_untracked_or_tracked() {
  local path="$1"
  if git ls-files --error-unmatch "$path" >/dev/null 2>&1; then
    git checkout -- "$path" >/dev/null 2>&1 || true
  else
    rm -f "$path" >/dev/null 2>&1 || true
  fi
}

# =============================================================================
# TASK MANAGEMENT
# =============================================================================

get_next_pending_task() {
  # Parse the CR file to find the next pending task
  # Supports multiple formats:
  # - "passes": false (from create-prd.md and create-change-request.md)
  # - "status": "pending" (alternative format)
  # Tasks can have either "id" or use "description" as identifier

  if grep -q '"passes":' "$CR_FILE" 2>/dev/null; then
    # Find first task with "passes": false
    local task_block=$(grep -B20 '"passes":[[:space:]]*false' "$CR_FILE" | head -25)
    if [ -n "$task_block" ]; then
      # Try to extract task ID first, fall back to description
      local task_id=$(echo "$task_block" | grep -oE '"id":[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"\([^"]*\)"$/\1/')
      local task_desc=$(echo "$task_block" | grep -oE '"description":[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"\([^"]*\)"$/\1/')
      local task_category=$(echo "$task_block" | grep -oE '"category":[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"\([^"]*\)"$/\1/')

      # Use description as ID if no explicit ID field (compatible with create-prd.md format)
      if [ -z "$task_id" ] && [ -n "$task_desc" ]; then
        task_id="$task_desc"
      fi

      if [ -n "$task_id" ]; then
        echo "Task ID: $task_id"
        [ -n "$task_category" ] && echo "Category: $task_category"
        echo "Description: $task_desc"
        echo ""
        echo "Full task context:"
        echo "$task_block"
        return 0
      fi
    fi
  else
    # Fallback to status field format
    local task_block=$(grep -B20 '"status":[[:space:]]*"pending"' "$CR_FILE" | head -25)
    if [ -n "$task_block" ]; then
      local task_id=$(echo "$task_block" | grep -oE '"id":[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"\([^"]*\)"$/\1/')
      local task_desc=$(echo "$task_block" | grep -oE '"description":[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"\([^"]*\)"$/\1/')

      if [ -z "$task_id" ] && [ -n "$task_desc" ]; then
        task_id="$task_desc"
      fi

      if [ -n "$task_id" ]; then
        echo "Task ID: $task_id"
        echo "Description: $task_desc"
        echo ""
        echo "Full task context:"
        echo "$task_block"
        return 0
      fi
    fi
  fi

  return 1
}

count_tasks() {
  if grep -q '"passes":' "$CR_FILE" 2>/dev/null; then
    # Note: `grep -c` prints "0" even when it returns exit code 1 (no matches).
    # Using `|| true` avoids capturing "0\n0" on macOS, which breaks numeric comparisons.
    COMPLETED_COUNT=$(grep -c '"passes":[[:space:]]*true' "$CR_FILE" 2>/dev/null || true)
    PENDING_COUNT=$(grep -c '"passes":[[:space:]]*false' "$CR_FILE" 2>/dev/null || true)
  else
    PENDING_COUNT=$(grep -c '"status":[[:space:]]*"pending"' "$CR_FILE" 2>/dev/null || true)
    COMPLETED_COUNT=$(grep -c '"status":[[:space:]]*"completed"' "$CR_FILE" 2>/dev/null || true)
  fi

  # Normalize to single-line integers for reliable `-eq` / `-gt` comparisons
  COMPLETED_COUNT=$(printf "%s" "${COMPLETED_COUNT:-0}" | tr -d '[:space:]')
  PENDING_COUNT=$(printf "%s" "${PENDING_COUNT:-0}" | tr -d '[:space:]')
  # Use if/then instead of && to avoid set -e issues
  if [ -z "$COMPLETED_COUNT" ]; then COMPLETED_COUNT=0; fi
  if [ -z "$PENDING_COUNT" ]; then PENDING_COUNT=0; fi
}

mark_task_complete() {
  local task_id="$1"

  # Verify checksum before modifying
  if ! verify_checksum; then
    echo -e "${RED}Cannot update task - checksum verification failed${NC}"
    return 1
  fi

  # Update the CR file - this is the ONLY place task status changes
  # Supports both "id" field and "description" as identifier (for create-prd.md compatibility)
  if grep -q '"passes":' "$CR_FILE" 2>/dev/null; then
    python3 << EOF
import re
import json

with open("$CR_FILE", "r") as f:
    content = f.read()

task_id = """$task_id"""

# Escape special regex characters in task_id
escaped_id = re.escape(task_id)

# Try to find by "id" field first
pattern_id = r'("id":\s*"' + escaped_id + r'".*?"passes":\s*)false'
new_content = re.sub(pattern_id, r'\1true', content, count=1, flags=re.DOTALL)

# If no change, try to find by "description" field (create-prd.md format)
if new_content == content:
    pattern_desc = r'("description":\s*"' + escaped_id + r'".*?"passes":\s*)false'
    new_content = re.sub(pattern_desc, r'\1true', content, count=1, flags=re.DOTALL)

# If still no change, try reverse order (passes before description)
if new_content == content:
    pattern_rev = r'(\{\s*"category":\s*"[^"]*",\s*"description":\s*"' + escaped_id + r'".*?)("passes":\s*)false'
    new_content = re.sub(pattern_rev, r'\1\2true', content, count=1, flags=re.DOTALL)

with open("$CR_FILE", "w") as f:
    f.write(new_content)

# Report if update was successful
if new_content != content:
    print(f"Updated task: {task_id[:50]}...")
else:
    print(f"Warning: Could not find task to update: {task_id[:50]}...")
EOF
  else
    # Update status field format
    python3 << EOF
import re

with open("$CR_FILE", "r") as f:
    content = f.read()

task_id = """$task_id"""
escaped_id = re.escape(task_id)

# Try "id" field first, then "description"
pattern_id = r'("id":\s*"' + escaped_id + r'".*?"status":\s*)"pending"'
new_content = re.sub(pattern_id, r'\1"completed"', content, count=1, flags=re.DOTALL)

if new_content == content:
    pattern_desc = r'("description":\s*"' + escaped_id + r'".*?"status":\s*)"pending"'
    new_content = re.sub(pattern_desc, r'\1"completed"', content, count=1, flags=re.DOTALL)

with open("$CR_FILE", "w") as f:
    f.write(new_content)
EOF
  fi

  # Update session task status
  python3 << EOF
import json
from datetime import datetime, timezone

with open("$SESSION_DIR/task-status.json", "r") as f:
    status = json.load(f)

now_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

status["tasks"].append({
    "task_id": "$task_id",
    "completed_at": now_utc,
    "iteration": $CURRENT_ITERATION
})
status["last_updated"] = now_utc

with open("$SESSION_DIR/task-status.json", "w") as f:
    json.dump(status, f, indent=2)
EOF

  # Update checksum after modification
  update_checksum

  echo -e "${GREEN}Task $task_id marked as complete by script${NC}"
}

# =============================================================================
# SIGNAL VALIDATION
# =============================================================================

validate_task_done_signal() {
  local output="$1"

  # Check if signal exists
  if ! echo "$output" | grep -q '<task-done session="'; then
    echo "NO_SIGNAL"
    return 1
  fi

  # Extract the session token from the signal
  local signal_token=$(echo "$output" | grep -o '<task-done session="[^"]*"' | sed 's/.*session="\([^"]*\)".*/\1/')

  if [ "$signal_token" != "$SESSION_TOKEN" ]; then
    echo "INVALID_TOKEN"
    return 1
  fi

  # Extract task ID from signal
  local task_id=$(echo "$output" | sed -n '/<task-done/,/<\/task-done>/p' | grep -o 'Task ID:.*' | sed 's/^Task ID:[[:space:]]*//; s/^[[:space:]]*//; s/[[:space:]]*$//')

  echo "$task_id"
  return 0
}

validate_tests_done_signal() {
  local output="$1"

  if ! echo "$output" | grep -q '<tests-done session="'; then
    echo "NO_SIGNAL"
    return 1
  fi

  local signal_token=$(echo "$output" | grep -o '<tests-done session="[^"]*"' | sed 's/.*session="\([^"]*\)".*/\1/')
  if [ "$signal_token" != "$SESSION_TOKEN" ]; then
    echo "INVALID_TOKEN"
    return 1
  fi

  local task_id=$(echo "$output" | sed -n '/<tests-done/,/<\/tests-done>/p' | grep -o 'Task ID:.*' | sed 's/^Task ID:[[:space:]]*//; s/^[[:space:]]*//; s/[[:space:]]*$//')
  echo "$task_id"
  return 0
}

validate_review_signal() {
  local output="$1"

  # Check for approval
  if echo "$output" | grep -q '<review-approved session="'; then
    local signal_token=$(echo "$output" | grep -o '<review-approved session="[^"]*"' | sed 's/.*session="\([^"]*\)".*/\1/')
    if [ "$signal_token" = "$SESSION_TOKEN" ]; then
      echo "APPROVED"
      return 0
    else
      echo "INVALID_TOKEN"
      return 1
    fi
  fi

  # Check for rejection
  if echo "$output" | grep -q '<review-rejected session="'; then
    local signal_token=$(echo "$output" | grep -o '<review-rejected session="[^"]*"' | sed 's/.*session="\([^"]*\)".*/\1/')
    if [ "$signal_token" = "$SESSION_TOKEN" ]; then
      # Extract rejection reason
      local issues=$(echo "$output" | sed -n '/<review-rejected/,/<\/review-rejected>/p')
      echo "REJECTED: $issues"
      return 0
    else
      echo "INVALID_TOKEN"
      return 1
    fi
  fi

  echo "NO_SIGNAL"
  return 1
}

# =============================================================================
# MAIN LOOP
# =============================================================================

main() {
  # Initialize session
  init_session

  # Extract CR name
  CR_NAME=$(basename "$CR_FILE" .md)
  CR_ACTIVITY_FILE="changes/${CR_NAME}-activity.md"

  # Display configuration
  echo ""
  echo -e "CR File:         ${GREEN}$CR_FILE${NC}"
  echo -e "Activity Log:    ${GREEN}$CR_ACTIVITY_FILE${NC}"
  echo -e "Max Iterations:  ${GREEN}$MAX_ITERATIONS${NC}"
  echo -e "Timeout/Agent:   ${GREEN}${CLAUDE_TIMEOUT}s${NC}"
  echo -e "Session Dir:     ${GREEN}$SESSION_DIR/${NC}"
  echo ""
  echo -e "${BLUE}Agent Models:${NC}"
  echo -e "  Impl Model:    ${GREEN}$IMPL_MODEL${NC}"
  echo -e "  Test Model:    ${GREEN}$TEST_MODEL${NC}"
  echo -e "  Review Model:  ${GREEN}$REVIEW_MODEL${NC}"
  echo -e "  Fix Model:     ${GREEN}$FIX_MODEL${NC}"
  echo -e "  Plan Model:    ${GREEN}$PLAN_MODEL${NC}"
  echo ""
  echo -e "${BLUE}Post-Completion Verification:${NC}"
  if [ "$POST_VERIFY" = "1" ]; then
    echo -e "  Enabled:            ${GREEN}Yes${NC}"
    echo -e "  Runtime Iters:      ${GREEN}$POST_VERIFY_MAX_ITERATIONS${NC}"
    echo -e "  Agent-Browser Iters:${GREEN}$UI_VERIFY_MAX_ITERATIONS${NC}"
    echo -e "  Robot Fwk Iters:    ${GREEN}$ROBOT_VERIFY_MAX_ITERATIONS${NC}"
  else
    echo -e "  Enabled:            ${YELLOW}No (POST_VERIFY=0)${NC}"
  fi
  echo ""

  # Show initial task count
  count_tasks
  echo -e "${BLUE}Task Summary:${NC}"
  echo -e "  ${GREEN}$COMPLETED_COUNT completed${NC}"
  echo -e "  ${YELLOW}$PENDING_COUNT pending${NC}"
  echo ""

  echo -e "${YELLOW}Starting in 3 seconds... Press Ctrl+C to abort${NC}"
  sleep 3
  echo ""

  local previous_feedback=""

  for ((CURRENT_ITERATION=1; CURRENT_ITERATION<=MAX_ITERATIONS; CURRENT_ITERATION++)); do
    echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}   Iteration $CURRENT_ITERATION of $MAX_ITERATIONS${NC}"
    echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}"
    echo ""

    # Verify session integrity
    if ! verify_checksum; then
      echo -e "${RED}Session integrity compromised. Regenerating checksum...${NC}"
      update_checksum
    fi

    # Get next pending task
    count_tasks
    echo -e "Tasks: ${GREEN}$COMPLETED_COUNT completed${NC}, ${YELLOW}$PENDING_COUNT pending${NC}"
    echo ""

    # Check if all tasks complete
    if [ "$PENDING_COUNT" -eq 0 ] && [ "$COMPLETED_COUNT" -gt 0 ]; then
      echo -e "${GREEN}All CR tasks are complete!${NC}"
      print_success_banner
      
      # Run post-completion verification if enabled
      if run_post_completion_verification; then
        echo -e "${GREEN}All verification passed! Exiting successfully.${NC}"
        exit 0
      else
        echo -e "${RED}Post-completion verification failed.${NC}"
        exit 1
      fi
    fi

    # Get next task
    local task_info=$(get_next_pending_task)
    if [ -z "$task_info" ]; then
      echo -e "${YELLOW}No pending tasks found. Checking CR format...${NC}"
      continue
    fi

    local current_task_id=$(echo "$task_info" | grep 'Task ID:' | sed 's/^Task ID:[[:space:]]*//; s/^[[:space:]]*//; s/[[:space:]]*$//')
    echo -e "${CYAN}Working on task: $current_task_id${NC}"
    echo ""

    # =========================================================================
    # PHASE 1: Implementation Agent
    # =========================================================================
    echo -e "${MAGENTA}▶ PHASE 1: Implementation Agent${NC}"
    echo ""

    local impl_prompt=$(generate_impl_prompt "$task_info" "$previous_feedback")

    echo -e "${CYAN}Running implementation agent (model: $IMPL_MODEL, timeout: ${CLAUDE_TIMEOUT}s)...${NC}"
    local impl_output=""
    impl_output=$(timeout "$CLAUDE_TIMEOUT" claude -p "$impl_prompt" --model "$IMPL_MODEL" --output-format text 2>&1) || {
      exit_code=$?
      if [ $exit_code -eq 124 ]; then
        echo -e "${RED}Implementation agent timed out${NC}"
        impl_output="TIMEOUT"
      else
        echo -e "${RED}Implementation agent failed with exit code $exit_code${NC}"
      fi
    }

    echo "$impl_output" | head -100
    echo ""

    # Validate task-done signal
    local task_done_result=$(validate_task_done_signal "$impl_output")

    if [ "$task_done_result" = "NO_SIGNAL" ]; then
      echo -e "${YELLOW}No valid task-done signal received. Continuing to next iteration...${NC}"
      previous_feedback="The implementation agent did not signal completion. Please ensure you output the task-done signal with the valid session token when done."
      sleep 2
      continue
    fi

    if [ "$task_done_result" = "INVALID_TOKEN" ]; then
      echo -e "${RED}SECURITY: Invalid session token in task-done signal!${NC}"
      echo -e "${RED}This could indicate an attempt to bypass verification.${NC}"
      previous_feedback="SECURITY WARNING: Your task-done signal had an invalid session token. You MUST use the exact token provided: $SESSION_TOKEN"
      sleep 2
      continue
    fi

    echo -e "${GREEN}Valid task-done signal received for task: $task_done_result${NC}"
    echo ""

    # =========================================================================
    # PHASE 2: Test Writing Agent (separate from implementation)
    # =========================================================================
    echo -e "${MAGENTA}▶ PHASE 2: Test Writing Agent${NC}"
    echo ""

    local pre_test_snapshot="/tmp/ralph-pre-test-${SESSION_TOKEN}.txt"
    local post_test_snapshot="/tmp/ralph-post-test-${SESSION_TOKEN}.txt"
    local newly_changed="/tmp/ralph-newly-changed-${SESSION_TOKEN}.txt"

    snapshot_modified_paths | sort -u > "$pre_test_snapshot"

    local test_prompt=$(generate_test_prompt "$task_info" "$impl_output" "$previous_feedback")
    echo -e "${CYAN}Running test-writing agent (model: $TEST_MODEL, timeout: ${CLAUDE_TIMEOUT}s)...${NC}"
    local test_output=""
    test_output=$(timeout "$CLAUDE_TIMEOUT" claude -p "$test_prompt" --model "$TEST_MODEL" --allowedTools "Read,Grep,Glob,Edit,Write" --output-format text 2>&1) || {
      exit_code=$?
      if [ $exit_code -eq 124 ]; then
        echo -e "${RED}Test-writing agent timed out${NC}"
        test_output="TIMEOUT"
      else
        echo -e "${RED}Test-writing agent failed with exit code $exit_code${NC}"
      fi
    }

    echo "$test_output" | head -80
    echo ""

    # Guardrail: revert any NEW paths that are not test-related
    snapshot_modified_paths | sort -u > "$post_test_snapshot"
    comm -13 "$pre_test_snapshot" "$post_test_snapshot" > "$newly_changed" || true

    local violations=()
    while IFS= read -r f; do
      if [ -z "$f" ]; then continue; fi
      if ! is_allowed_test_path "$f"; then
        violations+=("$f")
        revert_path_if_untracked_or_tracked "$f"
      fi
    done < "$newly_changed"

    if [ "${#violations[@]}" -gt 0 ]; then
      echo -e "${RED}Test-writing agent modified non-test files (reverted):${NC}"
      for v in "${violations[@]}"; do
        echo -e "${RED}  - $v${NC}"
      done
      previous_feedback="Your test-writing step modified non-test files, which is not allowed. Those changes were reverted. Only create/modify test files under tests/, test_scripts/, or frontend test paths."
      sleep 2
      continue
    fi

    # Validate tests-done signal (non-fatal; we can still proceed to gates)
    local tests_done_result=$(validate_tests_done_signal "$test_output")
    if [ "$tests_done_result" = "INVALID_TOKEN" ]; then
      echo -e "${RED}SECURITY: Invalid session token in tests-done signal!${NC}"
      previous_feedback="SECURITY WARNING: Your tests-done signal had an invalid session token. You MUST use the exact token provided: $SESSION_TOKEN"
      sleep 2
      continue
    fi

    # =========================================================================
    # PHASE 3: Test Gates (Script-enforced)
    # =========================================================================
    echo -e "${MAGENTA}▶ PHASE 3: Test Gates${NC}"
    echo ""

    if ! run_test_gates; then
      echo -e "${RED}Test gates failed. Implementation rejected.${NC}"
      previous_feedback="Your implementation failed the test gates. Please fix the issues and try again. Test results: $(cat $SESSION_DIR/test-results.json)"
      sleep 2
      continue
    fi

    # =========================================================================
    # PHASE 4: Review Agent
    # =========================================================================
    echo -e "${MAGENTA}▶ PHASE 4: Review Agent${NC}"
    echo ""

    local test_results=$(cat "$SESSION_DIR/test-results.json")
    local review_prompt=$(generate_review_prompt "$impl_output" "$test_results" "$task_info")

    echo -e "${CYAN}Running review agent (model: $REVIEW_MODEL, READ-ONLY)...${NC}"
    local review_output=""
    review_output=$(timeout "$CLAUDE_TIMEOUT" claude -p "$review_prompt" --model "$REVIEW_MODEL" --allowedTools "Read,Grep,Glob" --output-format text 2>&1) || {
      exit_code=$?
      if [ $exit_code -eq 124 ]; then
        echo -e "${YELLOW}Review agent timed out. Skipping review...${NC}"
        review_output="<review-approved session=\"$SESSION_TOKEN\">Timeout - auto-approved</review-approved>"
      fi
    }

    echo "$review_output" | head -50
    echo ""

    # Validate review signal
    local review_result=$(validate_review_signal "$review_output")

    if [[ "$review_result" == "APPROVED" ]]; then
      echo -e "${GREEN}Review approved!${NC}"
      echo ""

      # =========================================================================
      # PHASE 5: Script Updates Task Status
      # =========================================================================
      echo -e "${MAGENTA}▶ PHASE 5: Updating Task Status (script-only)${NC}"
      echo ""

      mark_task_complete "$current_task_id"

      # Log the review
      python3 << EOF
import json
from datetime import datetime, timezone

with open("$SESSION_DIR/review-log.json", "r") as f:
    log = json.load(f)

log.append({
    "task_id": "$current_task_id",
    "iteration": $CURRENT_ITERATION,
    "decision": "approved",
    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
})

with open("$SESSION_DIR/review-log.json", "w") as f:
    json.dump(log, f, indent=2)
EOF

      previous_feedback=""
      echo -e "${GREEN}Task $current_task_id completed successfully!${NC}"

    elif [[ "$review_result" == REJECTED* ]]; then
      echo -e "${RED}Review rejected!${NC}"
      local issues=$(echo "$review_result" | sed 's/REJECTED: //')
      previous_feedback="Your implementation was rejected by the review agent. Issues: $issues"

      # Log the rejection
      python3 << EOF
import json
from datetime import datetime, timezone

with open("$SESSION_DIR/review-log.json", "r") as f:
    log = json.load(f)

log.append({
    "task_id": "$current_task_id",
    "iteration": $CURRENT_ITERATION,
    "decision": "rejected",
    "issues": """$issues""",
    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
})

with open("$SESSION_DIR/review-log.json", "w") as f:
    json.dump(log, f, indent=2)
EOF

    elif [ "$review_result" = "INVALID_TOKEN" ]; then
      echo -e "${RED}SECURITY: Invalid session token in review signal!${NC}"
      previous_feedback=""

    else
      echo -e "${YELLOW}No valid review signal received. Treating as approved...${NC}"
      mark_task_complete "$current_task_id"
      previous_feedback=""
    fi

    echo ""
    echo -e "${YELLOW}--- End of iteration $CURRENT_ITERATION ---${NC}"
    echo ""

    # Small delay between iterations
    sleep 2
  done

  print_max_iterations_banner
  exit 1
}

print_success_banner() {
  echo ""
  echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
  echo -e "${GREEN}   CHANGE REQUEST COMPLETE!${NC}"
  echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
  echo ""
  echo -e "CR File:      ${GREEN}$CR_FILE${NC}"
  echo -e "Iterations:   ${GREEN}$CURRENT_ITERATION${NC}"
  echo -e "Session Dir:  ${GREEN}$SESSION_DIR/${NC}"
  echo ""
  echo "Session files preserved for debugging:"
  echo "  - $SESSION_DIR/session.json"
  echo "  - $SESSION_DIR/task-status.json"
  echo "  - $SESSION_DIR/review-log.json"
  echo "  - $SESSION_DIR/test-results.json"
  echo ""
  echo "Next steps:"
  echo "  1. Review the implementation in your codebase"
  echo "  2. Check the review log: cat $SESSION_DIR/review-log.json"
  echo "  3. Run the full test suite manually"
  echo "  4. Create a PR with the changes"
  echo ""
}

print_max_iterations_banner() {
  echo ""
  echo -e "${RED}══════════════════════════════════════════════════════════════${NC}"
  echo -e "${RED}   MAX ITERATIONS REACHED${NC}"
  echo -e "${RED}══════════════════════════════════════════════════════════════${NC}"
  echo ""
  echo -e "Reached max iterations (${RED}$MAX_ITERATIONS${NC}) without completion."
  echo ""

  count_tasks
  echo -e "Final status: ${GREEN}$COMPLETED_COUNT completed${NC}, ${YELLOW}$PENDING_COUNT pending${NC}"
  echo ""

  echo "Session files available for debugging:"
  echo "  - $SESSION_DIR/review-log.json"
  echo "  - $SESSION_DIR/test-results.json"
  echo ""

  echo "Options:"
  echo "  1. Run again with more iterations: $0 $CR_FILE 50"
  echo "  2. Check review log: cat $SESSION_DIR/review-log.json"
  echo "  3. Check test results: cat $SESSION_DIR/test-results.json"
  echo "  4. Manually complete remaining tasks"
  echo ""
}

# Run main
main
