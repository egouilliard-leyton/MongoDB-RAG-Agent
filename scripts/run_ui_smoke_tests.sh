#!/bin/bash
# =============================================================================
# UI Smoke Test Runner (Project Entry Point)
# =============================================================================
# Convenience script to run agent-browser UI smoke tests from the project root.
#
# Usage:
#   ./scripts/run_ui_smoke_tests.sh              # Run headless
#   ./scripts/run_ui_smoke_tests.sh --headed     # Run with visible browser
#   ./scripts/run_ui_smoke_tests.sh --install    # Install agent-browser first
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
UI_TESTS_DIR="${PROJECT_ROOT}/ui_tests/agent-browser"

# Forward all arguments to the actual runner
exec "${UI_TESTS_DIR}/run_tests.sh" "$@"
