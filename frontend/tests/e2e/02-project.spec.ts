/**
 * 02-project.spec.ts
 *
 * Tests for project creation via the UI modal.
 *
 * The project is created once and its name is stored in a module-level
 * state object so subsequent tests (within this file) can refer to it.
 * Playwright runs tests within a single file sequentially by default.
 */
import { test, expect } from "@playwright/test";
import { openProjectManagementSection } from "./helpers";

// Module-level shared state mutated across tests in this file.
const state: Record<string, string> = {};

const E2E_PROJECT_NAME = "E2E Frontend Test Project — IP Box";

test.describe("Project management", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    // Expand the Project Management section so buttons are accessible
    await openProjectManagementSection(page);
  });

  test("create project via UI", async ({ page }) => {
    // Click "New Project" to open the modal
    await page.getByRole("button", { name: "New Project" }).click();

    // Modal should appear with the title "Create New Project"
    const dialog = page.locator('[role="dialog"]');
    await dialog.waitFor({ state: "visible" });
    await expect(dialog.getByText("Create New Project")).toBeVisible();

    // Fill project name — the Input component renders label "Project Name *"
    // which is linked to the input via htmlFor
    await dialog.getByLabel("Project Name *").fill(E2E_PROJECT_NAME);

    // Submit
    await dialog.getByRole("button", { name: "Create Project" }).click();

    // Modal closes after success
    await dialog.waitFor({ state: "hidden" });

    // Store project name for downstream tests
    state.projectName = E2E_PROJECT_NAME;

    // The sidebar "Context" section should now show the project name because
    // createProject calls loadProject internally via ProjectContext
    await expect(page.locator("aside").getByText(E2E_PROJECT_NAME)).toBeVisible({
      timeout: 10_000,
    });
  });

  test("project appears in sidebar after being created", async ({ page }) => {
    // Navigate fresh — state is in DB, so project should be loadable.
    // The project selector dropdown should contain the project name.
    const select = page.locator("aside select").first();
    await select.waitFor({ state: "visible" });

    // The select contains an option with the project name
    await expect(
      page.locator(`aside option:has-text("${E2E_PROJECT_NAME}")`)
    ).toBeAttached();
  });

  test("fail: empty project name shows validation error", async ({ page }) => {
    // Open modal
    await page.getByRole("button", { name: "New Project" }).click();

    const dialog = page.locator('[role="dialog"]');
    await dialog.waitFor({ state: "visible" });

    // Leave name empty — click Create Project directly
    await dialog.getByRole("button", { name: "Create Project" }).click();

    // Validation error: "Project name is required"
    await expect(
      dialog.getByText("Project name is required")
    ).toBeVisible();

    // Close modal with ESC key
    await page.keyboard.press("Escape");
    await dialog.waitFor({ state: "hidden" });
  });
});
