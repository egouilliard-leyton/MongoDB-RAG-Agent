# How To Use Projects, Upload Documents, and Review Answers

This guide explains how to organize your work into **Projects**, upload documents to a specific project’s knowledge base, and use the built-in **answer review** and **Good/Bad feedback** features.

## Prerequisites

- The application is running (backend + frontend)
- You can access the web interface in your browser
- You have at least one supported file to upload: **PDF**, **DOCX**, or **PPTX**
- If you want to edit answers or rate them, you need to use the **Senior** role

## Step-by-Step Instructions

### 1) Create a Project

1. In the left sidebar, find the section labeled **“Project Management”**.
2. Click **“New Project”**.
3. Type a project name in **“Project Name”**.
4. Click **“Create Project”**.

### 2) Load an Existing Project

1. In **“Project Management”**, open the **“Select Project”** dropdown.
2. Choose your project.
3. Click **“Load Project”**.

### 3) Upload Documents to a Project

1. Load the project (see step 2).
2. In the left sidebar, find **“Project Uploads”**.
3. Click **“Upload Document”**.
4. Select a **PDF**, **DOCX**, or **PPTX** file from your computer.

### 4) Update the Project Stage

1. Load the project.
2. In the left sidebar, find **“Project Stage”**.
3. Under **“Next actions”**, click the button that matches your next step.
4. (Optional) If you need to go back, use the **“Rollback”** buttons.

### 5) Create a Session for the Current Project

1. In the left sidebar, find **“Session Management”**.
2. Click **“New Session”**.
3. Enter a session name in **“Session Name”**.
4. (Optional) Fill **“Company Information”**.
5. Choose a **User Role**:
   - **Junior**: can ask questions, but answers are not saved as Q&A pairs.
   - **Senior**: Q&A pairs are saved, can edit answers, and can rate answers.
6. Click **“Create Session”**.

### 6) Ask Questions

1. In the main page, type one or more questions.
2. Submit the questions.
3. Review the generated answers and citations.

### 7) Mark an Answer as Good or Bad (Senior only)

1. Switch to **Senior** role.
2. In each Q&A block, click **“Good”** or **“Bad”**.
3. Click the same button again to clear the rating (set it back to “not reviewed”).

### 8) Edit an Answer (Senior only)

1. Switch to **Senior** role.
2. Open a Q&A block.
3. Click **“Edit Answer”**.
4. Update the text in the editor.
5. Click **“Save”**.

## Expected Results

When everything is working:

- You can create and load projects from the **Project Management** sidebar section.
- Uploaded documents are ingested and become searchable **only within that project**.
- Sessions created while a project is selected are linked to that project.
- Each answer can show:
  - A **Good/Bad** rating (Senior only)
  - An **Edited** badge if a saved answer was modified
  - A **Review** badge (good / needs info / risk) and a short explanation
- A “what’s missing” **Review summary** can appear above the Q&A list.

## Troubleshooting

- **“Please select a project first” when creating a session**: Load a project in **Project Management** first, then create the session.
- **Upload fails with “Unsupported file type”**: Only **PDF**, **DOCX**, and **PPTX** are accepted.
- **Answers don’t seem project-scoped**: Make sure:
  - The session was created after selecting the project, and
  - Your uploaded documents were ingested successfully.
- **No review shown**: Reviews are generated for **Senior** sessions; if generation fails, the app will still return the answer without blocking.

## Additional Information

- **Project stages** are meant for tracking progress and can be moved forward (or rolled back) from the sidebar.
- **Follow-up sessions** build on the previous round’s Q&A but do not automatically change the parent session outcome.


