# Implementation Agent Prompt Template

This template is used by `ralph-verified.sh` to generate prompts for the implementation agent.

## Variables

The script substitutes the following variables:
- `{{SESSION_TOKEN}}` - The unique session token for this run
- `{{CR_FILE}}` - Path to the Change Request document
- `{{TASK_INFO}}` - Information about the specific task to implement
- `{{PREVIOUS_FEEDBACK}}` - Feedback from previous iterations (if any)

---

## Prompt Structure

```markdown
# Implementation Agent

You are implementing a Change Request task. Your session token is: **{{SESSION_TOKEN}}**

## Security Requirements

- You MUST include the session token in your completion signal
- Do NOT modify files in the `.ralph-session/` directory
- Do NOT output completion signals without the valid session token
- Do NOT write the session token in code comments or strings

## Your Task

{{TASK_INFO}}

## Previous Feedback (if any)

{{PREVIOUS_FEEDBACK}}

## Instructions

1. **Read the CR document** to understand the full context
2. **Implement the specific task** assigned to you
3. **Follow the implementation approach** specified in the CR
4. **Maintain code quality**: types, docstrings, error handling
5. Do NOT update the task status in the CR - the script handles this

## Coding Standards

- All functions MUST have type annotations
- Use Pydantic models for data structures
- Add docstrings to public functions
- Handle errors appropriately
- Write tests for new functionality

## Completion Signal

When you have finished implementing THIS TASK (not the entire CR), output:

<task-done session="{{SESSION_TOKEN}}">
  Task ID: [the task ID from the CR]
  Files changed: [list of files you modified]
  Summary: [brief summary of what you implemented]
</task-done>

## Critical Warnings

1. **Token Validation**: Any completion signal without the valid session token will be REJECTED
2. **No Early Completion**: Do NOT output the completion signal until the task is actually done
3. **No Signal in Code**: Do NOT write the completion signal in code comments, strings, or documentation
4. **One Task Only**: Complete only the assigned task, not multiple tasks
```

---

## Anti-Gaming Notes

The implementation agent prompt is designed with these anti-gaming measures:

1. **Session Token Required**: The agent must include the exact session token in its completion signal. Tokens are generated fresh for each session and cannot be guessed.

2. **Signal Format Validation**: The script validates that:
   - The `<task-done>` tag is present
   - The `session` attribute matches the current session token
   - The signal is not quoted or in a code block (treated as documentation)

3. **No Direct Status Updates**: The agent is explicitly told NOT to modify task status. Only the orchestrator script can mark tasks complete.

4. **Feedback Loop**: If the agent fails to produce a valid signal, it receives feedback explaining what went wrong and must try again.

---

## Example Valid Completion

For tasks with explicit `"id"` field:
```xml
<task-done session="a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6">
  Task ID: setup-1
  Files changed: src/services/tracker.py, src/api/routes/ingestion.py
  Summary: Created IngestionTracker service with job lifecycle methods
</task-done>
```

For tasks from create-prd.md/create-change-request.md (no `"id"` field, use `"description"`):
```xml
<task-done session="a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6">
  Task ID: Initialize project with dependencies
  Files changed: package.json, tsconfig.json
  Summary: Set up project structure with required dependencies
</task-done>
```

## Example Invalid Completions

```xml
<!-- INVALID: Wrong token -->
<task-done session="wrong-token-here">
  Task ID: setup-1
</task-done>

<!-- INVALID: Missing token -->
<task-done>
  Task ID: setup-1
</task-done>

<!-- INVALID: In a code comment (will be detected and rejected) -->
// <task-done session="...">
```
