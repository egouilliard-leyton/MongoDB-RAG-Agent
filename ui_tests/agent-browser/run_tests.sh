#!/bin/bash
# =============================================================================
# UI Smoke Test Runner
# =============================================================================
# Simple wrapper to run the agent-browser smoke tests.
# Ensures agent-browser is installed before running.
#
# Usage:
#   ./run_tests.sh              # Run in headless mode
#   ./run_tests.sh --headed     # Run with visible browser
#   ./run_tests.sh --help       # Show help
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

show_help() {
    cat << EOF
UI Smoke Test Runner

Usage:
    ./run_tests.sh [OPTIONS]

Options:
    --headed        Show browser window (for debugging)
    --url URL       Override base URL (default: http://127.0.0.1:5173)
    --install       Install agent-browser if not present
    --help          Show this help message

Prerequisites:
    - Node.js (for agent-browser)
    - agent-browser CLI (npm install -g agent-browser)
    - Frontend running at http://127.0.0.1:5173

Examples:
    ./run_tests.sh                           # Run smoke tests headless
    ./run_tests.sh --headed                  # Run with visible browser
    ./run_tests.sh --url http://localhost:3000  # Custom URL

EOF
}

check_agent_browser() {
    if ! command -v agent-browser &> /dev/null; then
        echo -e "${YELLOW}[WARN]${NC} agent-browser not found"
        echo ""
        echo "Install with:"
        echo "  npm install -g agent-browser"
        echo "  agent-browser install"
        echo ""
        return 1
    fi
    return 0
}

install_agent_browser() {
    echo -e "${GREEN}[INFO]${NC} Installing agent-browser..."
    npm install -g agent-browser
    echo -e "${GREEN}[INFO]${NC} Installing Chromium browser..."
    agent-browser install
}

# Parse args
INSTALL=false
ARGS=()

while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            show_help
            exit 0
            ;;
        --install)
            INSTALL=true
            shift
            ;;
        *)
            ARGS+=("$1")
            shift
            ;;
    esac
done

# Install if requested
if [[ "${INSTALL}" == "true" ]]; then
    install_agent_browser
fi

# Check dependencies
if ! check_agent_browser; then
    echo "Run with --install to install agent-browser"
    exit 1
fi

# Run the smoke test
echo -e "${GREEN}[INFO]${NC} Running UI smoke tests..."
echo ""

"${SCRIPT_DIR}/smoke_test.sh" "${ARGS[@]:-}"
