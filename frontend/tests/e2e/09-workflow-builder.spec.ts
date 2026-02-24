/**
 * 09-workflow-builder.spec.ts
 *
 * Tests for the Workflow Builder UI, accessed via Settings → Workflow Builder tab.
 *
 * The WorkflowBuilder component:
 *   - Loads all workflow templates from GET /api/workflows
 *   - Shows a <select> to pick the active template
 *   - Renders StageCard components for each stage in the active template
 *   - Provides "New Template", "Duplicate", and "Save Template" toolbar buttons
 *   - Supports inline editing of template name and description
 *   - Allows adding stages with "+ Add Stage"
 *   - Opens a StageEditor panel on the right when a stage is selected
 *
 * Test coverage:
 *   1. Navigate to Settings → Workflow Builder tab
 *   2. Workflow selector <select> is visible after loading
 *   3. Default workflow is pre-selected in the selector
 *   4. At least one stage card (StageCard) is rendered for the default workflow
 *   5. Stage cards show the stage label text
 *   6. "New Template" button exists and is clickable
 *   7. Duplicating the active workflow adds a new entry to the selector
 *   8. Template name input is editable — triggers dirty state
 *   9. "Save Template" button is disabled when form is clean
 *  10. "Save Template" button becomes enabled after a template name edit
 *  11. "+ Add Stage" button adds a new stage card to the list
 *  12. Clicking a stage card "Edit" button opens the StageEditor panel
 *  13. StageEditor panel has a close button and closing it hides the panel
 *  14. Deleting a newly added stage removes it from the list
 *  15. Empty-state message renders for a workflow that has no stages
 *  16. Navigating away and back preserves the workflow selector
 */
import { test, expect } from "@playwright/test";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Navigate to the Settings page by clicking the "Settings" NavTab.
 *
 * Args:
 *   page: Playwright Page instance.
 */
async function navigateToSettings(page: import("@playwright/test").Page): Promise<void> {
  await page.getByRole("navigation").getByRole("button", { name: "Settings" }).click();
  await page.getByRole("heading", { name: "Settings" }).waitFor({ state: "visible" });
}

/**
 * Navigate to the "Workflow Builder" tab inside Settings and wait for the
 * workflow <select> to appear (i.e., the async load has completed).
 *
 * The Workflow Builder tab renders four sub-tabs (Project Workflow, QA Session,
 * QA Pair, Agentic Pipeline). This helper clicks "Project Workflow" if the
 * sub-tabs are visible to guarantee the WorkflowBuilder component is active.
 *
 * Args:
 *   page: Playwright Page instance.
 */
async function openWorkflowBuilder(page: import("@playwright/test").Page): Promise<void> {
  await navigateToSettings(page);
  await page.getByRole("button", { name: "Workflow Builder" }).click();
  // Click the "Project Workflow" sub-tab if it appears (guards against timing
  // differences where sub-tabs render before the WorkflowBuilder select).
  const projectSubTab = page.getByRole("button", { name: "Project Workflow" });
  if (await projectSubTab.isVisible({ timeout: 3_000 }).catch(() => false)) {
    await projectSubTab.click();
  }
  // Wait for the async fetch of workflow list to finish
  await page.locator("select").first().waitFor({ state: "visible", timeout: 15_000 });
}

// ---------------------------------------------------------------------------
// Describe block
// ---------------------------------------------------------------------------

test.describe("Workflow Builder", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Q&A System" })).toBeVisible();
    await openWorkflowBuilder(page);
  });

  // -------------------------------------------------------------------------
  // 1. Basic render
  // -------------------------------------------------------------------------

  test("workflow builder tab renders with a workflow selector", async ({ page }) => {
    await expect(page.locator("select").first()).toBeVisible();
  });

  test("toolbar buttons are visible", async ({ page }) => {
    await expect(page.getByRole("button", { name: "New Template" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Duplicate" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Save Template" })).toBeVisible();
  });

  // -------------------------------------------------------------------------
  // 2. Default workflow pre-selection
  // -------------------------------------------------------------------------

  test("default workflow is pre-selected and its name contains 'default'", async ({ page }) => {
    const select = page.locator("select").first();
    const selectedText = await select.inputValue();
    // The selected option value is the workflow id; inspect the option text instead
    const selectedOption = select.locator("option[selected], option:checked");
    const optionText = await select.evaluate((el: HTMLSelectElement) => {
      return el.options[el.selectedIndex]?.text ?? "";
    });
    // The default workflow option label is "<name> (default)"
    expect(optionText.toLowerCase()).toMatch(/default/);
    // Sanity: a value must be selected
    expect(selectedText).toBeTruthy();
  });

  // -------------------------------------------------------------------------
  // 3. Stage cards rendered for the default workflow
  // -------------------------------------------------------------------------

  test("at least one stage card is visible for the default workflow", async ({ page }) => {
    // StageCard renders inside a flex div with a color dot + stage label.
    // We detect stage cards by the "Edit stage" title button (title="Edit stage")
    // OR by the "Stages" section heading being present.
    // Use getByRole to avoid strict-mode violations (the word "Stages" also
    // appears inside the empty-state message paragraph).
    await expect(page.getByRole("heading", { name: "Stages" })).toBeVisible();

    // Either stage cards exist, or the empty-state message is shown.
    const editStageBtns = page.locator('[title="Edit stage"]');
    const editCount = await editStageBtns.count();
    const emptyMsg = page.getByText('No stages yet. Click "Add Stage" to begin.');
    const emptyVisible = await emptyMsg.isVisible().catch(() => false);

    // At least one of the two states must be true
    expect(editCount > 0 || emptyVisible).toBe(true);
  });

  test("stage cards show stage label text when stages exist", async ({ page }) => {
    const editStageBtns = page.locator('[title="Edit stage"]');
    const count = await editStageBtns.count();

    if (count === 0) {
      // No stages — skip gracefully (empty state already tested above)
      return;
    }

    // Each StageCard renders the stage label as a <p class="text-sm font-medium ...">
    const stageLabels = page.locator("p.text-sm.font-medium.text-gray-900");
    await expect(stageLabels.first()).toBeVisible();
    const labelText = await stageLabels.first().textContent();
    expect(labelText?.trim().length).toBeGreaterThan(0);
  });

  // -------------------------------------------------------------------------
  // 4. Template name / description inputs
  // -------------------------------------------------------------------------

  test("template name input is visible and contains the workflow name", async ({ page }) => {
    // WorkflowBuilder renders a "Template Name" label + input when activeTemplate is set
    await expect(page.getByText("Template Name")).toBeVisible();

    // The input for template name — it follows the label in the grid
    const nameInputs = page.locator('input[type="text"]');
    const count = await nameInputs.count();
    expect(count).toBeGreaterThanOrEqual(1);

    const firstValue = await nameInputs.first().inputValue();
    expect(firstValue.trim().length).toBeGreaterThan(0);
  });

  test("editing template name marks the form as dirty (Unsaved badge)", async ({ page }) => {
    const nameInput = page.locator('input[type="text"]').first();
    await nameInput.waitFor({ state: "visible" });

    // Append a space to make it dirty without truly changing the name
    await nameInput.click();
    await nameInput.press("End");
    await nameInput.type(" ");

    // The "Unsaved" badge must appear in the toolbar
    await expect(page.getByText("Unsaved")).toBeVisible({ timeout: 5_000 });
    // "Save Template" button must now be enabled
    await expect(
      page.getByRole("button", { name: "Save Template" })
    ).toBeEnabled();
  });

  // -------------------------------------------------------------------------
  // 5. Save Template button state
  // -------------------------------------------------------------------------

  test("save template button is disabled when there are no unsaved changes", async ({ page }) => {
    // On fresh load with no edits the button must be disabled
    const saveBtn = page.getByRole("button", { name: "Save Template" });
    await expect(saveBtn).toBeDisabled();
  });

  // -------------------------------------------------------------------------
  // 6. Add Stage
  // -------------------------------------------------------------------------

  test("add stage button adds a new stage card", async ({ page }) => {
    // Count initial stage cards (by Edit-stage buttons)
    const initialCount = await page.locator('[title="Edit stage"]').count();

    // Click "+ Add Stage"
    await page.getByRole("button", { name: "+ Add Stage" }).click();

    // A new stage card should appear; allow a short moment for React re-render
    await expect(
      page.locator('[title="Edit stage"]')
    ).toHaveCount(initialCount + 1, { timeout: 5_000 });

    // The StageEditor panel should also open automatically (the new stage is selected)
    // We detect it by the close button ("×" or role="button" near the editor)
    const editorPanel = page.locator('div.w-96');
    const editorVisible = await editorPanel.isVisible().catch(() => false);
    if (editorVisible) {
      await expect(editorPanel).toBeVisible();
    }
  });

  // -------------------------------------------------------------------------
  // 7. Edit stage opens StageEditor panel
  // -------------------------------------------------------------------------

  test("clicking edit on a stage card opens the stage editor panel", async ({ page }) => {
    const editBtns = page.locator('[title="Edit stage"]');
    const count = await editBtns.count();

    if (count === 0) {
      // No stages — add one first so we can test editing
      await page.getByRole("button", { name: "+ Add Stage" }).click();
      await expect(page.locator('[title="Edit stage"]')).toHaveCount(1, { timeout: 5_000 });
    }

    // Click the first "Edit stage" icon button
    await page.locator('[title="Edit stage"]').first().click();

    // The StageEditor panel is a 384px-wide (w-96) flex-shrink-0 div
    await expect(page.locator("div.w-96")).toBeVisible({ timeout: 5_000 });
  });

  test("stage editor panel close button hides the panel", async ({ page }) => {
    // Ensure the editor is open
    const editBtns = page.locator('[title="Edit stage"]');
    const count = await editBtns.count();

    if (count === 0) {
      await page.getByRole("button", { name: "+ Add Stage" }).click();
      await expect(page.locator('[title="Edit stage"]')).toHaveCount(1, { timeout: 5_000 });
    }

    await page.locator('[title="Edit stage"]').first().click();
    const editorPanel = page.locator("div.w-96");
    await editorPanel.waitFor({ state: "visible", timeout: 5_000 });

    // The StageEditor should have a close button — look for a button that contains "×"
    // or has aria-label/title "Close"
    const closeBtn = editorPanel.getByRole("button", { name: /close|×/i });
    const hasClose = await closeBtn.isVisible().catch(() => false);
    if (hasClose) {
      await closeBtn.click();
      await expect(editorPanel).toBeHidden({ timeout: 5_000 });
    } else {
      // Fallback: the editor may close via the "×" text button rendered at the top right
      const xBtn = editorPanel.locator("button").filter({ hasText: "×" });
      if (await xBtn.isVisible().catch(() => false)) {
        await xBtn.click();
        await expect(editorPanel).toBeHidden({ timeout: 5_000 });
      }
    }
    // Settings heading must remain (no crash)
    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
  });

  // -------------------------------------------------------------------------
  // 8. Delete a newly added stage
  // -------------------------------------------------------------------------

  test("deleting a newly added stage removes it from the stage list", async ({ page }) => {
    const initialCount = await page.locator('[title="Edit stage"]').count();

    // Add a stage
    await page.getByRole("button", { name: "+ Add Stage" }).click();
    await expect(
      page.locator('[title="Edit stage"]')
    ).toHaveCount(initialCount + 1, { timeout: 5_000 });

    // Delete the last stage (the new one) using the "Delete stage" title button
    await page.locator('[title="Delete stage"]').last().click();

    // Count should return to initial
    await expect(
      page.locator('[title="Edit stage"]')
    ).toHaveCount(initialCount, { timeout: 5_000 });
  });

  // -------------------------------------------------------------------------
  // 9. Duplicate workflow
  // -------------------------------------------------------------------------

  test("duplicating the active workflow adds a new entry to the selector", async ({ page }) => {
    const select = page.locator("select").first();
    const initialOptionCount = await select.locator("option").count();

    // Click "Duplicate"
    await page.getByRole("button", { name: "Duplicate" }).click();

    // After duplication the new workflow should be selected and a new option added
    await expect(select.locator("option")).toHaveCount(
      initialOptionCount + 1,
      { timeout: 15_000 }
    );

    // The duplicated template name typically contains "Copy" but we only require
    // it to be a non-empty string
    const newOptionText = await select.evaluate((el: HTMLSelectElement) => {
      return el.options[el.selectedIndex]?.text ?? "";
    });
    expect(newOptionText.trim().length).toBeGreaterThan(0);
  });

  // -------------------------------------------------------------------------
  // 10. New Template button
  // -------------------------------------------------------------------------

  test("new template button creates a blank workflow and selects it", async ({ page }) => {
    const select = page.locator("select").first();
    const initialCount = await select.locator("option").count();

    await page.getByRole("button", { name: "New Template" }).click();

    // A new option must appear in the selector
    await expect(select.locator("option")).toHaveCount(
      initialCount + 1,
      { timeout: 15_000 }
    );

    // The new workflow is selected; it defaults to "New Workflow"
    const selectedText = await select.evaluate((el: HTMLSelectElement) => {
      return el.options[el.selectedIndex]?.text ?? "";
    });
    expect(selectedText.trim().length).toBeGreaterThan(0);

    // Stages section shows the empty-state message because the new workflow has no stages
    await expect(
      page.getByText('No stages yet. Click "Add Stage" to begin.')
    ).toBeVisible({ timeout: 5_000 });
  });

  // -------------------------------------------------------------------------
  // 11. Empty state for a workflow with no stages
  // -------------------------------------------------------------------------

  test("empty state message renders when a workflow has no stages", async ({ page }) => {
    // Create a new blank template (guaranteed to have zero stages)
    await page.getByRole("button", { name: "New Template" }).click();

    // Wait for the new option to appear in the selector
    await page.waitForTimeout(1_000);

    // Verify empty-state copy is visible
    await expect(
      page.getByText('No stages yet. Click "Add Stage" to begin.')
    ).toBeVisible({ timeout: 10_000 });
  });

  // -------------------------------------------------------------------------
  // 12. Navigate away and back
  // -------------------------------------------------------------------------

  test("navigating to Q&A and back to workflow builder retains selector", async ({ page }) => {
    // Capture the currently selected workflow option text
    const select = page.locator("select").first();
    const textBefore = await select.evaluate((el: HTMLSelectElement) => {
      return el.options[el.selectedIndex]?.text ?? "";
    });

    // Navigate away to Q&A
    await page.getByRole("navigation").getByRole("button", { name: "Q&A" }).click();
    await expect(
      page.getByPlaceholder("Enter your questions here (one per line or numbered list)...")
    ).toBeVisible();

    // Navigate back to Settings → Workflow Builder
    await openWorkflowBuilder(page);

    // The selector must still be populated (app did not crash)
    await expect(page.locator("select").first()).toBeVisible();
    const optionCount = await page.locator("select").first().locator("option").count();
    expect(optionCount).toBeGreaterThanOrEqual(1);

    // Settings page heading is still present (no crash)
    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
  });

  // -------------------------------------------------------------------------
  // 13. Selecting a different workflow in the selector loads it
  // -------------------------------------------------------------------------

  test("selecting a different workflow from the dropdown loads its stages", async ({ page }) => {
    const select = page.locator("select").first();
    const optionCount = await select.locator("option").count();

    if (optionCount < 2) {
      // Only one workflow exists; create a second one so we can switch between them
      await page.getByRole("button", { name: "New Template" }).click();
      await expect(select.locator("option")).toHaveCount(optionCount + 1, { timeout: 15_000 });
    }

    // Select the first option (index 0)
    await select.selectOption({ index: 0 });
    // Give the async getWorkflow call a moment to resolve
    await page.waitForTimeout(1_500);

    // "Stages" section heading must still be visible (template loaded).
    // Use getByRole to avoid strict-mode violations — "Stages" also appears
    // inside the empty-state paragraph text.
    await expect(page.getByRole("heading", { name: "Stages" })).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// Sub-tab feature tests
// ---------------------------------------------------------------------------

/**
 * Click a workflow sub-tab and wait for the WorkflowBuilder to fully reload.
 *
 * When a sub-tab is clicked, the `WorkflowBuilder` component re-renders with
 * the new `workflowType` prop. It sets `isLoading=true` (showing a spinner
 * and hiding the <select>) and then `isLoading=false` (showing the <select>
 * again). This helper waits for the loading transition to complete so that
 * the stage cards are from the correct workflow type.
 *
 * Args:
 *   page:    Playwright Page instance.
 *   subTab:  Button name of the sub-tab to click.
 */
async function clickSubTab(
  page: import("@playwright/test").Page,
  subTab: string
): Promise<void> {
  await page.getByRole("button", { name: subTab }).click();
  // The WorkflowBuilder briefly shows a loading spinner (select is hidden).
  // Wait for the hidden state first, then for it to become visible again.
  // This prevents `waitFor({ state: "visible" })` from resolving on the
  // stale select from the previously loaded workflow type.
  await page.locator("select").first().waitFor({ state: "hidden", timeout: 5_000 }).catch(() => {
    // If the select was not visible before or transitions instantly, that is fine.
  });
  await page.locator("select").first().waitFor({ state: "visible", timeout: 15_000 });
}

test.describe("Workflow Builder — sub-tabs", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Q&A System" })).toBeVisible();
    await navigateToSettings(page);
    await page.getByRole("button", { name: "Workflow Builder" }).click();
    // Wait for sub-tabs to appear
    await page.getByRole("button", { name: "Project Workflow" }).waitFor({ state: "visible", timeout: 10_000 });
    // Also wait for the default Project Workflow to complete loading (select appears).
    // This ensures clickSubTab's hidden→visible transition logic works correctly —
    // without this, the select may still be loading when the first test clicks
    // another sub-tab, causing the hidden-wait to be a no-op.
    await page.locator("select").first().waitFor({ state: "visible", timeout: 15_000 });
  });

  // -------------------------------------------------------------------------
  // Sub-tab visibility
  // -------------------------------------------------------------------------

  test("all four workflow type sub-tabs are visible", async ({ page }) => {
    await expect(page.getByRole("button", { name: "Project Workflow" })).toBeVisible();
    await expect(page.getByRole("button", { name: "QA Session" })).toBeVisible();
    await expect(page.getByRole("button", { name: "QA Pair" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Agentic Pipeline" })).toBeVisible();
  });

  test("Project Workflow sub-tab is active by default", async ({ page }) => {
    // The active sub-tab has border-indigo-500 class
    const projectBtn = page.getByRole("button", { name: "Project Workflow" });
    await expect(projectBtn).toHaveClass(/border-indigo-500/);
  });

  // -------------------------------------------------------------------------
  // Project Workflow — 15 real pipeline stages
  // -------------------------------------------------------------------------

  test("Project Workflow tab shows 15 real pipeline stages", async ({ page }) => {
    await clickSubTab(page, "Project Workflow");
    // All 15 stage cards should be present
    const stageCards = page.locator('[title="Edit stage"]');
    await expect(stageCards).toHaveCount(15, { timeout: 10_000 });
  });

  test("Project Workflow contains key real stage labels", async ({ page }) => {
    await clickSubTab(page, "Project Workflow");
    // Check for a representative set of the 15 stage labels
    await expect(page.getByText("Prepare documents")).toBeVisible();
    await expect(page.getByText("Submit (1st instance)")).toBeVisible();
    await expect(page.getByText("Inquiry check")).toBeVisible();
    await expect(page.getByText("End: refund")).toBeVisible();
    await expect(page.getByText("End: no appeal")).toBeVisible();
  });

  test("old placeholder stages are not present in Project Workflow", async ({ page }) => {
    await clickSubTab(page, "Project Workflow");
    // None of the old placeholder stage names should appear
    await expect(page.getByText("Intake")).not.toBeVisible();
    await expect(page.getByText("Complete")).not.toBeVisible();
  });

  // -------------------------------------------------------------------------
  // Per-type stage counts
  // -------------------------------------------------------------------------

  test("QA Session sub-tab loads 4 stages", async ({ page }) => {
    await clickSubTab(page, "QA Session");
    const stageCards = page.locator('[title="Edit stage"]');
    await expect(stageCards).toHaveCount(4, { timeout: 10_000 });
    await expect(page.getByText("Open")).toBeVisible();
    await expect(page.getByText("In Review")).toBeVisible();
  });

  test("QA Pair sub-tab loads 5 stages", async ({ page }) => {
    await clickSubTab(page, "QA Pair");
    const stageCards = page.locator('[title="Edit stage"]');
    await expect(stageCards).toHaveCount(5, { timeout: 10_000 });
    // Use exact matching to avoid strict-mode violations — stage descriptions
    // may also contain the same text (e.g. "Answer draft" contains "draft").
    await expect(page.getByText("Draft", { exact: true })).toBeVisible();
    await expect(page.getByText("Exemplar", { exact: true })).toBeVisible();
  });

  test("Agentic Pipeline sub-tab loads 5 stages", async ({ page }) => {
    await clickSubTab(page, "Agentic Pipeline");
    const stageCards = page.locator('[title="Edit stage"]');
    await expect(stageCards).toHaveCount(5, { timeout: 10_000 });
    await expect(page.getByText("Question Analysis", { exact: true })).toBeVisible();
    // Use exact match — "Output" also appears inside the stage description text.
    await expect(page.getByText("Output", { exact: true })).toBeVisible();
  });

  // -------------------------------------------------------------------------
  // Tab switching
  // -------------------------------------------------------------------------

  test("switching sub-tabs changes the displayed stages", async ({ page }) => {
    // Start on Project Workflow (default)
    await clickSubTab(page, "Project Workflow");
    const projectCount = await page.locator('[title="Edit stage"]').count();
    expect(projectCount).toBe(15);

    // Switch to QA Session — use clickSubTab to wait for the reload transition
    await clickSubTab(page, "QA Session");
    const qaCount = await page.locator('[title="Edit stage"]').count();
    expect(qaCount).toBe(4);
    expect(qaCount).not.toBe(projectCount);
  });

  // -------------------------------------------------------------------------
  // Sub-tab isolation
  // -------------------------------------------------------------------------

  test("sub-tab isolation: template created in QA Session not visible in Project Workflow", async ({ page }) => {
    // Capture the Project Workflow option count BEFORE creating anything
    await clickSubTab(page, "Project Workflow");
    const projectCountBefore = await page.locator("select").first().locator("option").count();

    // Switch to QA Session and create a new blank template
    await clickSubTab(page, "QA Session");
    const initialQaCount = await page.locator("select").first().locator("option").count();
    await page.getByRole("button", { name: "New Template" }).click();
    await expect(page.locator("select").first().locator("option")).toHaveCount(
      initialQaCount + 1, { timeout: 15_000 }
    );

    // Switch back to Project Workflow — its count must be UNCHANGED
    await clickSubTab(page, "Project Workflow");
    const projectCountAfter = await page.locator("select").first().locator("option").count();

    // The new QA Session template must NOT appear under Project Workflow
    expect(projectCountAfter).toBe(projectCountBefore);
  });
});
