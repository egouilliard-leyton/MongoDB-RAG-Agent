# Robot Framework Browser UI Tests

This directory contains Robot Framework Browser (Playwright-based) UI smoke tests for the MongoDB-RAG-Agent frontend application.

## What's Covered

| Test | Description | Tags |
|------|-------------|------|
| App Loads And Main Layout Renders | Verifies app loads and Q&A System heading displays | `critical`, `load` |
| Dashboard Tab Is Clickable | Verifies Dashboard navigation tab works | `navigation`, `dashboard` |
| Dashboard Page Is Not Blank | **Critical assertion** - Dashboard renders visible content | `critical`, `dashboard`, `not-blank` |
| Dashboard Shows Summary Cards Or Loading State | Verifies Dashboard shows cards or loading indicator | `dashboard`, `content` |

## Prerequisites

1. **Python environment** with Robot Framework installed:

   ```bash
   pip install robotframework robotframework-browser
   ```

2. **Browser binaries** (one-time setup):

   ```bash
   rfbrowser init
   ```

3. **Frontend running** at `http://127.0.0.1:5173`:

   ```bash
   cd frontend && npm run dev
   ```

## How to Run Locally

### Option 1: Using the runner script (recommended)

```bash
# Run all Robot UI tests
./scripts/run_ui_robot_tests.sh

# Run with visible browser (for debugging)
./scripts/run_ui_robot_tests.sh --headed

# Run specific suite
./scripts/run_ui_robot_tests.sh --suite smoke_dashboard

# Run only critical tests
./scripts/run_ui_robot_tests.sh --tag critical

# Run against different URL
./scripts/run_ui_robot_tests.sh --url http://localhost:3000

# Install browser binaries first
./scripts/run_ui_robot_tests.sh --install
```

### Option 2: Direct robot command

```bash
# From project root
robot --outputdir .ralph-session/ui/robot \
      --variable BASE_URL:http://127.0.0.1:5173 \
      --variable HEADLESS:true \
      ui_tests/robot/
```

## Interpreting Results

After running tests, check these files in `.ralph-session/ui/robot/`:

| File | Purpose |
|------|---------|
| `report.html` | High-level summary with pass/fail status |
| `log.html` | Detailed execution log with screenshots |
| `output.xml` | Machine-readable results (for CI integration) |

Screenshots are saved to `ui_tests/artifacts/robot/`:
- `01_app_loaded.png` - Initial app load
- `02_dashboard_clicked.png` - After clicking Dashboard tab
- `03_dashboard_content.png` - Dashboard content verification
- `FAILURE_*.png` - Screenshots on test failure

## Test Design Principles

1. **Semantic Locators**: Tests use `role=button >> text=Dashboard` instead of brittle CSS selectors
2. **Not-Blank Assertion**: Dashboard test uses JavaScript evaluation to count visible text elements
3. **Graceful States**: Tests accept either loaded content OR loading state as valid
4. **Screenshot Evidence**: Each key step captures a screenshot for debugging

## Adding New Tests

1. Create a new `.robot` file in `ui_tests/robot/`
2. Follow the existing structure with Settings, Variables, Test Cases, and Keywords
3. Use semantic locators where possible
4. Add appropriate tags for filtering

Example test case:

```robot
*** Test Cases ***
My New Feature Works
    [Documentation]    Verify the new feature displays correctly.
    [Tags]    feature    smoke
    
    Click    role=button >> text=My Feature
    Wait For Elements State    text=Expected Content    visible
    Take Screenshot    ${SCREENSHOT_DIR}/my_feature.png
```

## CI Integration

The runner script exits with appropriate exit codes:
- `0` - All tests passed
- `1` - Some tests failed
- Other non-zero - Setup/execution error

For CI pipelines, use the XML output for test reporting:

```yaml
- name: Run Robot UI Tests
  run: ./scripts/run_ui_robot_tests.sh
  continue-on-error: true

- name: Upload Robot Results
  uses: actions/upload-artifact@v3
  with:
    name: robot-results
    path: .ralph-session/ui/robot/
```
