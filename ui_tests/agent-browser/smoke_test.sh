#!/bin/bash
# =============================================================================
# Agent-Browser UI Smoke Test Suite
# =============================================================================
# This script performs navigation-based UI smoke testing using the Vercel
# agent-browser CLI. It validates that key UI components are reachable and
# that pages render content (not blank).
#
# Usage:
#   ./smoke_test.sh [--headed] [--url URL]
#
# Options:
#   --headed    Show browser window (for debugging)
#   --url URL   Override base URL (default: http://127.0.0.1:5173)
# =============================================================================

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARTIFACTS_DIR="${SCRIPT_DIR}/artifacts"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RUN_DIR="${ARTIFACTS_DIR}/${TIMESTAMP}"
BASE_URL="${BASE_URL:-http://127.0.0.1:5173}"
HEADED=""
SESSION_NAME="smoke_${TIMESTAMP}"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --headed)
            HEADED="--headed"
            shift
            ;;
        --url)
            BASE_URL="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Initialize results
declare -A TAB_RESULTS
FAILURES=()
OVERALL_STATUS="passed"

# Create run directory
mkdir -p "${RUN_DIR}"

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

# Helper: Run agent-browser command with session
ab() {
    agent-browser --session "${SESSION_NAME}" $HEADED "$@"
}

# Helper: Save snapshot to file
save_snapshot() {
    local name="$1"
    local snapshot_file="${RUN_DIR}/${name}_snapshot.txt"
    ab snapshot > "${snapshot_file}" 2>/dev/null || true
    echo "${snapshot_file}"
}

# Helper: Save screenshot
save_screenshot() {
    local name="$1"
    local screenshot_file="${RUN_DIR}/${name}_screenshot.png"
    ab screenshot "${screenshot_file}" 2>/dev/null || true
    echo "${screenshot_file}"
}

# Helper: Check if element exists in snapshot
element_exists_in_snapshot() {
    local snapshot_file="$1"
    local pattern="$2"
    grep -qi "${pattern}" "${snapshot_file}" 2>/dev/null
}

# Helper: Count visible content elements using eval
count_visible_content() {
    # Use JavaScript to count non-empty text elements in main content
    local result
    result=$(ab eval "
        (() => {
            const main = document.querySelector('main');
            if (!main) return JSON.stringify({count: 0, error: 'No main element found'});
            
            // Get all text nodes and elements with direct text
            const walker = document.createTreeWalker(
                main,
                NodeFilter.SHOW_TEXT,
                {
                    acceptNode: (node) => {
                        const text = node.textContent.trim();
                        if (!text) return NodeFilter.FILTER_REJECT;
                        
                        // Check if visible
                        const parent = node.parentElement;
                        if (!parent) return NodeFilter.FILTER_REJECT;
                        const style = window.getComputedStyle(parent);
                        if (style.display === 'none' || style.visibility === 'hidden') {
                            return NodeFilter.FILTER_REJECT;
                        }
                        return NodeFilter.FILTER_ACCEPT;
                    }
                }
            );
            
            let count = 0;
            let samples = [];
            while (walker.nextNode() && count < 100) {
                const text = walker.currentNode.textContent.trim();
                if (text.length > 0) {
                    count++;
                    if (samples.length < 5) {
                        samples.push(text.substring(0, 50));
                    }
                }
            }
            
            return JSON.stringify({count: count, samples: samples});
        })()
    " --json 2>/dev/null) || echo '{"count": 0, "error": "eval failed"}'
    
    echo "${result}"
}

# Helper: Check if Dashboard page is not blank
check_dashboard_not_blank() {
    local snapshot_file="$1"
    local result_file="${RUN_DIR}/dashboard_content_check.json"
    
    # Check 1: h1 "Dashboard" heading exists
    local has_heading=false
    if element_exists_in_snapshot "${snapshot_file}" 'heading.*Dashboard'; then
        has_heading=true
    fi
    
    # Check 2: Count visible content in main
    local content_result
    content_result=$(count_visible_content)
    local content_count
    # macOS-compatible grep (no -P flag)
    content_count=$(echo "${content_result}" | grep -o '"count":[[:space:]]*[0-9]*' | grep -o '[0-9]*' | head -1 || echo "0")
    
    # Ensure content_count is a number
    if [[ ! "${content_count}" =~ ^[0-9]+$ ]]; then
        content_count=0
    fi
    
    # Check 3: Look for key Dashboard elements
    local has_summary_cards=false
    local has_charts=false
    local has_loading=false
    local has_error=false
    
    if element_exists_in_snapshot "${snapshot_file}" 'Total Projects' || \
       element_exists_in_snapshot "${snapshot_file}" 'Total Sessions' || \
       element_exists_in_snapshot "${snapshot_file}" 'Q&A Pairs' || \
       element_exists_in_snapshot "${snapshot_file}" 'Success Rate'; then
        has_summary_cards=true
    fi
    
    if element_exists_in_snapshot "${snapshot_file}" 'Activity Trends' || \
       element_exists_in_snapshot "${snapshot_file}" 'Region' || \
       element_exists_in_snapshot "${snapshot_file}" 'Industry'; then
        has_charts=true
    fi
    
    if element_exists_in_snapshot "${snapshot_file}" 'Loading dashboard'; then
        has_loading=true
    fi
    
    if element_exists_in_snapshot "${snapshot_file}" 'Failed to load' || \
       element_exists_in_snapshot "${snapshot_file}" 'error'; then
        has_error=true
    fi
    
    # Determine if blank BEFORE writing JSON
    local is_blank=true
    # Dashboard is NOT blank if:
    # - Has heading AND (has content OR is loading)
    # - Content count > 2 (excluding just the heading text)
    if [[ "${has_heading}" == "true" ]] && [[ ${content_count} -ge 2 || "${has_loading}" == "true" ]]; then
        is_blank=false
    fi
    
    # Build result JSON
    cat > "${result_file}" << EOF
{
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "checks": {
        "has_h1_dashboard": ${has_heading},
        "visible_content_count": ${content_count},
        "has_summary_cards": ${has_summary_cards},
        "has_charts": ${has_charts},
        "is_loading": ${has_loading},
        "has_error": ${has_error}
    },
    "content_sample": ${content_result},
    "is_blank": ${is_blank},
    "assertion": "main content visibleTextCount > 0"
}
EOF

    # Return based on is_blank
    if [[ "${is_blank}" == "false" ]]; then
        return 0  # Not blank - success
    else
        return 1  # Blank - failure
    fi
}

# Test: Navigate to app and verify initial load
test_app_loads() {
    log_info "Testing: App loads at ${BASE_URL}"
    
    # Open the URL
    if ! ab open "${BASE_URL}" 2>/dev/null; then
        log_fail "Failed to open ${BASE_URL}"
        return 1
    fi
    
    # Wait for page load
    sleep 2
    
    # Take initial snapshot
    local snapshot_file
    snapshot_file=$(save_snapshot "01_initial_load")
    save_screenshot "01_initial_load"
    
    # Verify Q&A System heading exists
    if element_exists_in_snapshot "${snapshot_file}" 'Q&A System'; then
        log_success "App loads: Q&A System heading found"
        return 0
    else
        log_fail "App loads: Q&A System heading not found"
        return 1
    fi
}

# Test: Click tab and verify it renders
test_tab() {
    local tab_name="$1"
    local tab_number="$2"
    local expected_content="$3"
    
    log_info "Testing: ${tab_name} tab"
    
    # Take before snapshot
    local before_snapshot
    before_snapshot=$(save_snapshot "${tab_number}_${tab_name}_before")
    
    # Click the tab using semantic locator
    if ! ab find role button click --name "${tab_name}" 2>/dev/null; then
        log_fail "${tab_name} tab: Could not click tab button"
        TAB_RESULTS["${tab_name}"]="failed"
        return 1
    fi
    
    # Wait for content to render
    sleep 1
    
    # Take after snapshot
    local after_snapshot
    after_snapshot=$(save_snapshot "${tab_number}_${tab_name}_after")
    save_screenshot "${tab_number}_${tab_name}"
    
    # Verify expected content
    if element_exists_in_snapshot "${after_snapshot}" "${expected_content}"; then
        log_success "${tab_name} tab: Expected content found"
        TAB_RESULTS["${tab_name}"]="passed"
        return 0
    else
        log_fail "${tab_name} tab: Expected content '${expected_content}' not found"
        TAB_RESULTS["${tab_name}"]="failed"
        return 1
    fi
}

# Test: Dashboard specifically - verify not blank
test_dashboard_not_blank() {
    log_info "Testing: Dashboard is not blank"
    
    # Click Dashboard tab
    if ! ab find role button click --name "Dashboard" 2>/dev/null; then
        log_fail "Dashboard: Could not click tab button"
        return 1
    fi
    
    # Wait for content to render (Dashboard may load async data)
    sleep 2
    
    # Take snapshot
    local snapshot_file
    snapshot_file=$(save_snapshot "dashboard_content")
    save_screenshot "dashboard_content"
    
    # Run the not-blank assertion
    if check_dashboard_not_blank "${snapshot_file}"; then
        log_success "Dashboard: Page is NOT blank - content verified"
        TAB_RESULTS["Dashboard-NotBlank"]="passed"
        return 0
    else
        log_fail "Dashboard: Page IS BLANK - assertion failed"
        TAB_RESULTS["Dashboard-NotBlank"]="failed"
        return 1
    fi
}

# Generate JSON failure report
generate_report() {
    local report_file="${RUN_DIR}/smoke_test_report.json"
    local failed_tabs=()
    local passed_tabs=()
    
    for tab in "${!TAB_RESULTS[@]}"; do
        if [[ "${TAB_RESULTS[$tab]}" == "failed" ]]; then
            failed_tabs+=("\"${tab}\"")
        else
            passed_tabs+=("\"${tab}\"")
        fi
    done
    
    # Convert arrays to JSON
    local failed_json="[$(IFS=,; echo "${failed_tabs[*]:-}")]"
    local passed_json="[$(IFS=,; echo "${passed_tabs[*]:-}")]"
    
    # Build failure details
    local failure_details="[]"
    if [[ ${#FAILURES[@]} -gt 0 ]]; then
        failure_details="["
        for i in "${!FAILURES[@]}"; do
            if [[ $i -gt 0 ]]; then
                failure_details+=","
            fi
            failure_details+="\"${FAILURES[$i]}\""
        done
        failure_details+="]"
    fi
    
    # Get list of artifacts
    local snapshots_list=""
    local screenshots_list=""
    snapshots_list=$(ls -1 "${RUN_DIR}"/*_snapshot.txt 2>/dev/null | tr '\n' ',' | sed 's/,$//') || snapshots_list=""
    screenshots_list=$(ls -1 "${RUN_DIR}"/*.png 2>/dev/null | tr '\n' ',' | sed 's/,$//') || screenshots_list=""
    
    cat > "${report_file}" << EOF
{
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "run_id": "${TIMESTAMP}",
    "base_url": "${BASE_URL}",
    "overall_status": "${OVERALL_STATUS}",
    "artifacts_dir": "${RUN_DIR}",
    "results": {
        "passed": ${passed_json},
        "failed": ${failed_json}
    },
    "failures": ${failure_details},
    "artifacts": {
        "snapshots": "${snapshots_list}",
        "screenshots": "${screenshots_list}"
    }
}
EOF

    echo "${report_file}"
}

# Cleanup function
cleanup() {
    log_info "Cleaning up browser session..."
    ab close 2>/dev/null || true
}

# Main execution
main() {
    log_info "=== Agent-Browser UI Smoke Test Suite ==="
    log_info "Base URL: ${BASE_URL}"
    log_info "Artifacts: ${RUN_DIR}"
    echo ""
    
    # Set trap for cleanup
    trap cleanup EXIT
    
    # Test 1: App loads
    if ! test_app_loads; then
        FAILURES+=("App failed to load")
        OVERALL_STATUS="failed"
    fi
    
    # Test 2: Q&A tab (should already be active, but test clicking it)
    if ! test_tab "Q&A" "02" "QuestionInput\|Ask a question\|Type your question"; then
        FAILURES+=("Q&A tab failed")
        OVERALL_STATUS="failed"
    fi
    
    # Test 3: Documents tab
    if ! test_tab "Documents" "03" "Documents\|Upload\|Document List"; then
        FAILURES+=("Documents tab failed")
        OVERALL_STATUS="failed"
    fi
    
    # Test 4: Ingestion tab
    if ! test_tab "Ingestion" "04" "Ingestion\|History\|Dashboard"; then
        FAILURES+=("Ingestion tab failed")
        OVERALL_STATUS="failed"
    fi
    
    # Test 5: Dashboard tab - with strong "not blank" assertion
    if ! test_dashboard_not_blank; then
        FAILURES+=("Dashboard is blank - main content visibleTextCount == 0")
        OVERALL_STATUS="failed"
    fi
    
    echo ""
    log_info "=== Test Summary ==="
    
    # Generate report
    local report_file
    report_file=$(generate_report)
    
    # Print summary
    local passed_count=0
    local failed_count=0
    for tab in "${!TAB_RESULTS[@]}"; do
        if [[ "${TAB_RESULTS[$tab]}" == "passed" ]]; then
            ((passed_count++))
            log_success "  ${tab}: PASSED"
        else
            ((failed_count++))
            log_fail "  ${tab}: FAILED"
        fi
    done
    
    echo ""
    log_info "Results: ${passed_count} passed, ${failed_count} failed"
    log_info "Report: ${report_file}"
    log_info "Artifacts: ${RUN_DIR}"
    
    # Exit with appropriate code
    if [[ "${OVERALL_STATUS}" == "failed" ]]; then
        log_fail "Overall: FAILED"
        exit 1
    else
        log_success "Overall: PASSED"
        exit 0
    fi
}

# Run main
main "$@"
