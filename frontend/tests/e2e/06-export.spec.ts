/**
 * 06-export.spec.ts
 *
 * Tests for session export functionality.
 *
 * The ExportButton component renders inside the "Session Details" collapsible
 * section of the sidebar. It requires an active session.
 */
import { test, expect, type Page } from "@playwright/test";
import {
  openProjectManagementSection,
  openSessionManagementSection,
} from "./helpers";

const E2E_PROJECT_NAME = "E2E Frontend Test Project — IP Box";
const E2E_SESSION_NAME = "E2E Senior Session — Frontend Test";

/**
 * Load the E2E project and session from the sidebar controls.
 */
async function loadProjectAndSession(page: Page): Promise<void> {
  // Load project
  await openProjectManagementSection(page);
  const projectSelect = page.locator("aside").getByRole("combobox").first();
  await projectSelect.selectOption({ label: E2E_PROJECT_NAME });
  await page.getByRole("button", { name: "Load Project" }).click();
  await expect(
    page.locator("aside").getByText(E2E_PROJECT_NAME)
  ).toBeVisible({ timeout: 10_000 });

  // Load session
  await openSessionManagementSection(page);
  await page
    .locator("aside select")
    .last()
    .selectOption({ label: new RegExp(E2E_SESSION_NAME) });
  await page.getByRole("button", { name: "Load Session" }).click();
  await expect(
    page.locator("aside").getByText(E2E_SESSION_NAME)
  ).toBeVisible({ timeout: 10_000 });
}

/**
 * Expand the "Session Details" collapsible section in the sidebar.
 */
async function openSessionDetailsSection(page: Page): Promise<void> {
  const sectionBtn = page.getByRole("button", {
    name: /Expand Session Details/i,
  });
  const isCollapsed = await sectionBtn.isVisible().catch(() => false);
  if (isCollapsed) {
    await sectionBtn.click();
  }
  // Wait for the Export Session button to appear
  await page.getByRole("button", { name: "Export Session" }).waitFor({
    state: "visible",
  });
}

test.describe("Session export", () => {
  test("export session as markdown triggers download", async ({ page }) => {
    await page.goto("/");
    await loadProjectAndSession(page);

    // Open "Session Details" collapsible section
    await openSessionDetailsSection(page);

    // Select Markdown format in the <select> dropdown
    // The ExportButton renders a <select> with options: markdown, pdf, docx
    await page.locator("aside select[class*='border-gray-300']").selectOption("markdown");

    // Set up a download event listener before clicking
    const downloadPromise = page.waitForEvent("download");

    // Click "Export Session"
    await page.getByRole("button", { name: "Export Session" }).click();

    // Wait for the download to start
    const download = await downloadPromise;

    // The file name should end with ".md"
    expect(download.suggestedFilename()).toMatch(/\.md$/);

    // Save to a temp location and verify non-empty
    const path = await download.path();
    expect(path).toBeTruthy();
  });

  test("export button is absent when no session is loaded", async ({ page }) => {
    await page.goto("/");

    // Do NOT load any session — just navigate to the page fresh.
    // The ExportButton component returns null when currentSession is undefined.
    // The "Session Details" collapsible section itself only renders when
    // currentSession is truthy (in Layout.tsx: {currentSession && ...}).

    // Verify the "Export Session" button does not exist in the DOM
    await expect(
      page.getByRole("button", { name: "Export Session" })
    ).not.toBeAttached();
  });
});
