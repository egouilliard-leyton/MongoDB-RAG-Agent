/**
 * 01-preflight.spec.ts
 *
 * Smoke tests verifying that both the backend and frontend are reachable
 * and that the default workflow has been seeded in the database.
 */
import { test, expect } from "@playwright/test";

const BACKEND_URL = "http://localhost:8000";

test.describe("Preflight checks", () => {
  test("backend is healthy", async ({ page }) => {
    const response = await page.request.get(`${BACKEND_URL}/api/system/health`);
    expect(response.status()).toBe(200);

    const body = await response.json();
    // Health endpoint should return a body — any non-error JSON is acceptable
    expect(body).toBeTruthy();
  });

  test("frontend loads", async ({ page }) => {
    await page.goto("/");

    // The app renders a header with "Q&A System" as the main title
    await expect(page.getByRole("heading", { name: "Q&A System" })).toBeVisible();
  });

  test("default workflow is seeded", async ({ page }) => {
    const response = await page.request.get(`${BACKEND_URL}/api/workflows`);
    expect(response.status()).toBe(200);

    const body = await response.json();
    // Response may be an array directly or wrapped in a data key
    const workflows: Array<{ is_default?: boolean }> = Array.isArray(body)
      ? body
      : body.data ?? body.workflows ?? [];

    const hasDefault = workflows.some(
      (w) => w.is_default === true
    );
    expect(hasDefault).toBe(true);
  });
});
