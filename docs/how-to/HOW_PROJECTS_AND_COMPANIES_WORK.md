# How Projects and Companies Work

This guide explains how projects organize your work and how company information is captured and used throughout the system. Projects help you organize documents, sessions, and questions around specific clients or cases.

> **Visual Diagram**: A flow diagram showing the project creation and management process is available in Excalidraw. The diagram illustrates project creation, document upload, session creation, and how everything connects together.

## Introduction

Projects are containers that help you organize all your work around a specific client, case, or matter. When you create a project, you can upload documents specific to that project, create sessions linked to it, and ensure that questions are answered using the right set of documents.

## Prerequisites

- Access to the project management features in the application
- Basic understanding of how to navigate the application interface

## What is a Project?

A project represents a specific client engagement, case, or matter you're working on. Think of it as a folder that contains:

- **Documents**: All documents related to this specific project
- **Sessions**: Question-and-answer sessions conducted for this project
- **Company Information**: Details about the client or company involved
- **Project Status**: Where you are in the project workflow

## Creating a New Project

### Step 1: Access Project Management

1. In the left sidebar, find the section labeled **"Project Management"**
2. Look for the **"New Project"** button

### Step 2: Enter Project Details

1. Click **"New Project"**
2. Enter a **Project Name** in the field provided
   - Use a descriptive name that clearly identifies the project (e.g., "Acme Corp Tax Consultation 2025")
3. Optionally, enter **Company Information**:
   - **Company Name**: The official name of the company
   - **Company Context**: Additional details about the company, industry, or situation
4. Click **"Create Project"**

### Step 3: Project Created

After creation, you should see:
- A success message confirming the project was created
- The project appears in your project list
- The project is automatically selected as your current project

## Company Information

### What Company Information is Captured

When you create a project or session, you can provide company information that helps the system understand the context:

#### Structured Company Information

The system automatically extracts structured information when possible:

- **Company Name**: The official name of the company
- **Company Context**: Free-form description of the company, its business, or the situation
- **Additional Details**: Any other relevant information you provide

#### How Company Information is Used

Company information serves several purposes:

1. **Context for Answers**: When answering questions, the system can consider the company's specific situation
2. **Session Organization**: Helps identify which sessions belong to which company
3. **Document Filtering**: Can help filter and organize documents by company
4. **Reporting**: Useful for generating reports and summaries

### Providing Company Information

You can provide company information in two ways:

1. **When Creating a Project**: Enter company details in the project creation form
2. **When Creating a Session**: Add company information when creating a session (this is optional if the project already has company info)

## Project Stages and Workflow

Projects move through different stages to track progress:

### Available Project Stages

1. **Preparation** (`prep_docs`): Initial stage where you're gathering and uploading documents
2. **Document Review** (`review_docs`): Reviewing uploaded documents
3. **Question Preparation** (`prep_questions`): Preparing questions to ask
4. **Question Processing** (`process_questions`): Actively processing questions and getting answers
5. **Answer Review** (`review_answers`): Reviewing and refining answers
6. **Finalization** (`finalize`): Finalizing the project deliverables

### Updating Project Stage

1. Load the project you want to update
2. In the left sidebar, find **"Project Stage"**
3. Under **"Next actions"**, click the button matching your next stage
4. Optionally, add a note explaining the stage change
5. The project stage updates immediately

### Rolling Back Project Stage

If you need to go back to a previous stage:

1. Load the project
2. In the **"Project Stage"** section, use the **"Rollback"** buttons
3. Select the stage you want to return to
4. The project stage history is maintained for audit purposes

## Loading and Selecting Projects

### Loading an Existing Project

1. In **"Project Management"**, open the **"Select Project"** dropdown
2. Choose the project you want to work with
3. Click **"Load Project"**
4. The project becomes your active project

### What Happens When You Load a Project

- The project becomes your **current project**
- Any documents you upload will be linked to this project
- Any sessions you create will be linked to this project
- Searches within sessions will prioritize documents from this project

## Project-Scoped Documents

### Uploading Documents to a Project

1. Load the project you want to add documents to
2. In the left sidebar, find **"Project Uploads"**
3. Click **"Upload Document"**
4. Select a file from your computer (PDF, DOCX, PPTX, etc.)
5. The document is automatically linked to the current project

### Benefits of Project-Scoped Documents

- **Organized Storage**: Documents are clearly associated with specific projects
- **Targeted Searches**: When answering questions in a project's session, the system prioritizes documents from that project
- **Better Context**: The system understands which documents are relevant to which project
- **Easier Management**: You can see all documents for a project in one place

## Project-Scoped Sessions

### Creating Sessions for a Project

1. Load the project you want to create a session for
2. In **"Session Management"**, click **"New Session"**
3. Enter session details (name, user role, company info)
4. Click **"Create Session"**
5. The session is automatically linked to the current project

### Benefits of Project-Scoped Sessions

- **Automatic Linking**: Sessions are automatically associated with the project
- **Document Access**: Sessions can access all documents uploaded to the project
- **Context Preservation**: Company information and project context flow to sessions
- **Organized Work**: All sessions for a project are grouped together

## What Information Gets Stored

### Project-Level Fields

| Field Name | Description | Example |
|-----------|-------------|---------|
| `name` | Project name | "Acme Corp Tax Consultation 2025" |
| `company_info` | Company information dictionary | `{"name": "Acme Corp", "context": "..."}` |
| `stage` | Current project stage | `{"key": "prep_docs", "updated_at": "2025-01-15"}` |
| `stage_history` | History of stage changes | Array of stage change records |
| `created_at` | When project was created | "2025-01-15T10:30:00" |
| `updated_at` | Last update timestamp | "2025-01-15T14:20:00" |

### Company Information Fields

| Field Name | Description | Example |
|-----------|-------------|---------|
| `name` | Company name | "Acme Corporation" |
| `context` | Company description/context | "Manufacturing company specializing in..." |

### Stage History Fields

Each stage change record includes:

- **`at`**: Timestamp of the change
- **`from`**: Previous stage (null for initial creation)
- **`to`**: New stage
- **`event`**: Type of event ("create", "update", "rollback")
- **`note`**: Optional note explaining the change
- **`by`**: Who made the change (if tracked)

## Expected Results

When working with projects, you should see:

- Projects listed in the project management section
- Ability to load and switch between projects
- Documents uploaded to projects appear in project-specific lists
- Sessions created while a project is loaded are linked to that project
- Project stage updates reflect immediately
- Stage history shows all changes over time

## Troubleshooting

### "Please select a project first" Error

- **Cause**: You're trying to create a session or upload a document without a project loaded
- **Solution**: Load a project first using the "Select Project" dropdown, then try again

### Project Not Appearing in List

- **Check creation**: Verify the project was created successfully (look for success message)
- **Refresh**: Try refreshing the project list
- **Permissions**: Ensure you have access to view projects

### Documents Not Appearing in Project

- **Verify project selection**: Make sure you uploaded documents while the correct project was loaded
- **Check upload status**: Verify the document upload completed successfully
- **Project scope**: Documents uploaded without a project selected won't be linked to any project

### Stage Changes Not Reflecting

- **Refresh**: Try refreshing the project information
- **Verify permissions**: Ensure you have permission to update project stages
- **Check stage validity**: Make sure you're moving to a valid next stage

## Additional Information

### Project Organization Best Practices

- **Use Descriptive Names**: Choose project names that clearly identify the client or case
- **Complete Company Information**: Provide as much company context as possible for better answers
- **Update Stages Regularly**: Keep project stages current to track progress accurately
- **Use Notes**: Add notes when changing stages to document important decisions

### Multiple Projects

- You can have multiple projects active at the same time
- Each project maintains its own documents and sessions
- You can switch between projects as needed
- Project data is kept separate and organized

### Project Lifecycle

A typical project lifecycle:

1. **Create Project**: Start a new project with company information
2. **Upload Documents**: Add all relevant documents to the project
3. **Create Sessions**: Create Q&A sessions for the project
4. **Process Questions**: Ask questions and get answers using project documents
5. **Review Answers**: Review and refine answers as needed
6. **Finalize**: Mark project as finalized when complete

### Project vs. Session

Understanding the difference:

- **Project**: A container for all work related to a specific client or case
- **Session**: A specific Q&A session within a project where you ask questions and get answers
- **Relationship**: Projects contain multiple sessions, and sessions belong to one project

## Related Features

- **Document Upload**: Upload documents specifically to projects
- **Session Management**: Create sessions linked to projects
- **Question Processing**: Ask questions using project-scoped documents
- **Answer Review**: Review answers within project context
- **Export Functionality**: Export project sessions and answers

