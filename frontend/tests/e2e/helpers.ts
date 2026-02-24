/**
 * Shared Playwright E2E test helpers for the MongoDB RAG Agent frontend.
 *
 * Covers project creation, session creation, question submission,
 * rating, and answer editing workflows.
 */
import { type Page, expect } from "@playwright/test";

/** Backend base URL (not proxied through Vite). */
const BACKEND_URL = "http://localhost:8000";

/**
 * Verify the backend health endpoint is reachable before proceeding.
 *
 * Args:
 *   page: Playwright Page instance.
 */
export async function waitForBackend(page: Page): Promise<void> {
  const response = await page.request.get(`${BACKEND_URL}/api/system/health`);
  expect(response.status()).toBe(200);
}

/**
 * Open the "Project Management" collapsible section in the sidebar.
 * The section is closed by default, so this expands it when needed.
 *
 * Args:
 *   page: Playwright Page instance.
 */
export async function openProjectManagementSection(page: Page): Promise<void> {
  const sectionBtn = page.getByRole("button", {
    name: /Expand Project Management/i,
  });
  // If the button says "Expand", the section is currently collapsed — click to open
  const isCollapsed = await sectionBtn.isVisible().catch(() => false);
  if (isCollapsed) {
    await sectionBtn.click();
  }
  // Wait for the "New Project" button to be visible inside the section
  await page.getByRole("button", { name: "New Project" }).waitFor({ state: "visible" });
}

/**
 * Open the "Session Management" collapsible section in the sidebar.
 *
 * Args:
 *   page: Playwright Page instance.
 */
export async function openSessionManagementSection(page: Page): Promise<void> {
  const sectionBtn = page.getByRole("button", {
    name: /Expand Session Management/i,
  });
  const isCollapsed = await sectionBtn.isVisible().catch(() => false);
  if (isCollapsed) {
    await sectionBtn.click();
  }
  await page.getByRole("button", { name: "New Session" }).waitFor({ state: "visible" });
}

/**
 * Create a new project via the UI modal.
 *
 * Steps:
 *   1. Expand "Project Management" section in the sidebar.
 *   2. Click "New Project" button.
 *   3. Fill the project name field.
 *   4. Submit the form.
 *   5. Wait for the modal to close.
 *
 * Args:
 *   page: Playwright Page instance.
 *   name: Project name to use.
 */
export async function createProject(page: Page, name: string): Promise<void> {
  await openProjectManagementSection(page);

  // Click "New Project" button
  await page.getByRole("button", { name: "New Project" }).click();

  // Wait for the modal dialog to appear
  const dialog = page.locator('[role="dialog"]');
  await dialog.waitFor({ state: "visible" });
  await expect(dialog.getByText("Create New Project")).toBeVisible();

  // Fill project name — the label is "Project Name *"
  await dialog.getByLabel("Project Name *").fill(name);

  // Submit — button text is "Create Project"
  await dialog.getByRole("button", { name: "Create Project" }).click();

  // Modal should close after success
  await dialog.waitFor({ state: "hidden" });
}

/**
 * Create a new session linked to the currently selected project.
 *
 * Steps:
 *   1. Ensure the user role is set to "senior" first (needed for editing/saving).
 *   2. Expand "Session Management" section.
 *   3. Click "New Session".
 *   4. Fill session name and optional company info.
 *   5. Submit the form.
 *
 * Args:
 *   page: Playwright Page instance.
 *   name: Session name to use.
 *   companyInfo: Optional company information text.
 */
export async function createSeniorSession(
  page: Page,
  name: string,
  companyInfo?: string
): Promise<void> {
  // First set the user role to "Senior" via the header toggle
  // The header UserRoleToggle is always visible on desktop (md:block)
  const seniorBtn = page.locator("header").getByRole("button", { name: "Senior" });
  await seniorBtn.waitFor({ state: "visible" });
  await seniorBtn.click();

  // Expand "Session Management" and click "New Session"
  await openSessionManagementSection(page);
  await page.getByRole("button", { name: "New Session" }).click();

  // Wait for modal
  const dialog = page.locator('[role="dialog"]');
  await dialog.waitFor({ state: "visible" });
  await expect(dialog.getByText("Create New Session")).toBeVisible();

  // Fill session name — label is "Session Name *"
  await dialog.getByLabel("Session Name *").fill(name);

  // Fill company info if provided — label is "Company Information (Optional)"
  if (companyInfo) {
    await dialog.getByLabel("Company Information (Optional)").fill(companyInfo);
  }

  // Set role to Senior inside the session creator form.
  // The UserRoleToggle inside the modal dialog renders two buttons: "Junior" and "Senior"
  await dialog.getByRole("button", { name: "Senior" }).click();

  // Submit
  await dialog.getByRole("button", { name: "Create Session" }).click();

  // Wait for modal to close
  await dialog.waitFor({ state: "hidden" });
}

/**
 * Submit one or more questions and wait for answers to be generated.
 *
 * Steps:
 *   1. Fill the question textarea.
 *   2. Click "Generate Answers".
 *   3. Wait for the button to become enabled again (signals response received).
 *
 * Args:
 *   page: Playwright Page instance.
 *   question: Question text (can include multiple lines for multiple questions).
 */
export async function submitQuestion(
  page: Page,
  question: string
): Promise<void> {
  // The Textarea for questions has a specific placeholder text
  const textarea = page.getByPlaceholder(
    "Enter your questions here (one per line or numbered list)..."
  );
  await textarea.waitFor({ state: "visible" });
  await textarea.fill(question);

  // Click "Generate Answers" button
  const submitBtn = page.getByRole("button", { name: "Generate Answers" });
  await submitBtn.click();

  // Wait for the button to become enabled again — signals the API responded.
  // During processing the button is disabled (isLoading=true). Timeout 60s for LLM calls.
  await expect(submitBtn).toBeEnabled({ timeout: 60_000 });
}

/**
 * Rate an answer (Good or Bad) on the Nth Q&A block (0-indexed).
 *
 * Args:
 *   page: Playwright Page instance.
 *   index: 0-based index of the Q&A block.
 *   good: true for "Good" rating, false for "Bad".
 */
export async function rateAnswer(
  page: Page,
  index: number,
  good: boolean
): Promise<void> {
  // Q&A blocks are rendered as bg-white rounded-lg with border-gray-200
  const blocks = page.locator(
    'div.bg-white.rounded-lg.shadow-md.p-6.border.border-gray-200'
  );
  const block = blocks.nth(index);
  await block.waitFor({ state: "visible" });

  const buttonName = good ? "Good" : "Bad";
  await block.getByRole("button", { name: buttonName }).click();
}

/**
 * Edit an answer on the Nth Q&A block (0-indexed).
 * Requires senior user role to be active.
 *
 * Steps:
 *   1. Find the block.
 *   2. Click "Edit Answer".
 *   3. Clear and fill the textarea with new text.
 *   4. Click "Save".
 *   5. Wait for edit mode to close.
 *
 * Args:
 *   page: Playwright Page instance.
 *   index: 0-based index of the Q&A block.
 *   newText: Replacement answer text.
 */
export async function editAnswer(
  page: Page,
  index: number,
  newText: string
): Promise<void> {
  const blocks = page.locator(
    'div.bg-white.rounded-lg.shadow-md.p-6.border.border-gray-200'
  );
  const block = blocks.nth(index);
  await block.waitFor({ state: "visible" });

  // Click "Edit Answer" to enter edit mode
  await block.getByRole("button", { name: "Edit Answer" }).click();

  // Wait for the textarea to appear in edit mode
  const editTextarea = block.locator("textarea");
  await editTextarea.waitFor({ state: "visible" });

  // Clear and type new text
  await editTextarea.fill(newText);

  // Save
  await block.getByRole("button", { name: "Save" }).click();

  // Wait for the "Edit Answer" button to reappear (signals edit mode closed)
  await block.getByRole("button", { name: "Edit Answer" }).waitFor({
    state: "visible",
    timeout: 15_000,
  });
}
