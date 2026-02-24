---
allowed-tools: Bash(uv run pytest:*), Bash(uv run ruff:*), Bash(uv run mypy:*)
description: Run all checks (lint, type check, test)
---

Run comprehensive validation. Execute in sequence:

1. **Lint**:
   ```bash
   uv run ruff check .
   ```

2. **Type check**:
   ```bash
   uv run mypy examples/
   ```

3. **Tests**:
   ```bash
   uv run pytest tests/ -v
   ```

## Report

Summarize results:
- Lint: X errors, Y warnings
- Type check: PASS/FAIL
- Tests: X passed, Y failed

**Overall: PASS or FAIL**
