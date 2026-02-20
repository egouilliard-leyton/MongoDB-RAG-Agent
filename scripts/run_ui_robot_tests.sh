#!/bin/bash
# =============================================================================
# Robot Framework Browser UI Test Runner
# =============================================================================
# This script runs the Robot Framework Browser UI smoke tests for the
# MongoDB-RAG-Agent frontend application.
#
# Prerequisites:
#   - Python environment with robotframework and robotframework-browser
#   - Browser binaries installed via `rfbrowser init`
#   - Frontend running at http://127.0.0.1:5173 (or specify --url)
#
# Usage:
#   ./scripts/run_ui_robot_tests.sh [options]
#
# Options:
#   --url URL       Override base URL (default: http://127.0.0.1:5173)
#   --headed        Run with visible browser (default: headless)
#   --install       Install/initialize Robot Browser before running
#   --suite NAME    Run specific test suite (e.g., smoke_dashboard)
#   --tag TAG       Run tests with specific tag (e.g., critical, dashboard)
#   --help          Show this help message
# =============================================================================

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ROBOT_TESTS_DIR="${PROJECT_ROOT}/ui_tests/robot"
OUTPUT_DIR="${PROJECT_ROOT}/.ralph-session/ui/robot"
BASE_URL="${BASE_URL:-http://127.0.0.1:5173}"
HEADLESS="true"
INSTALL_BROWSER="false"
SUITE=""
TAG=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Show help
show_help() {
    head -30 "$0" | tail -25
    exit 0
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --url)
            BASE_URL="$2"
            shift 2
            ;;
        --headed)
            HEADLESS="false"
            shift
            ;;
        --install)
            INSTALL_BROWSER="true"
            shift
            ;;
        --suite)
            SUITE="$2"
            shift 2
            ;;
        --tag)
            TAG="$2"
            shift 2
            ;;
        --help|-h)
            show_help
            ;;
        *)
            log_warn "Unknown option: $1"
            shift
            ;;
    esac
done

# Create output directory
mkdir -p "${OUTPUT_DIR}"
mkdir -p "${PROJECT_ROOT}/ui_tests/artifacts/robot"

log_info "=== Robot Framework Browser UI Tests ==="
log_info "Base URL: ${BASE_URL}"
log_info "Headless: ${HEADLESS}"
log_info "Output: ${OUTPUT_DIR}"
echo ""

# Check if Robot Framework is installed
if ! command -v robot &> /dev/null; then
    log_fail "Robot Framework not found. Install with: pip install robotframework robotframework-browser"
    exit 1
fi

# Check/install Browser library
if [[ "${INSTALL_BROWSER}" == "true" ]]; then
    log_info "Installing Robot Framework Browser library..."
    rfbrowser init
fi

# Verify rfbrowser is available
if ! command -v rfbrowser &> /dev/null; then
    log_warn "rfbrowser command not found. Attempting to initialize..."
    if python -c "from Browser import Browser" 2>/dev/null; then
        log_info "Browser library found, initializing browsers..."
        rfbrowser init || {
            log_fail "Failed to initialize rfbrowser. Run: rfbrowser init"
            exit 1
        }
    else
        log_fail "robotframework-browser not installed. Run: pip install robotframework-browser && rfbrowser init"
        exit 1
    fi
fi

# Build robot command
ROBOT_CMD="robot"
ROBOT_ARGS=(
    "--outputdir" "${OUTPUT_DIR}"
    "--variable" "BASE_URL:${BASE_URL}"
    "--variable" "HEADLESS:${HEADLESS}"
    "--loglevel" "INFO"
    "--timestampoutputs"
    "--consolecolors" "on"
)

# Add suite filter if specified
if [[ -n "${SUITE}" ]]; then
    ROBOT_ARGS+=("--suite" "${SUITE}")
fi

# Add tag filter if specified
if [[ -n "${TAG}" ]]; then
    ROBOT_ARGS+=("--include" "${TAG}")
fi

# Add test directory
ROBOT_ARGS+=("${ROBOT_TESTS_DIR}")

# Run tests
log_info "Running Robot Framework tests..."
echo ""

set +e  # Don't exit on test failure
${ROBOT_CMD} "${ROBOT_ARGS[@]}"
EXIT_CODE=$?
set -e

echo ""
log_info "=== Test Results ==="

# Check results
if [[ ${EXIT_CODE} -eq 0 ]]; then
    log_success "All UI tests passed!"
else
    log_fail "Some UI tests failed (exit code: ${EXIT_CODE})"
fi

# Show output locations
log_info "Reports available at:"
log_info "  - ${OUTPUT_DIR}/report.html"
log_info "  - ${OUTPUT_DIR}/log.html"
log_info "  - ${OUTPUT_DIR}/output.xml"

# List screenshots if any
if ls "${PROJECT_ROOT}/ui_tests/artifacts/robot/"*.png 1> /dev/null 2>&1; then
    log_info "Screenshots:"
    ls -la "${PROJECT_ROOT}/ui_tests/artifacts/robot/"*.png 2>/dev/null || true
fi

exit ${EXIT_CODE}
