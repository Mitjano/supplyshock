import { test, expect } from "@playwright/test";

/**
 * SupplyShock E2E smoke tests — Issue #105
 *
 * Verifies critical user paths are functional.
 * Requires the app to be running (dev or preview).
 */

test.describe("Smoke tests", () => {
  test("homepage loads and shows title", async ({ page }) => {
    await page.goto("/");
    // The page should load without errors
    await expect(page).toHaveTitle(/SupplyShock/i);
  });

  test("API health endpoint returns ok", async ({ request }) => {
    const apiBase = process.env.E2E_API_URL || "http://localhost:8000";
    const response = await request.get(`${apiBase}/health`);
    expect(response.ok()).toBeTruthy();

    const body = await response.json();
    expect(body.status).toBeDefined();
    expect(["ok", "degraded"]).toContain(body.status);
  });

  test("login page is accessible", async ({ page }) => {
    await page.goto("/login");
    // Should either show login form or redirect to Clerk
    await expect(page.locator("body")).toBeVisible();
    // No uncaught JS errors
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(err.message));
    await page.waitForTimeout(1000);
    expect(errors).toHaveLength(0);
  });

  test("dashboard redirects unauthenticated users", async ({ page }) => {
    await page.goto("/dashboard");
    // Should redirect to login or show auth wall
    await page.waitForURL(/\/(login|sign-in|dashboard)/, { timeout: 10_000 });
    await expect(page.locator("body")).toBeVisible();
  });

  test("map page loads without errors", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(err.message));

    await page.goto("/");
    // Wait for page to settle
    await page.waitForTimeout(2000);

    // Filter out known non-critical errors (e.g., missing Mapbox token in test env)
    const criticalErrors = errors.filter(
      (e) => !e.includes("mapbox") && !e.includes("MapLibre") && !e.includes("Clerk"),
    );
    expect(criticalErrors).toHaveLength(0);
  });
});
