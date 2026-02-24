/**
 * 04-qa-workflow.spec.ts
 *
 * Tests for the core Q&A workflow: submitting questions, receiving answers,
 * rating answers, and editing answers.
 *
 * These tests require:
 * - The E2E project to exist (created in 02-project.spec.ts).
 * - The E2E session to exist (created in 03-session.spec.ts).
 *
 * Each test re-loads the project and session from the backend to ensure a
 * consistent state regardless of Playwright worker isolation.
 */
import { test, expect, type Page } from "@playwright/test";
import {
  openProjectManagementSection,
  openSessionManagementSection,
} from "./helpers";

const E2E_PROJECT_NAME = "E2E Frontend Test Project — IP Box";
const E2E_SESSION_NAME = "E2E Senior Session — Frontend Test";

const QA_BLOCK_SELECTOR =
  "div.bg-white.rounded-lg.shadow-md.p-6.border.border-gray-200";

/**
 * Navigate to "/" and load the E2E project + session so question input is enabled.
 */
async function loadProjectAndSession(page: Page): Promise<void> {
  // Ensure Senior role is set first (required for edit/rate actions)
  const headerSeniorBtn = page.locator("header").getByRole("button", { name: "Senior" });
  await headerSeniorBtn.waitFor({ state: "visible" });
  await headerSeniorBtn.click();

  // --- Load project ---
  await openProjectManagementSection(page);
  const projectSelect = page.locator("aside").getByRole("combobox").first();
  await projectSelect.selectOption({ label: E2E_PROJECT_NAME });
  await page.getByRole("button", { name: "Load Project" }).click();
  await expect(
    page.locator("aside").getByText(E2E_PROJECT_NAME)
  ).toBeVisible({ timeout: 10_000 });

  // --- Load session ---
  await openSessionManagementSection(page);

  // The grouped session select uses optgroup labels; match by partial text
  const sessionSelect = page
    .locator("aside")
    .getByRole("combobox")
    .filter({ hasText: "" }); // the session <select>
  // Select by visible text containing the session name
  await page
    .locator("aside select")
    .last()
    .selectOption({ label: new RegExp(E2E_SESSION_NAME) });

  await page.getByRole("button", { name: "Load Session" }).click();

  // Wait for "Current Session" panel to show the session name
  await expect(
    page.locator("aside").getByText(E2E_SESSION_NAME)
  ).toBeVisible({ timeout: 10_000 });
}

test.describe("Q&A workflow", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await loadProjectAndSession(page);
  });

  test("can submit a question and receive an answer", async ({ page }) => {
    const textarea = page.getByPlaceholder(
      "Enter your questions here (one per line or numbered list)..."
    );
    await textarea.waitFor({ state: "visible" });
    await textarea.fill(
      "What are the conditions for applying the IP Box preferential 5% CIT rate in Poland?"
    );

    const submitBtn = page.getByRole("button", { name: "Generate Answers" });
    await submitBtn.click();

    // Wait up to 60s for the LLM to respond — button re-enables when done
    await expect(submitBtn).toBeEnabled({ timeout: 60_000 });

    // At least one Q&A block should appear
    const blocks = page.locator(QA_BLOCK_SELECTOR);
    await expect(blocks.first()).toBeVisible({ timeout: 5_000 });

    // The block should contain non-empty answer text
    await expect(
      blocks.first().locator("p.text-gray-700").first()
    ).not.toBeEmpty();
  });

  test("can submit multiple questions", async ({ page }) => {
    const textarea = page.getByPlaceholder(
      "Enter your questions here (one per line or numbered list)..."
    );
    await textarea.fill(
      "1. What is the IP Box regime?\n2. Who is eligible for IP Box in Poland?\n3. What documentation is required for IP Box?"
    );

    const submitBtn = page.getByRole("button", { name: "Generate Answers" });
    await submitBtn.click();

    // Wait for processing to complete
    await expect(submitBtn).toBeEnabled({ timeout: 90_000 });

    // At least 3 Q&A blocks should be rendered
    const blocks = page.locator(QA_BLOCK_SELECTOR);
    await expect(blocks).toHaveCount(3, { timeout: 10_000 });
  });

  test("can rate an answer as good", async ({ page }) => {
    // First ensure there is at least one Q&A pair — submit a question
    const textarea = page.getByPlaceholder(
      "Enter your questions here (one per line or numbered list)..."
    );
    await textarea.fill("What is the IP Box preferential tax rate?");
    const submitBtn = page.getByRole("button", { name: "Generate Answers" });
    await submitBtn.click();
    await expect(submitBtn).toBeEnabled({ timeout: 60_000 });

    // Find the first Q&A block and click "Good"
    const block = page.locator(QA_BLOCK_SELECTOR).first();
    await block.waitFor({ state: "visible" });

    const goodBtn = block.getByRole("button", { name: "Good" });
    await goodBtn.click();

    // After rating, the button should gain the green active style.
    // We verify by checking for the bg-green-100 class on the button.
    await expect(goodBtn).toHaveClass(/bg-green-100/, { timeout: 10_000 });
  });

  test("can edit an answer", async ({ page }) => {
    // Submit a question to have a Q&A pair to edit
    const textarea = page.getByPlaceholder(
      "Enter your questions here (one per line or numbered list)..."
    );
    await textarea.fill("Briefly describe the IP Box regime.");
    const submitBtn = page.getByRole("button", { name: "Generate Answers" });
    await submitBtn.click();
    await expect(submitBtn).toBeEnabled({ timeout: 60_000 });

    // Find the first Q&A block and click "Edit Answer"
    const block = page.locator(QA_BLOCK_SELECTOR).first();
    await block.waitFor({ state: "visible" });

    await block.getByRole("button", { name: "Edit Answer" }).click();

    // A textarea should appear for editing
    const editTextarea = block.locator("textarea");
    await editTextarea.waitFor({ state: "visible" });

    const newText =
      "Updated answer: IP Box regime under Article 24d of the Polish Corporate Income Tax Act provides a preferential 5% CIT rate on income derived from qualifying intellectual property rights.";
    await editTextarea.fill(newText);

    // Save the edit
    await block.getByRole("button", { name: "Save" }).click();

    // The "Edit Answer" button should reappear once editing is complete
    await block
      .getByRole("button", { name: "Edit Answer" })
      .waitFor({ state: "visible", timeout: 15_000 });

    // An "Edited" badge should appear on the block
    await expect(block.getByText("Edited")).toBeVisible({ timeout: 5_000 });

    // The answer text should reflect the update
    await expect(block.getByText(/Updated answer:/)).toBeVisible();
  });

  test("empty question shows validation error", async ({ page }) => {
    // The "Generate Answers" button is disabled when textarea is empty (disabled prop)
    // We verify this by checking the disabled state
    const submitBtn = page.getByRole("button", { name: "Generate Answers" });
    await expect(submitBtn).toBeDisabled();

    // The textarea is empty — clicking a disabled button does nothing,
    // but we can also try submitting by pressing Enter in the form and
    // verify the error message if the form is submitted programmatically.
    // Because the button is rendered disabled, we verify its state instead.
    await expect(submitBtn).toHaveAttribute("disabled");
  });
});
