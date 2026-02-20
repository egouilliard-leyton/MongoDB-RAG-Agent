#!/bin/bash

# Ralph CR - Change Request Implementation Loop
# ==============================================
# This script runs Claude Code in a continuous loop to implement a Change Request.
# Each iteration has a fresh context window. It reads the CR document and
# implements tasks one by one until all are complete.
#
# Usage: ./ralph-cr.sh <cr-file> [max_iterations]
# Example: ./ralph-cr.sh changes/CR-DOCUMENT-INGESTION-DASHBOARD.md 30

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Banner
echo -e "${CYAN}"
echo "  ╔═══════════════════════════════════════════════════════════╗"
echo "  ║                                                           ║"
echo "  ║   Ralph CR - Change Request Implementation Loop           ║"
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
  echo "Examples:"
  echo "  $0 changes/CR-DOCUMENT-INGESTION-DASHBOARD.md"
  echo "  $0 changes/CR-DOCUMENT-INGESTION-DASHBOARD.md 50"
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
# Configuration
IMPL_MODEL="${IMPL_MODEL:-claude-opus-4-5-20251101}"
# Timeout per iteration in seconds (default: 30 minutes = 1800 seconds)
CLAUDE_TIMEOUT=${CLAUDE_TIMEOUT:-1800}

# Verify CR file exists
if [ ! -f "$CR_FILE" ]; then
  echo -e "${RED}Error: Change Request file not found: $CR_FILE${NC}"
  echo ""
  echo "Available Change Requests:"
  if [ -d "changes" ]; then
    ls -1 changes/CR-*.md 2>/dev/null || echo "  (none found)"
  else
    echo "  (changes/ directory not found)"
  fi
  exit 1
fi

# Extract CR name from filename
CR_NAME=$(basename "$CR_FILE" .md)
CR_ACTIVITY_FILE="changes/${CR_NAME}-activity.md"

# Create activity log if it doesn't exist
if [ ! -f "$CR_ACTIVITY_FILE" ]; then
  echo -e "${YELLOW}Creating activity log: $CR_ACTIVITY_FILE${NC}"
  cat > "$CR_ACTIVITY_FILE" << EOF
# ${CR_NAME} - Implementation Activity Log

## Current Status
**Last Updated:** $(date '+%Y-%m-%d %H:%M:%S')
**CR File:** ${CR_FILE}
**Status:** In Progress

---

## Implementation Log

<!-- Claude will append entries here as tasks are completed -->
EOF
fi

# Create the implementation prompt
PROMPT=$(cat << 'PROMPT_END'
# Change Request Implementation

You are implementing a Change Request. Your goal is to complete the tasks defined in the CR document.

## Instructions

1. **Read the CR document** to understand what needs to be implemented
2. **Read the activity log** to see what has already been done
3. **Find the next pending task** from the Task List in the CR
4. **Implement that task** following the steps defined
5. **Update the CR document** - change the task status from "pending" to "completed"
6. **Update the activity log** with what you did
7. **Run any relevant tests** to verify the implementation

## Important Rules

- Only work on ONE task per iteration
- Always update the task status in the CR document after completing it
- Always update the activity log with a dated entry
- If you encounter a blocker, mark the task as "blocked" and add a note
- Follow the implementation approach specified in the CR
- Maintain code quality - add types, docstrings, error handling
- Run tests if they exist for the affected code

## Completion Signal

When ALL tasks in the CR are marked as "completed", output exactly:
<promise>CR_COMPLETE</promise>

If there are still pending tasks, do NOT output this signal.

## Files to Read

1. CR Document: CR_FILE_PLACEHOLDER
2. Activity Log: ACTIVITY_FILE_PLACEHOLDER

Start by reading both files, then implement the next pending task.
PROMPT_END
)

# Replace placeholders in prompt
PROMPT="${PROMPT//CR_FILE_PLACEHOLDER/$CR_FILE}"
PROMPT="${PROMPT//ACTIVITY_FILE_PLACEHOLDER/$CR_ACTIVITY_FILE}"

# Display configuration
echo -e "CR File:        ${GREEN}$CR_FILE${NC}"
echo -e "Activity Log:   ${GREEN}$CR_ACTIVITY_FILE${NC}"
echo -e "Max Iterations: ${GREEN}$MAX_ITERATIONS${NC}"
echo -e "Model:          ${GREEN}$IMPL_MODEL${NC}"
echo -e "Timeout/Iter:    ${GREEN}${CLAUDE_TIMEOUT}s${NC} (set CLAUDE_TIMEOUT env var to change)"
echo -e "Completion:     ${GREEN}<promise>CR_COMPLETE</promise>${NC} or all tasks complete"
echo ""

# Show task summary from CR
# Support both "status": "pending" format and "passes": false format
echo -e "${BLUE}Task Summary from CR:${NC}"
passes_true=$(grep -c '"passes":[[:space:]]*true' "$CR_FILE" 2>/dev/null || true)
passes_false=$(grep -c '"passes":[[:space:]]*false' "$CR_FILE" 2>/dev/null || true)
passes_true=$(printf "%s" "${passes_true:-0}" | tr -d '[:space:]')
passes_false=$(printf "%s" "${passes_false:-0}" | tr -d '[:space:]')
[ -z "$passes_true" ] && passes_true=0
[ -z "$passes_false" ] && passes_false=0
if [ "$passes_true" -gt 0 ] || [ "$passes_false" -gt 0 ]; then
  echo -e "  ${GREEN}$passes_true completed${NC}"
  echo -e "  ${YELLOW}$passes_false pending${NC}"
else
  # Fallback to status field format
  grep -E '"status":[[:space:]]*"(pending|completed|in_progress|blocked)"' "$CR_FILE" 2>/dev/null | \
    sed 's/.*"status":[[:space:]]*"\([^"]*\)".*/\1/' | sort | uniq -c | \
    while read count status; do
      case $status in
        pending) echo -e "  ${YELLOW}$count pending${NC}" ;;
        completed) echo -e "  ${GREEN}$count completed${NC}" ;;
        in_progress) echo -e "  ${BLUE}$count in progress${NC}" ;;
        blocked) echo -e "  ${RED}$count blocked${NC}" ;;
      esac
    done
fi
echo ""

echo -e "${YELLOW}Starting in 3 seconds... Press Ctrl+C to abort${NC}"
sleep 3
echo ""

# Main loop
for ((i=1; i<=MAX_ITERATIONS; i++)); do
  echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}"
  echo -e "${BLUE}   Iteration $i of $MAX_ITERATIONS${NC}"
  echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}"
  echo ""

  # Count remaining tasks - support both "passes" and "status" formats
  if grep -q '"passes":' "$CR_FILE" 2>/dev/null; then
    # Note: `grep -c` prints "0" even when it returns exit code 1 (no matches).
    # Using `|| true` avoids capturing "0\n0" on macOS, which breaks numeric comparisons.
    completed_count=$(grep -c '"passes":[[:space:]]*true' "$CR_FILE" 2>/dev/null || true)
    pending_count=$(grep -c '"passes":[[:space:]]*false' "$CR_FILE" 2>/dev/null || true)
  else
    pending_count=$(grep -c '"status":[[:space:]]*"pending"' "$CR_FILE" 2>/dev/null || true)
    completed_count=$(grep -c '"status":[[:space:]]*"completed"' "$CR_FILE" 2>/dev/null || true)
  fi
  completed_count=$(printf "%s" "${completed_count:-0}" | tr -d '[:space:]')
  pending_count=$(printf "%s" "${pending_count:-0}" | tr -d '[:space:]')
  [ -z "$completed_count" ] && completed_count=0
  [ -z "$pending_count" ] && pending_count=0
  echo -e "Tasks: ${GREEN}$completed_count completed${NC}, ${YELLOW}$pending_count pending${NC}"
  echo ""

  # Check if all tasks are already complete (automatic completion detection)
  if [ "$pending_count" -eq 0 ] && [ "$completed_count" -gt 0 ]; then
    echo -e "${GREEN}All tasks are complete!${NC}"
    echo ""
    echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}   CHANGE REQUEST COMPLETE!${NC}"
    echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "CR File:    ${GREEN}$CR_FILE${NC}"
    echo -e "Iterations: ${GREEN}$i${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Review the implementation in your codebase"
    echo "  2. Check $CR_ACTIVITY_FILE for the full implementation log"
    echo "  3. Run the full test suite"
    echo "  4. Update CR status to 'Implemented' if satisfied"
    echo "  5. Create a PR with the changes"
    echo ""
    exit 0
  fi

  # Run Claude with the prompt and timeout
  echo -e "${CYAN}Running Claude (model: $IMPL_MODEL, timeout: ${CLAUDE_TIMEOUT}s)...${NC}"
  result=$(timeout "$CLAUDE_TIMEOUT" claude -p "$PROMPT" --model "$IMPL_MODEL" --output-format text 2>&1) || {
    exit_code=$?
    if [ $exit_code -eq 124 ]; then
      echo -e "${RED}Claude command timed out after ${CLAUDE_TIMEOUT} seconds${NC}"
      echo -e "${YELLOW}This iteration will be skipped. Consider increasing CLAUDE_TIMEOUT.${NC}"
      echo ""
      result=""
    else
      echo -e "${RED}Claude command failed with exit code $exit_code${NC}"
      echo ""
      result=""
    fi
  }

  if [ -n "$result" ]; then
    echo "$result"
    echo ""
  fi

  # Re-count tasks after Claude run (in case it updated the CR file)
  if grep -q '"passes":' "$CR_FILE" 2>/dev/null; then
    completed_count=$(grep -c '"passes":[[:space:]]*true' "$CR_FILE" 2>/dev/null || true)
    pending_count=$(grep -c '"passes":[[:space:]]*false' "$CR_FILE" 2>/dev/null || true)
  else
    pending_count=$(grep -c '"status":[[:space:]]*"pending"' "$CR_FILE" 2>/dev/null || true)
    completed_count=$(grep -c '"status":[[:space:]]*"completed"' "$CR_FILE" 2>/dev/null || true)
  fi
  completed_count=$(printf "%s" "${completed_count:-0}" | tr -d '[:space:]')
  pending_count=$(printf "%s" "${pending_count:-0}" | tr -d '[:space:]')
  [ -z "$completed_count" ] && completed_count=0
  [ -z "$pending_count" ] && pending_count=0

  # Check for completion signal in Claude's output
  # Use grep to find the signal on its own line (not quoted in code/text)
  # The -E enables extended regex, ^ and $ ensure it's a standalone line
  # We also check for the signal with optional leading/trailing whitespace
  if [ -n "$result" ] && echo "$result" | grep -qE '^[[:space:]]*<promise>CR_COMPLETE</promise>[[:space:]]*$'; then
    echo ""
    echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}   CHANGE REQUEST COMPLETE!${NC}"
    echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "CR File:    ${GREEN}$CR_FILE${NC}"
    echo -e "Iterations: ${GREEN}$i${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Review the implementation in your codebase"
    echo "  2. Check $CR_ACTIVITY_FILE for the full implementation log"
    echo "  3. Run the full test suite"
    echo "  4. Update CR status to 'Implemented' if satisfied"
    echo "  5. Create a PR with the changes"
    echo ""
    exit 0
  fi

  # Also check if all tasks are now complete (after Claude's updates)
  if [ "$pending_count" -eq 0 ] && [ "$completed_count" -gt 0 ]; then
    echo -e "${GREEN}All tasks are now complete!${NC}"
    echo ""
    echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}   CHANGE REQUEST COMPLETE!${NC}"
    echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "CR File:    ${GREEN}$CR_FILE${NC}"
    echo -e "Iterations: ${GREEN}$i${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Review the implementation in your codebase"
    echo "  2. Check $CR_ACTIVITY_FILE for the full implementation log"
    echo "  3. Run the full test suite"
    echo "  4. Update CR status to 'Implemented' if satisfied"
    echo "  5. Create a PR with the changes"
    echo ""
    exit 0
  fi

  echo ""
  echo -e "${YELLOW}--- End of iteration $i ---${NC}"
  echo ""

  # Small delay between iterations
  sleep 2
done

echo ""
echo -e "${RED}══════════════════════════════════════════════════════════════${NC}"
echo -e "${RED}   MAX ITERATIONS REACHED${NC}"
echo -e "${RED}══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "Reached max iterations (${RED}$MAX_ITERATIONS${NC}) without completion."
echo ""

# Show remaining tasks
echo -e "${YELLOW}Remaining pending tasks:${NC}"
if grep -q '"passes":' "$CR_FILE" 2>/dev/null; then
  grep -B5 '"passes":[[:space:]]*false' "$CR_FILE" 2>/dev/null | grep '"description"' | \
    sed 's/.*"description":[[:space:]]*"\([^"]*\)".*/  - \1/' | head -5
else
  grep -B5 '"status":[[:space:]]*"pending"' "$CR_FILE" 2>/dev/null | grep '"description"' | \
    sed 's/.*"description":[[:space:]]*"\([^"]*\)".*/  - \1/' | head -5
fi
echo ""

echo "Options:"
echo "  1. Run again with more iterations: $0 $CR_FILE 50"
echo "  2. Check $CR_ACTIVITY_FILE to see progress"
echo "  3. Check $CR_FILE to see remaining tasks"
echo "  4. Manually complete remaining tasks"
echo ""
exit 1
