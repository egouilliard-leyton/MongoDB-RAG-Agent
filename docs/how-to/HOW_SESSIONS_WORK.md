# How Sessions Work

This guide explains what sessions are, how they're created, and how they organize your question-and-answer work. Sessions are where you ask questions, receive answers, and manage the Q&A process for a specific project or topic.

> **Visual Diagram**: A flow diagram showing the session lifecycle is available in Excalidraw. The diagram illustrates session creation, the difference between Junior and Senior users, Q&A pair storage, and follow-up session creation.

## Introduction

A session is a container for a set of questions and answers related to a specific project or topic. Think of it as a conversation or consultation session where you ask questions about documents and receive answers with citations. Sessions help organize your work and track the progress of your Q&A activities.

## Prerequisites

- Access to the session management features in the application
- A project created and loaded (recommended, but not always required)
- Understanding of user roles (Junior vs Senior)

## What is a Session?

A session represents a specific Q&A consultation or conversation. Each session contains:

- **Session Name**: A descriptive name identifying the session
- **Questions and Answers**: All Q&A pairs created during the session
- **User Role**: Whether the session is for a Junior or Senior user
- **Company Information**: Context about the company or client (if provided)
- **Project Link**: Association with a specific project (if created within a project)
- **Status**: Current status of the session (active, completed, etc.)
- **Outcome Status**: Final outcome of the session (if determined)

## Creating a New Session

### Step 1: Access Session Management

1. In the left sidebar, find the section labeled **"Session Management"**
2. Look for the **"New Session"** button

### Step 2: Enter Session Details

1. Click **"New Session"**
2. Enter a **Session Name** in the field provided
   - Use a descriptive name (e.g., "Acme Corp Initial Consultation" or "Tax Questions Round 1")
3. Optionally, enter **Company Information**:
   - This can be a company name, description, or any relevant context
   - The system will try to extract structured information automatically
4. Select a **User Role**:
   - **Junior**: For users who ask questions but don't need to save answers
   - **Senior**: For users who need to save, edit, and review answers
5. Ensure a **Project is Selected** (if you want to link the session to a project)
6. Click **"Create Session"**

### Step 3: Session Created

After creation, you should see:
- A success message confirming the session was created
- The session becomes your active session
- You can now start asking questions in this session

## User Roles: Junior vs Senior

### Junior User Role

**Characteristics**:
- Can ask questions and receive answers
- Answers are **NOT saved** to the database as Q&A pairs
- Cannot edit answers
- Cannot rate answers as good or bad
- Answers are temporary and only visible during the session

**Use Cases**:
- Initial exploration of documents
- Quick questions without needing to save answers
- Learning about the system
- Testing document search capabilities

### Senior User Role

**Characteristics**:
- Can ask questions and receive answers
- Answers **ARE saved** to the database as Q&A pairs
- Can edit answers after they're generated
- Can rate answers as good or bad
- Can mark outcome status for Q&A pairs
- Answers persist and can be exported

**Use Cases**:
- Official consultations requiring saved answers
- Work that needs to be reviewed and refined
- Deliverables that will be exported or shared
- Professional consultations with clients

## Session Types

### Regular Sessions

A standard session where you:
- Ask questions
- Receive answers with citations
- (If Senior) Save, edit, and review answers
- Work within a project context (if linked to a project)

### Follow-Up Sessions

Follow-up sessions build on previous sessions:

**What They Are**:
- New sessions that reference previous Q&A work
- Allow you to ask follow-up questions based on earlier answers
- Maintain context from previous rounds

**When to Create One**:
- After reviewing answers from a previous session
- When you need to ask clarifying questions
- When building on previous consultation work

**How They Work**:
1. Create a follow-up session from an existing session
2. The system includes context from previous Q&A pairs
3. New questions can reference and build on previous answers
4. Each follow-up session is a new "round" of questions

## Session Lifecycle

### 1. Creation

- Session is created with a name and user role
- Company information is captured (if provided)
- Session is linked to current project (if one is selected)
- Session status is set to "active"

### 2. Active Use

- Questions are asked and answers are generated
- Q&A pairs are created (for Senior users)
- Answers can be edited and reviewed (for Senior users)
- Session is actively being used

### 3. Review and Refinement

- Answers are reviewed for accuracy
- Answers are edited if needed (Senior users)
- Answers are rated as good or bad (Senior users)
- Outcome status is marked for Q&A pairs

### 4. Completion

- Session can be marked as completed
- Final outcome status can be set for the session
- Session can be exported in various formats
- Follow-up sessions can be created if needed

## Linking Sessions to Projects

### Automatic Linking

When you create a session:
- If a project is currently loaded, the session is automatically linked to that project
- The session can access all documents uploaded to that project
- Searches prioritize documents from the linked project

### Benefits of Project Linking

- **Organized Work**: All sessions for a project are grouped together
- **Document Access**: Sessions can search project-specific documents
- **Context Preservation**: Company information flows from project to session
- **Better Organization**: Easy to see all work related to a specific project

## What Information Gets Stored

### Session-Level Fields

| Field Name | Description | Example |
|-----------|-------------|---------|
| `session_name` | Name of the session | "Acme Corp Initial Consultation" |
| `user_role` | User role for this session | "junior" or "senior" |
| `status` | Current session status | "active", "completed" |
| `outcome_status` | Final outcome (if determined) | "successful", "unsuccessful", null |
| `project_id` | Link to project (if linked) | Object ID reference |
| `created_at` | When session was created | "2025-01-15T10:30:00" |
| `updated_at` | Last update timestamp | "2025-01-15T14:20:00" |

### Session Metadata Fields

| Field Name | Description | Example |
|-----------|-------------|---------|
| `company_info` | Company information dictionary | `{"name": "Acme Corp", "context": "..."}` |
| `round_number` | Round number (1 for regular, 2+ for follow-ups) | 1, 2, 3... |
| `parent_session_id` | Link to parent session (for follow-ups) | Object ID or null |

### Q&A Pair Fields (Stored for Senior Users)

Each Q&A pair includes:

| Field Name | Description |
|-----------|-------------|
| `question` | The question that was asked |
| `original_answer` | The initial answer generated |
| `final_answer` | The final answer (may be edited) |
| `edited_answer` | Edited version (if modified) |
| `citations` | Source documents cited in the answer |
| `question_index` | Order of question in the session |
| `session_id` | Link to the session |
| `outcome_status` | Outcome for this Q&A pair |
| `rating_good` | Good/bad rating (true/false/null) |
| `review` | Review information (if generated) |
| `created_at` | When Q&A pair was created |
| `updated_at` | Last update timestamp |

## Expected Results

When working with sessions, you should see:

- Sessions listed in the session management section
- Ability to create new sessions with names and roles
- Active session displayed prominently
- Questions and answers organized within sessions
- For Senior users: Q&A pairs saved and editable
- For Junior users: Answers visible but not saved
- Ability to switch between sessions
- Follow-up sessions linked to parent sessions

## Troubleshooting

### "Please select a project first" Error

- **Cause**: You're trying to create a session without a project loaded
- **Solution**: Load a project first using "Select Project", then create the session
- **Note**: Some workflows may allow sessions without projects, but linking to projects is recommended

### Session Not Appearing After Creation

- **Check creation**: Verify the session was created successfully (look for success message)
- **Refresh**: Try refreshing the session list
- **Check filters**: Ensure you're not filtering sessions in a way that hides the new one

### Answers Not Being Saved (Senior User)

- **Verify role**: Double-check that you selected "Senior" when creating the session
- **Check session**: Ensure you're working in the correct session
- **Review permissions**: Verify you have permission to save Q&A pairs

### Cannot Edit Answers

- **Check role**: Only Senior users can edit answers
- **Verify session**: Ensure you're in a Senior session
- **Check answer status**: Some answers may not be editable in certain states

### Follow-Up Session Not Showing Previous Context

- **Verify parent**: Ensure the follow-up session was created from the correct parent session
- **Check round number**: Verify the round number is correct (should be 2 or higher)
- **Review Q&A pairs**: Ensure the parent session has Q&A pairs to reference

## Additional Information

### Session Organization Best Practices

- **Use Descriptive Names**: Choose session names that clearly identify the purpose
- **Link to Projects**: Always create sessions within projects for better organization
- **Complete Company Information**: Provide company context for better answers
- **Choose Appropriate Role**: Select Junior for exploration, Senior for official work

### Multiple Sessions

- You can have multiple sessions active
- Each session maintains its own Q&A pairs
- You can switch between sessions as needed
- Sessions are organized by project (if linked)

### Session vs. Project

Understanding the difference:

- **Project**: A container for all work related to a client or case
- **Session**: A specific Q&A conversation within a project
- **Relationship**: Projects contain multiple sessions, sessions belong to one project

### Session Export

Sessions can be exported in multiple formats:

- **Markdown**: Text format with formatting
- **PDF**: Portable document format
- **Word**: Microsoft Word document format

Exports include all Q&A pairs, citations, and session metadata.

### Follow-Up Session Workflow

A typical follow-up workflow:

1. **Create Initial Session**: Ask initial questions and get answers
2. **Review Answers**: Review the answers and identify gaps or follow-up needs
3. **Create Follow-Up Session**: Create a new session linked to the first one
4. **Ask Follow-Up Questions**: Ask questions that build on previous answers
5. **Get Enhanced Answers**: Receive answers that consider previous context
6. **Continue as Needed**: Create additional follow-up rounds if necessary

## Related Features

- **Project Management**: Sessions are organized within projects
- **Question Processing**: Ask questions within sessions
- **Answer Review**: Review and edit answers (Senior users)
- **Export Functionality**: Export sessions with all Q&A pairs
- **Follow-Up Sessions**: Create follow-up sessions building on previous work

