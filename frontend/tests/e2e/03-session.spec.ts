/**
 * 03-session.spec.ts
 *
 * Tests for session creation and user role toggle.
 *
 * These tests assume the E2E project created in 02-project.spec.ts is
 * present in the database. Each test navigates to "/" fresh.
 */
import { test, expect } from "@playwright/test";
import {
  openProjectManagementSection,
  openSessionManagementSection,
} from "./helpers";

const E2E_PROJECT_NAME = "E2E Frontend Test Project — IP Box";
const E2E_SESSION_NAME = "E2E Senior Session — Frontend Test";
const E2E_COMPANY_INFO = "Leyton Poland Sp. z o.o., R&D and IP Box consultancy";

/**
 * Helper: select and load the E2E project via the sidebar dropdown.
 */
async function loadE2EProject(page: import("@playwright/test").Page): Promise<void> {
  await openProjectManagementSection(page);

  // Select the project in the dropdown
  const projectSelect = page.locator("aside").getByRole("combobox").first();
  await projectSelect.selectOption({ label: E2E_PROJECT_NAME });

  // Click "Load Project"
  await page.getByRole("button", { name: "Load Project" }).click();

  // Wait for the project name to appear in the Context section of the sidebar
  await expect(
    page.locator("aside").getByText(E2E_PROJECT_NAME)
  ).toBeVisible({ timeout: 10_000 });
}

test.describe("Session management", () => {
  test("create senior session via UI", async ({ page }) => {
    await page.goto("/");

    // Load the E2E project first (session requires a project)
    await loadE2EProject(page);

    // Set user role to Senior in the header
    const headerSeniorBtn = page.locator("header").getByRole("button", { name: "Senior" });
    await headerSeniorBtn.click();
    // Confirm Senior is active (badge text "Can edit & save" visible in header)
    await expect(
      page.locator("header").getByText("Can edit & save")
    ).toBeVisible();

    // Open Session Management section and click "New Session"
    await openSessionManagementSection(page);
    await page.getByRole("button", { name: "New Session" }).click();

    // Modal should appear
    const dialog = page.locator('[role="dialog"]');
    await dialog.waitFor({ state: "visible" });
    await expect(dialog.getByText("Create New Session")).toBeVisible();

    // The modal shows which project it will be linked to
    await expect(dialog.getByText(E2E_PROJECT_NAME)).toBeVisible();

    // Fill session name — label "Session Name *"
    await dialog.getByLabel("Session Name *").fill(E2E_SESSION_NAME);

    // Fill company info — label "Company Information (Optional)"
    await dialog.getByLabel("Company Information (Optional)").fill(E2E_COMPANY_INFO);

    // Click "Senior" inside the UserRoleToggle embedded in the form
    await dialog.getByRole("button", { name: "Senior" }).click();

    // Submit
    await dialog.getByRole("button", { name: "Create Session" }).click();

    // Modal should close
    await dialog.waitFor({ state: "hidden" });

    // The session selector in the sidebar (inside Session Management) should
    // reflect the current session.  The "Current Session" panel in the blue box
    // shows the session name.
    await openSessionManagementSection(page);
    await expect(
      page.locator("aside").getByText(E2E_SESSION_NAME)
    ).toBeVisible({ timeout: 10_000 });
  });

  test("user role toggle switches between Junior and Senior", async ({ page }) => {
    await page.goto("/");

    // Header UserRoleToggle is visible on desktop (md:block)
    const seniorBtn = page.locator("header").getByRole("button", { name: "Senior" });
    const juniorBtn = page.locator("header").getByRole("button", { name: "Junior" });

    // Switch to Senior
    await seniorBtn.click();
    await expect(page.locator("header").getByText("Can edit & save")).toBeVisible();

    // Switch to Junior
    await juniorBtn.click();
    await expect(page.locator("header").getByText("View only")).toBeVisible();

    // Switch back to Senior
    await seniorBtn.click();
    await expect(page.locator("header").getByText("Can edit & save")).toBeVisible();
  });

  test("fail: missing session name shows validation error", async ({ page }) => {
    await page.goto("/");

    // Load the E2E project so the session creator passes the project check
    await loadE2EProject(page);

    await openSessionManagementSection(page);
    await page.getByRole("button", { name: "New Session" }).click();

    const dialog = page.locator('[role="dialog"]');
    await dialog.waitFor({ state: "visible" });

    // Leave session name empty — submit directly
    await dialog.getByRole("button", { name: "Create Session" }).click();

    // Validation error: "Session name is required"
    await expect(dialog.getByText("Session name is required")).toBeVisible();

    // Close modal
    await page.keyboard.press("Escape");
    await dialog.waitFor({ state: "hidden" });
  });
});
