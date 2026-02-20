# UI Test Catalog

This directory contains the UI testing infrastructure for the MongoDB-RAG-Agent frontend application. Tests are integrated into the post-completion verification pipeline in `ralph-verified.sh`.

## Test Suite Overview

| Suite | Tool | Purpose | Speed | CI Gate |
|-------|------|---------|-------|---------|
| **Agent-Browser Smoke** | [Vercel agent-browser](https://github.com/vercel-labs/agent-browser) | Fast triage for UI regressions | ~10s | Phase 2 |
| **Robot Framework** | [robotframework-browser](https://robotframework-browser.org/) | Deterministic regression gate | ~30s | Phase 3 |

## What's Covered

### Navigation Tests
- App loads and main layout renders
- Q&A tab is clickable and displays content
- Documents tab is clickable and displays content
- Ingestion tab is clickable and displays content
- Dashboard tab is clickable and displays content

### Critical "Not Blank" Assertions
- Dashboard page renders visible content (not just HTTP 200)
- Main content area has non-empty text elements
- Summary cards OR loading state are present

### Semantic Locators Used
Tests use stable, semantic locators rather than brittle CSS selectors:
- `role=button >> text=Dashboard` (click Dashboard tab)
- `text=Q&A System` (verify app heading)
- `h1:text("Dashboard")` (verify Dashboard h1)

## Directory Structure

```
ui_tests/
├── README.md                    # This file - UI test catalog
├── agent-browser/               # Agent-browser smoke tests
│   ├── README.md               # Agent-browser specific docs
│   ├── run_tests.sh            # Runner wrapper
│   ├── smoke_test.sh           # Main test script
│   └── artifacts/              # Test artifacts (snapshots, screenshots)
└── robot/                       # Robot Framework tests
    ├── README.md               # Robot Framework specific docs
    └── smoke_dashboard.robot   # Dashboard smoke tests
```

## How to Run Locally

### Prerequisites

1. **Frontend running** at `http://127.0.0.1:5173`:
   ```bash
   cd frontend && npm run dev
   ```

2. **Backend running** at `http://127.0.0.1:8000`:
   ```bash
   uv run uvicorn src.api.main:app --reload
   ```

### Agent-Browser Tests (Fast Triage)

```bash
# Install agent-browser (one-time)
npm install -g agent-browser
agent-browser install

# Run tests
./scripts/run_ui_smoke_tests.sh

# Run with visible browser (debugging)
./scripts/run_ui_smoke_tests.sh --headed
```

### Robot Framework Tests (Regression Gate)

```bash
# Install dependencies (one-time)
pip install robotframework robotframework-browser
rfbrowser init

# Run tests
./scripts/run_ui_robot_tests.sh

# Run with visible browser (debugging)
./scripts/run_ui_robot_tests.sh --headed

# Run specific test by tag
./scripts/run_ui_robot_tests.sh --tag critical
```

## Integration with ralph-verified.sh

The UI tests are automatically run as part of the post-completion verification pipeline:

```
┌─────────────────────────────────────────────────────────────┐
│           POST-COMPLETION VERIFICATION PIPELINE             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Phase 1: Build & Runtime                                   │
│    ├── mypy type checking                                   │
│    ├── TypeScript compilation                               │
│    ├── Frontend build                                       │
│    ├── Backend health check                                 │
│    └── Frontend serving check                               │
│                                                             │
│  Phase 2: Agent-Browser UI Smoke (Fast Triage)              │
│    ├── App loads                                            │
│    ├── Tab navigation works                                 │
│    └── Dashboard not blank assertion                        │
│           │                                                 │
│           └── If FAIL: Plan → Fix → Retest loop             │
│                                                             │
│  Phase 3: Robot Framework (Deterministic Regression Gate)   │
│    ├── App loads and main layout renders                    │
│    ├── Dashboard tab is clickable                           │
│    ├── Dashboard page is not blank                          │
│    └── Dashboard shows summary cards or loading state       │
│           │                                                 │
│           └── If FAIL: Plan → Fix → Retest loop             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `POST_VERIFY` | `1` | Enable/disable post-completion verification |
| `UI_VERIFY_MAX_ITERATIONS` | `10` | Max agent-browser fix loop iterations |
| `ROBOT_VERIFY_MAX_ITERATIONS` | `10` | Max Robot Framework fix loop iterations |

### Example: Run with custom iteration limits

```bash
UI_VERIFY_MAX_ITERATIONS=5 ROBOT_VERIFY_MAX_ITERATIONS=5 ./ralph-verified.sh changes/CR-FEATURE.md
```

## Interpreting Artifacts

### Agent-Browser Artifacts

Located in `.ralph-session/ui/`:

| File | Purpose |
|------|---------|
| `snapshots/*/01_initial_load_snapshot.txt` | Accessibility tree at app load |
| `screens/*/01_initial_load_screenshot.png` | Screenshot at app load |
| `report_*.json` | JSON test report |
| `failures.txt` | Failure summary for fix agents |

### Robot Framework Artifacts

Located in `.ralph-session/ui/robot/`:

| File | Purpose |
|------|---------|
| `report.html` | Human-readable test report |
| `log.html` | Detailed execution log with screenshots |
| `output.xml` | Machine-readable results (for CI) |
| `robot_failures.txt` | Failure summary for fix agents |

## Fix Loop Behavior

When a UI test fails, the verification system automatically:

1. **Captures failure artifacts** (snapshots, screenshots, logs)
2. **Runs a Planning Agent** (read-only) to analyze the failure
3. **Runs an Implementation Agent** to fix the frontend code
4. **Runs Build Verification** to ensure changes compile
5. **Restarts services** and re-runs the tests
6. **Repeats** until tests pass or max iterations reached

### Planning Agent Input

The planning agent receives:
- Failure summary from `failures.txt` or `robot_failures.txt`
- UI snapshots (accessibility trees)
- Screenshots
- Test logs

### Implementation Agent Output

The implementation agent:
- Modifies frontend code in `frontend/src/`
- Ensures TypeScript compiles
- Signals completion with session token

## Adding New UI Tests

### Agent-Browser

Edit `ui_tests/agent-browser/smoke_test.sh` to add new tests:

```bash
# Test: New Feature
test_new_feature() {
    log_info "Testing: New Feature"
    
    ab find role button click --name "New Feature"
    sleep 1
    
    local snapshot_file
    snapshot_file=$(save_snapshot "new_feature")
    save_screenshot "new_feature"
    
    if element_exists_in_snapshot "${snapshot_file}" 'Expected Content'; then
        log_success "New Feature: Expected content found"
        return 0
    else
        log_fail "New Feature: Expected content not found"
        return 1
    fi
}
```

### Robot Framework

Create new `.robot` files in `ui_tests/robot/`:

```robot
*** Test Cases ***
New Feature Works
    [Documentation]    Verify the new feature displays correctly.
    [Tags]    feature    smoke
    
    Click    role=button >> text=New Feature
    Wait For Elements State    text=Expected Content    visible
    Take Screenshot    ${SCREENSHOT_DIR}/new_feature.png
```

## Troubleshooting

### "agent-browser not found"

```bash
npm install -g agent-browser
agent-browser install
```

### "Robot Framework not found"

```bash
pip install robotframework robotframework-browser
rfbrowser init
```

### "Dashboard is blank" failures

1. Check backend API is running: `curl http://127.0.0.1:8000/api/dashboard/summary`
2. Check `DashboardContext` is loading data
3. Use `--headed` mode to see browser console errors
4. Check `frontend/src/pages/Dashboard.tsx` for rendering issues

### Tests timeout

Increase wait times in test scripts or increase iteration limits:

```bash
UI_VERIFY_MAX_ITERATIONS=20 ./ralph-verified.sh changes/CR-FEATURE.md
```

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | All tests passed |
| `1` | One or more tests failed |
| Other | Setup/execution error |
