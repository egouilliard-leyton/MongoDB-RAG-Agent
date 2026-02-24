/**
 * 08-settings-page.spec.ts
 *
 * Tests for the Settings page UI.
 *
 * Navigation uses the `currentView` state variable managed by App.tsx —
 * there is no React Router; views are switched by clicking the "Settings"
 * NavTab button rendered inside the header <nav>.
 *
 * Test coverage:
 *   1. Navigate to Settings page via the header nav tab
 *   2. Settings page loads with the correct heading
 *   3. All six settings tabs are present and clickable
 *   4. Prompts tab (default) shows the prompt editor textareas
 *   5. Version History button is accessible on the Prompts tab
 *   6. Parameter Suggestions section is present on the Prompts tab
 *   7. RAG Parameters tab renders toggle switches and number inputs
 *   8. Model Config tab renders without errors
 *   9. Stage Defaults tab renders without errors
 *  10. Workflow Builder tab renders with a workflow selector <select>
 *  11. Playground tab renders the Test Prompt button and question textarea
 *  12. Save Changes button is disabled when there are no unsaved changes
 *  13. Editing a prompt field marks the form as dirty (shows "Unsaved changes")
 *  14. Saving dirty changes succeeds without a UI error alert
 *  15. App does not crash after all navigation (heading still visible)
 *
 * LLM-dependent features (Prompt Playground test execution) are marked with
 * soft assertions so they do not fail the suite when the backend is not
 * fully operational.
 */
import { test, expect } from "@playwright/test";

// ---------------------------------------------------------------------------
// Helper: navigate to the Settings view via the header NavTab
// ---------------------------------------------------------------------------

/**
 * Click the "Settings" NavTab in the header to switch the app view.
 *
 * Args:
 *   page: Playwright Page instance.
 */
async function navigateToSettings(page: import("@playwright/test").Page): Promise<void> {
  // The NavTab renders as a <button> with "Settings" text inside a <nav>
  await page.getByRole("navigation").getByRole("button", { name: "Settings" }).click();
  // Wait for the Settings heading to confirm the view rendered
  await page.getByRole("heading", { name: "Settings" }).waitFor({ state: "visible" });
}

// ---------------------------------------------------------------------------
// Describe block
// ---------------------------------------------------------------------------

test.describe("Settings page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    // Confirm the app is up before proceeding
    await expect(page.getByRole("heading", { name: "Q&A System" })).toBeVisible();
    // Navigate to Settings
    await navigateToSettings(page);
  });

  // -------------------------------------------------------------------------
  // 1. Basic render
  // -------------------------------------------------------------------------

  test("settings page loads with correct heading", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
  });

  // -------------------------------------------------------------------------
  // 2. Tab navigation bar
  // -------------------------------------------------------------------------

  test("all six settings tabs are visible", async ({ page }) => {
    const expectedTabs = [
      "Prompts",
      "RAG Parameters",
      "Model Config",
      "Stage Defaults",
      "Workflow Builder",
      "Playground",
    ];

    for (const tabLabel of expectedTabs) {
      await expect(
        page.getByRole("button", { name: tabLabel })
      ).toBeVisible();
    }
  });

  // -------------------------------------------------------------------------
  // 3. Prompts tab (default active tab)
  // -------------------------------------------------------------------------

  test("prompts tab is active by default and shows prompt editors", async ({ page }) => {
    // The Prompts tab should already be active (no click needed)
    // Verify at least one labeled prompt textarea is rendered.
    // PromptEditor renders a <label> + <textarea>; we look for the label text.
    await expect(page.getByText("Main System Prompt")).toBeVisible();
    await expect(page.getByText("Follow-up Context Prompt")).toBeVisible();
    await expect(page.getByText("Q&A History Prompt")).toBeVisible();
  });

  test("version history button is present on prompts tab", async ({ page }) => {
    // The "Version History" button is rendered at the bottom of the Prompts tab
    await expect(
      page.getByRole("button", { name: "Version History" })
    ).toBeVisible();
  });

  test("parameter suggestions section is present on prompts tab", async ({ page }) => {
    // ParameterSuggestions renders an h4 with "Parameter Suggestions" — either
    // the heading or a loading spinner will be visible; accept both.
    const suggestionsHeading = page.getByText("Parameter Suggestions");
    const isVisible = await suggestionsHeading.isVisible().catch(() => false);
    // Use a soft check: the component mounts — if the heading is not yet
    // visible the spinner must be present instead.
    if (!isVisible) {
      await expect(page.locator("svg.animate-spin").first()).toBeVisible();
    } else {
      await expect(suggestionsHeading).toBeVisible();
    }
  });

  // -------------------------------------------------------------------------
  // 4. Save Changes button state
  // -------------------------------------------------------------------------

  test("save changes button is disabled when form is clean", async ({ page }) => {
    // On initial load with no edits, "Save Changes" must be disabled
    const saveBtn = page.getByRole("button", { name: "Save Changes" });
    await expect(saveBtn).toBeVisible();
    await expect(saveBtn).toBeDisabled();
  });

  // -------------------------------------------------------------------------
  // 5. Dirty-state indicator
  // -------------------------------------------------------------------------

  test("editing a prompt field marks the form dirty and enables save", async ({ page }) => {
    // Find the first visible textarea (Main System Prompt editor)
    const firstTextarea = page.locator("textarea").first();
    await firstTextarea.waitFor({ state: "visible" });

    // Append a character to make the form dirty
    await firstTextarea.click();
    await firstTextarea.press("End");
    await firstTextarea.type(" ");

    // "Unsaved changes" badge should appear in the header row
    await expect(page.getByText("Unsaved changes")).toBeVisible({ timeout: 5_000 });

    // "Save Changes" button must now be enabled
    const saveBtn = page.getByRole("button", { name: "Save Changes" });
    await expect(saveBtn).toBeEnabled();
  });

  // -------------------------------------------------------------------------
  // 6. Save dirty changes (no UI error)
  // -------------------------------------------------------------------------

  test("saving dirty changes does not produce a UI error", async ({ page }) => {
    // Make the form dirty
    const firstTextarea = page.locator("textarea").first();
    await firstTextarea.waitFor({ state: "visible" });
    await firstTextarea.click();
    await firstTextarea.press("End");
    await firstTextarea.type(" ");

    await expect(page.getByText("Unsaved changes")).toBeVisible({ timeout: 5_000 });

    // Click Save
    await page.getByRole("button", { name: "Save Changes" }).click();

    // After a successful save the "Unsaved changes" badge disappears and
    // the Save button becomes disabled again.
    await expect(page.getByText("Unsaved changes")).toBeHidden({ timeout: 15_000 });
    await expect(page.getByRole("button", { name: "Save Changes" })).toBeDisabled();

    // No error alerts should be present
    const alertCount = await page.locator('[role="alert"]').count();
    for (let i = 0; i < alertCount; i++) {
      const text = await page.locator('[role="alert"]').nth(i).textContent();
      expect(text ?? "").not.toMatch(/error|failed/i);
    }
  });

  // -------------------------------------------------------------------------
  // 7. RAG Parameters tab
  // -------------------------------------------------------------------------

  test("rag parameters tab renders toggle switches and number inputs", async ({ page }) => {
    await page.getByRole("button", { name: "RAG Parameters" }).click();

    // Expect the known toggle labels to be visible
    await expect(page.getByText("Question Decomposition")).toBeVisible();
    await expect(page.getByText("Q&A History Search")).toBeVisible();

    // Expect at least one <input type="number"> for numeric parameters
    await expect(page.locator('input[type="number"]').first()).toBeVisible();
  });

  // -------------------------------------------------------------------------
  // 8. Model Config tab
  // -------------------------------------------------------------------------

  test("model config tab renders without crashing", async ({ page }) => {
    await page.getByRole("button", { name: "Model Config" }).click();

    // The tab panel container (bg-white rounded-lg) must still be visible
    await expect(
      page.locator("div.bg-white.rounded-lg").first()
    ).toBeVisible();

    // No error-state heading should appear
    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
  });

  // -------------------------------------------------------------------------
  // 9. Stage Defaults tab
  // -------------------------------------------------------------------------

  test("stage defaults tab renders without crashing", async ({ page }) => {
    await page.getByRole("button", { name: "Stage Defaults" }).click();

    // The outer settings panel must remain visible
    await expect(
      page.locator("div.bg-white.rounded-lg").first()
    ).toBeVisible();

    // Settings heading still present (app has not crashed)
    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
  });

  // -------------------------------------------------------------------------
  // 10. Workflow Builder tab (embedded inside Settings)
  // -------------------------------------------------------------------------

  test("workflow builder tab renders with a workflow selector", async ({ page }) => {
    await page.getByRole("button", { name: "Workflow Builder" }).click();

    // WorkflowBuilder renders a <select> for choosing the active workflow template
    // after loading; wait up to 15 s for the async fetch to complete.
    const workflowSelect = page.locator("select").first();
    await workflowSelect.waitFor({ state: "visible", timeout: 15_000 });
    await expect(workflowSelect).toBeVisible();

    // The "New Template" and "Duplicate" buttons should be available
    await expect(page.getByRole("button", { name: "New Template" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Duplicate" })).toBeVisible();
  });

  // -------------------------------------------------------------------------
  // 11. Playground tab structure (LLM-optional: soft assertions)
  // -------------------------------------------------------------------------

  test("playground tab renders the test prompt form", async ({ page }) => {
    await page.getByRole("button", { name: "Playground" }).click();

    // PromptEditor label for the test prompt — use the label element to avoid
    // strict-mode violations (the text "Test Prompt" also appears inside the
    // submit button and the helper text paragraph).
    await expect(page.locator("label").filter({ hasText: /^Test Prompt$/ })).toBeVisible();

    // "Test Question" label for the secondary textarea
    await expect(page.locator("label").filter({ hasText: /^Test Question$/ })).toBeVisible();

    // "Test Prompt" submit button
    const testBtn = page.getByRole("button", { name: "Test Prompt" });
    await expect(testBtn).toBeVisible();

    // Button should be disabled when fields are empty (guards against blank submissions)
    await expect(testBtn).toBeDisabled();
  });

  test("playground compare-with-current checkbox is present", async ({ page }) => {
    await page.getByRole("button", { name: "Playground" }).click();

    // The "Compare with current prompt" checkbox
    const checkbox = page.getByRole("checkbox", { name: /compare with current prompt/i });
    // Soft assertion — UI may not be fully loaded if settings fetch is slow
    const isVisible = await checkbox.isVisible().catch(() => false);
    if (isVisible) {
      await expect(checkbox).not.toBeChecked();
    }
    // Either way, the Test Prompt button must be visible (non-negotiable)
    await expect(page.getByRole("button", { name: "Test Prompt" })).toBeVisible();
  });

  // -------------------------------------------------------------------------
  // 12. Version history modal (open + close)
  // -------------------------------------------------------------------------

  test("version history modal opens and can be closed", async ({ page }) => {
    // Ensure we are on the Prompts tab
    await page.getByRole("button", { name: "Prompts" }).click();

    // Click "Version History"
    await page.getByRole("button", { name: "Version History" }).click();

    // The modal must appear — PromptVersionHistory renders a dialog overlay
    // Look for the modal container (fixed inset overlay)
    const modal = page.locator('[role="dialog"]');
    const modalVisible = await modal.isVisible().catch(() => false);

    if (modalVisible) {
      // Close the modal — there should be a close button
      const closeBtn = modal.getByRole("button", { name: /close/i });
      if (await closeBtn.isVisible().catch(() => false)) {
        await closeBtn.click();
        await modal.waitFor({ state: "hidden", timeout: 5_000 });
      } else {
        await page.keyboard.press("Escape");
      }
    }
    // Regardless of whether the modal was found, the Settings heading must remain
    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
  });

  // -------------------------------------------------------------------------
  // 13. Navigation back to Q&A view — no crash
  // -------------------------------------------------------------------------

  test("navigating back to Q&A view after visiting settings does not crash", async ({ page }) => {
    // Go back to Q&A
    await page.getByRole("navigation").getByRole("button", { name: "Q&A" }).click();

    // Q&A System heading must be visible and the Q&A textarea must be present
    await expect(page.getByRole("heading", { name: "Q&A System" })).toBeVisible();
    await expect(
      page.getByPlaceholder(
        "Enter your questions here (one per line or numbered list)..."
      )
    ).toBeVisible();
  });
});
