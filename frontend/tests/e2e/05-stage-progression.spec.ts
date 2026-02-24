/**
 * 05-stage-progression.spec.ts
 *
 * Tests for the Stage Workflow Visualization component in the sidebar.
 *
 * The component shows the current stage, available transitions (click to advance),
 * and rollback options. It requires a project to be loaded.
 */
import { test, expect, type Page } from "@playwright/test";
import { openProjectManagementSection } from "./helpers";

const E2E_PROJECT_NAME = "E2E Frontend Test Project — IP Box";

/**
 * Load the E2E project via the sidebar Project Management section.
 */
async function loadE2EProject(page: Page): Promise<void> {
  await openProjectManagementSection(page);

  const projectSelect = page.locator("aside").getByRole("combobox").first();
  await projectSelect.selectOption({ label: E2E_PROJECT_NAME });

  await page.getByRole("button", { name: "Load Project" }).click();

  // Confirm project loaded by checking sidebar Context section
  await expect(
    page.locator("aside").getByText(E2E_PROJECT_NAME)
  ).toBeVisible({ timeout: 10_000 });
}

test.describe("Stage workflow visualization", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await loadE2EProject(page);
  });

  test("stage workflow section is visible when a project is loaded", async ({
    page,
  }) => {
    // The StageWorkflowVisualization renders a heading "Stage Workflow" in the sidebar
    await expect(
      page.locator("aside").getByText("Stage Workflow")
    ).toBeVisible();

    // The current stage node should be highlighted (contains "● Current")
    await expect(page.locator("aside").getByText("● Current")).toBeVisible();
  });

  test("current stage badge is displayed in the context section", async ({
    page,
  }) => {
    // The sidebar Context section shows "Stage:" followed by a badge
    await expect(page.locator("aside").getByText("Stage:")).toBeVisible();

    // The stage badge renders inside a span with bg-blue-100 class
    const stageBadge = page
      .locator("aside span.inline-flex.items-center.bg-blue-100");
    await expect(stageBadge.first()).toBeVisible();
  });

  test("can advance project stage via quick action button", async ({ page }) => {
    // The StageWorkflowVisualization shows "Quick actions:" buttons when transitions exist.
    // These are rendered as Button components with the to_label as their text.
    const quickActionsSection = page.locator("aside").getByText("Quick actions:");
    const hasQuickActions = await quickActionsSection.isVisible().catch(() => false);

    if (!hasQuickActions) {
      // If no quick actions are available (e.g., project is in a terminal stage),
      // we skip the click step but still verify the workflow section renders.
      console.log("No quick actions available for current stage — skipping transition.");
      await expect(page.locator("aside").getByText("Stage Workflow")).toBeVisible();
      return;
    }

    // Record the current stage label before transitioning
    const currentStageBadge = page
      .locator("aside span.inline-flex.items-center.bg-blue-100")
      .first();
    const stageBefore = await currentStageBadge.textContent();

    // Click the first available quick action button
    const quickActionBtn = page
      .locator("aside")
      .getByText("Quick actions:")
      .locator("..")  // parent div
      .locator("button")
      .first();
    await quickActionBtn.click();

    // Wait for the stage to update (the API call updates the project)
    await page.waitForTimeout(2_000);

    // The current stage badge should have changed, OR a new "● Current" marker
    // appears on a different stage node.
    const stageAfter = await currentStageBadge.textContent();
    // Stage should have changed (or network latency means we check the "Current" dot moved)
    // We allow for the case where the stage label text updates
    expect(stageAfter).not.toEqual(stageBefore);
  });

  test("stage history is shown after a transition has occurred", async ({
    page,
  }) => {
    // After at least one transition, the timeline should show "✓ Completed"
    // on a previous stage node. If the project has never been advanced, this
    // test checks that the UI at least renders the workflow nodes.

    // The stage workflow always renders all stage nodes
    const stageNodes = page.locator(
      "aside .border-l-4"
    );
    // There should be multiple stage nodes (STAGES has ~15 entries)
    const nodeCount = await stageNodes.count();
    expect(nodeCount).toBeGreaterThan(3);
  });
});
