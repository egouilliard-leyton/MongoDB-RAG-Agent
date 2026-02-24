/**
 * 07-full-senior-workflow.spec.ts
 *
 * Comprehensive end-to-end test covering the complete senior user workflow:
 *
 *   1. Navigate to "/"
 *   2. Create a new project
 *   3. Create a senior session linked to that project
 *   4. Submit an IP Box question
 *   5. Wait for the answer
 *   6. Rate the answer as "Good"
 *   7. Verify rating was saved (button style changes)
 *   8. Submit a follow-up question
 *   9. Advance the project stage (if possible)
 *  10. Export the session as Markdown
 *  11. Assert no errors occurred at any step
 */
import { test, expect } from "@playwright/test";
import {
  openProjectManagementSection,
  openSessionManagementSection,
} from "./helpers";

const FULL_E2E_PROJECT = "Full E2E Senior Test — IP Box 2025";
const FULL_E2E_SESSION = "Full E2E Senior Session";
const FULL_E2E_COMPANY = "Leyton Poland — Full E2E Test Run";

const QA_BLOCK_SELECTOR =
  "div.bg-white.rounded-lg.shadow-md.p-6.border.border-gray-200";

test("complete senior workflow: create project, session, Q&A, rate, advance stage, export", async ({
  page,
}) => {
  // -------------------------------------------------------------------------
  // Step 1: Navigate to the app
  // -------------------------------------------------------------------------
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Q&A System" })).toBeVisible();

  // -------------------------------------------------------------------------
  // Step 2: Set user role to Senior (header toggle)
  // -------------------------------------------------------------------------
  const headerSeniorBtn = page.locator("header").getByRole("button", { name: "Senior" });
  await headerSeniorBtn.waitFor({ state: "visible" });
  await headerSeniorBtn.click();
  await expect(page.locator("header").getByText("Can edit & save")).toBeVisible();

  // -------------------------------------------------------------------------
  // Step 3: Create a new project
  // -------------------------------------------------------------------------
  await openProjectManagementSection(page);
  await page.getByRole("button", { name: "New Project" }).click();

  const projectDialog = page.locator('[role="dialog"]');
  await projectDialog.waitFor({ state: "visible" });
  await projectDialog.getByLabel("Project Name *").fill(FULL_E2E_PROJECT);
  await projectDialog.getByRole("button", { name: "Create Project" }).click();
  await projectDialog.waitFor({ state: "hidden" });

  // Confirm project is now selected in the sidebar Context section
  await expect(
    page.locator("aside").getByText(FULL_E2E_PROJECT)
  ).toBeVisible({ timeout: 10_000 });

  // -------------------------------------------------------------------------
  // Step 4: Create a senior session linked to the new project
  // -------------------------------------------------------------------------
  await openSessionManagementSection(page);
  await page.getByRole("button", { name: "New Session" }).click();

  const sessionDialog = page.locator('[role="dialog"]');
  await sessionDialog.waitFor({ state: "visible" });
  await expect(sessionDialog.getByText("Create New Session")).toBeVisible();

  // Confirm it shows the correct project linkage
  await expect(sessionDialog.getByText(FULL_E2E_PROJECT)).toBeVisible();

  await sessionDialog.getByLabel("Session Name *").fill(FULL_E2E_SESSION);
  await sessionDialog.getByLabel("Company Information (Optional)").fill(FULL_E2E_COMPANY);

  // Click Senior inside the modal
  await sessionDialog.getByRole("button", { name: "Senior" }).click();

  await sessionDialog.getByRole("button", { name: "Create Session" }).click();
  await sessionDialog.waitFor({ state: "hidden" });

  // Confirm session appears in sidebar
  await openSessionManagementSection(page);
  await expect(
    page.locator("aside").getByText(FULL_E2E_SESSION)
  ).toBeVisible({ timeout: 10_000 });

  // -------------------------------------------------------------------------
  // Step 5: Submit an IP Box question
  // -------------------------------------------------------------------------
  const textarea = page.getByPlaceholder(
    "Enter your questions here (one per line or numbered list)..."
  );
  await textarea.waitFor({ state: "visible" });
  await textarea.fill(
    "What are the conditions for applying the IP Box preferential 5% CIT rate in Poland?"
  );

  const submitBtn = page.getByRole("button", { name: "Generate Answers" });
  await submitBtn.click();

  // -------------------------------------------------------------------------
  // Step 6: Wait for the answer (up to 60 seconds)
  // -------------------------------------------------------------------------
  await expect(submitBtn).toBeEnabled({ timeout: 60_000 });

  // At least one Q&A block must be present
  const firstBlock = page.locator(QA_BLOCK_SELECTOR).first();
  await firstBlock.waitFor({ state: "visible" });

  // -------------------------------------------------------------------------
  // Step 7: Rate the first answer as "Good"
  // -------------------------------------------------------------------------
  const goodBtn = firstBlock.getByRole("button", { name: "Good" });
  await goodBtn.click();

  // Verify rating saved — button gains bg-green-100 class
  await expect(goodBtn).toHaveClass(/bg-green-100/, { timeout: 10_000 });

  // -------------------------------------------------------------------------
  // Step 8: Submit a follow-up question
  // -------------------------------------------------------------------------
  await textarea.fill("What documentation is required to claim IP Box benefits?");
  await submitBtn.click();
  await expect(submitBtn).toBeEnabled({ timeout: 60_000 });

  // Now there should be 2 Q&A blocks
  await expect(page.locator(QA_BLOCK_SELECTOR)).toHaveCount(2, { timeout: 10_000 });

  // -------------------------------------------------------------------------
  // Step 9: Advance the project stage (if quick actions are available)
  // -------------------------------------------------------------------------
  const quickActionsLabel = page.locator("aside").getByText("Quick actions:");
  const hasQuickActions = await quickActionsLabel.isVisible().catch(() => false);

  if (hasQuickActions) {
    const firstQuickAction = page
      .locator("aside")
      .getByText("Quick actions:")
      .locator("..")
      .locator("button")
      .first();
    await firstQuickAction.click();
    // Give the API time to update
    await page.waitForTimeout(2_000);
  } else {
    console.log("No quick actions available — stage transition step skipped.");
  }

  // -------------------------------------------------------------------------
  // Step 10: Export the session as Markdown
  // -------------------------------------------------------------------------
  // Open "Session Details" collapsible section
  const sessionDetailsSectionBtn = page.getByRole("button", {
    name: /Expand Session Details/i,
  });
  const isSessionDetailsCollapsed = await sessionDetailsSectionBtn.isVisible().catch(() => false);
  if (isSessionDetailsCollapsed) {
    await sessionDetailsSectionBtn.click();
  }
  await page
    .getByRole("button", { name: "Export Session" })
    .waitFor({ state: "visible" });

  // Select Markdown format
  await page.locator("aside select[class*='border-gray-300']").selectOption("markdown");

  // Set up download listener and click Export
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export Session" }).click();
  const download = await downloadPromise;

  // -------------------------------------------------------------------------
  // Step 11: Assert no errors — verify download and page state
  // -------------------------------------------------------------------------
  expect(download.suggestedFilename()).toMatch(/\.md$/);

  // No error alerts should be visible anywhere on the page
  const errorAlerts = page.locator('[role="alert"]');
  const errorCount = await errorAlerts.count();
  for (let i = 0; i < errorCount; i++) {
    const alertText = await errorAlerts.nth(i).textContent();
    // Fail if any error alert contains "Error" or "Failed"
    expect(alertText).not.toMatch(/error|failed/i);
  }

  // The "Q&A System" heading should still be visible — app has not crashed
  await expect(page.getByRole("heading", { name: "Q&A System" })).toBeVisible();
});
