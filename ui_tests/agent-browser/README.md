# Agent-Browser UI Smoke Tests

This directory contains navigation-based UI smoke tests using the [Vercel agent-browser](https://github.com/vercel-labs/agent-browser) CLI.

## Purpose

These tests validate that key UI components render correctly by:
1. Opening the frontend application
2. Clicking navigation tabs (Q&A, Documents, Ingestion, Dashboard)
3. Asserting that each page renders visible content (not blank)
4. Generating snapshots, screenshots, and a JSON failure report

## Key Test: Dashboard Not Blank

The most critical test validates that the Dashboard tab doesn't render blank:
- Waits for the `h1` "Dashboard" heading
- Counts visible text content in the `<main>` element
- Checks for summary cards (Total Projects, Sessions, etc.)
- Fails if `visibleTextCount < 2` and no loading indicator

## Prerequisites

1. **Node.js** - Required for agent-browser
2. **agent-browser CLI**:
   ```bash
   npm install -g agent-browser
   agent-browser install  # Downloads Chromium
   ```
3. **Frontend running** at `http://127.0.0.1:5173`

## Usage

### Run all smoke tests (headless)

```bash
./run_tests.sh
```

### Run with visible browser (debugging)

```bash
./run_tests.sh --headed
```

### Custom URL

```bash
./run_tests.sh --url http://localhost:3000
```

### Install agent-browser and run

```bash
./run_tests.sh --install
```

## Artifacts

Each test run creates a timestamped directory in `artifacts/`:

```
artifacts/
└── 20260124_143022/
    ├── 01_initial_load_snapshot.txt
    ├── 01_initial_load_screenshot.png
    ├── 02_Q&A_before_snapshot.txt
    ├── 02_Q&A_after_snapshot.txt
    ├── 02_Q&A_screenshot.png
    ├── 03_Documents_after_snapshot.txt
    ├── 03_Documents_screenshot.png
    ├── 04_Ingestion_after_snapshot.txt
    ├── 04_Ingestion_screenshot.png
    ├── dashboard_content_snapshot.txt
    ├── dashboard_content_screenshot.png
    ├── dashboard_content_check.json
    └── smoke_test_report.json
```

### JSON Report Format

`smoke_test_report.json`:
```json
{
    "timestamp": "2026-01-24T14:30:22+00:00",
    "run_id": "20260124_143022",
    "base_url": "http://127.0.0.1:5173",
    "overall_status": "passed",
    "artifacts_dir": "/path/to/artifacts/20260124_143022",
    "results": {
        "passed": ["Q&A", "Documents", "Ingestion", "Dashboard-NotBlank"],
        "failed": []
    },
    "failures": [],
    "artifacts": {
        "snapshots": "/path/to/snapshot1.txt,/path/to/snapshot2.txt",
        "screenshots": "/path/to/screenshot1.png,/path/to/screenshot2.png"
    }
}
```

### Dashboard Content Check

`dashboard_content_check.json`:
```json
{
    "timestamp": "2026-01-24T14:30:25+00:00",
    "checks": {
        "has_h1_dashboard": true,
        "visible_content_count": 42,
        "has_summary_cards": true,
        "has_charts": true,
        "is_loading": false,
        "has_error": false
    },
    "content_sample": {
        "count": 42,
        "samples": ["Dashboard", "Total Projects", "0", "Total Sessions", "0"]
    },
    "is_blank": false,
    "assertion": "main content visibleTextCount > 0"
}
```

## Integration with CI/CD

These tests are designed to be used as part of the post-completion verification pipeline:

1. **Build/runtime health** - Backend and frontend start successfully
2. **agent-browser UI smoke** - Fast triage for UI regressions
3. **Robot Framework UI suite** - Deterministic regression gate

### Fix Loop Behavior

If tests fail:
1. The JSON report identifies which tab/page failed
2. Snapshots and screenshots provide visual context
3. Planning agents can consume the failure report
4. Implementation agents can fix the frontend
5. Tests re-run automatically

## Exit Codes

- `0` - All tests passed
- `1` - One or more tests failed

## Troubleshooting

### "agent-browser not found"

Install agent-browser:
```bash
npm install -g agent-browser
agent-browser install
```

### "Failed to open URL"

Ensure the frontend is running:
```bash
cd frontend && npm run dev
```

### "Dashboard is blank"

The Dashboard page is rendering but has no content. Check:
1. Backend API is running (`/api/dashboard/summary`)
2. `DashboardContext` is loading data
3. Browser console for errors (use `--headed` mode)

### Tests timeout

Increase wait times in `smoke_test.sh` if the app loads slowly:
```bash
# After clicking Dashboard tab
sleep 3  # Increase from 2
```
