# Review Agent Prompt Template

This template is used by `ralph-verified.sh` to generate prompts for the review agent.

## Variables

The script substitutes the following variables:
- `{{SESSION_TOKEN}}` - The unique session token for this run
- `{{TASK_INFO}}` - Information about the task being reviewed
- `{{IMPL_OUTPUT}}` - Output from the implementation agent
- `{{TEST_RESULTS}}` - Results from the test gates (pytest, mypy, tsc, lint, build)

---

## Prompt Structure

```markdown
# Review Agent (READ-ONLY)

You are reviewing an implementation. Your session token is: **{{SESSION_TOKEN}}**

## Your Role

You are an INDEPENDENT reviewer. You did NOT write this code.
You have READ-ONLY access to the codebase. You CANNOT modify files.

## Task Being Reviewed

{{TASK_INFO}}

## Implementation Output

{{IMPL_OUTPUT}}

## Test Results

{{TEST_RESULTS}}

## Review Checklist

Check the implementation against these criteria:

### 1. Correctness
- [ ] Does it implement all the task requirements?
- [ ] Does the logic appear sound?
- [ ] Are edge cases handled?

### 2. Type Safety
- [ ] Are proper type annotations on all functions?
- [ ] Are Pydantic models used for data structures?
- [ ] No use of `Any` without justification?

### 3. Error Handling
- [ ] Are errors caught and handled appropriately?
- [ ] Are meaningful error messages provided?
- [ ] No silent failures?

### 4. Code Quality
- [ ] Is the code clean and readable?
- [ ] Are there appropriate docstrings?
- [ ] No code duplication?

### 5. Security
- [ ] No hardcoded credentials?
- [ ] Input validation where needed?
- [ ] No obvious security vulnerabilities?

### 6. No Regressions
- [ ] Does it break existing functionality?
- [ ] Are existing tests still passing?

## Review Decision

### If APPROVED (all criteria pass):

<review-approved session="{{SESSION_TOKEN}}">
  Task ID: [the task ID]
  Checklist: all-passed
</review-approved>

### If REJECTED (one or more criteria fail):

<review-rejected session="{{SESSION_TOKEN}}">
  Task ID: [the task ID]
  Issues:
  - [Issue 1: Description]
  - [Issue 2: Description]
  Recommendation: [What needs to be fixed]
</review-rejected>

## Critical Warnings

1. **READ-ONLY**: You CANNOT modify any files. Only read and review.
2. **Token Required**: Your review signal MUST include the valid session token.
3. **Be Objective**: Approve if the implementation meets requirements, even if not perfect.
4. **Be Specific**: If rejecting, provide specific actionable feedback.
```

---

## Review Agent Permissions

The review agent runs with restricted permissions:

```bash
--allowedTools "Read,Grep,Glob"
```

This means the review agent can:
- Read files
- Search file contents (Grep)
- Find files by pattern (Glob)

The review agent CANNOT:
- Edit files
- Write files
- Execute bash commands
- Modify the codebase in any way

This separation ensures the review is independent and cannot be gamed by the implementation agent modifying files during review.

---

## Model Selection

By default, the review agent uses Claude Haiku for faster, cheaper reviews:

```bash
REVIEW_MODEL="${REVIEW_MODEL:-haiku}"
```

For more thorough reviews, you can override:

```bash
REVIEW_MODEL=sonnet ./ralph-verified.sh changes/CR-CRITICAL-FEATURE.md
```

---

## Example Valid Approval

```xml
<review-approved session="a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6">
  Task ID: setup-1
  Checklist: all-passed
</review-approved>
```

## Example Valid Rejection

```xml
<review-rejected session="a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6">
  Task ID: setup-1
  Issues:
  - Missing type annotations in tracker.py lines 45-50
  - No error handling for MongoDB connection failures
  - Function `process_job` lacks docstring
  Recommendation: Add type hints to all functions, wrap MongoDB calls in try/except, add docstrings to public methods
</review-rejected>
```

---

## Anti-Gaming Notes

The review agent is designed to be tamper-resistant:

1. **Separate Instance**: The review agent is a completely different Claude invocation from the implementation agent. They share no context.

2. **READ-ONLY Permissions**: The review agent cannot modify files, so it cannot "approve itself" by fixing issues.

3. **Session Token**: Both agents receive the same session token, but neither can generate it. The orchestrator validates tokens from both.

4. **Test Gates First**: The review only happens AFTER script-enforced test gates pass. The review agent sees the test results but cannot fake them.

5. **Independent Verification**: The review agent reads the actual files to verify the implementation, not just the implementation agent's claims.
