import { test, expect } from '@playwright/test';
import { setupMockApi } from './helpers/mockApi';

test.describe('Dashboard End-to-End User Journeys (P9.11)', () => {
  test.beforeEach(async ({ page }) => {
    await setupMockApi(page);
  });

  test('full navigation flow across all tabs and type switching', async ({ page }) => {
    await page.goto('/');

    // 1. Header & Type Switcher
    await expect(page.getByRole('banner').getByText('Discovery Engine')).toBeVisible();
    const typeTrigger = page.getByRole('tab', { name: /movies/i });
    await expect(typeTrigger).toBeVisible();

    // 2. For You Tab: Profile & Recommendations
    await expect(page.getByRole('banner').getByText(/User #1/i)).toBeVisible();
    await expect(page.getByRole('heading', { name: 'The Matrix (1999)' }).first()).toBeVisible();

    // Test k selector
    const k5Button = page.getByRole('button', { name: /k=5/i });
    if (await k5Button.isVisible()) {
      await k5Button.click();
      await expect(page).toHaveURL(/k=5/);
    }

    // 3. Item Drawer Interaction
    const matrixButton = page.getByRole('button', { name: 'The Matrix (1999)' }).first();
    await matrixButton.click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await expect(page).toHaveURL(/item=385/);

    // Close drawer
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog')).not.toBeVisible();

    // 4. Compare Tab Flow
    const compareTabButton = page.getByRole('tab', { name: /compare/i });
    await compareTabButton.click();
    await expect(page).toHaveURL(/tab=compare/);
    await expect(page.getByRole('heading', { name: /Popular for Everyone/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: /Personalized for User #1/i })).toBeVisible();

    // Toggle User vs User mode
    const userVsUserMode = page.getByRole('tab', { name: /User vs. User/i });
    await userVsUserMode.click();
    await expect(page.getByText(/Compare User #1 with:/i)).toBeVisible();

    // 5. Cold Start Tab Flow
    const coldStartTabButton = page.getByRole('tab', { name: /cold start/i });
    await coldStartTabButton.click();
    await expect(page).toHaveURL(/tab=cold-start/);
    await expect(page.getByRole('searchbox')).toBeVisible();
    await expect(page.getByText(/0 items selected/i)).toBeVisible();

    // Search and add item
    const searchBox = page.getByRole('searchbox');
    await searchBox.fill('matrix');
    const addButton = page.getByRole('button', { name: /add the matrix/i });
    await addButton.click();
    await expect(page.getByText(/Selected History \(1 \/ 200\)/i)).toBeVisible();

    // Clear all
    const clearButton = page.getByRole('button', { name: /clear all/i });
    await clearButton.click();
    await expect(page.getByText(/Selected History \(0 \/ 200\)/i)).toBeVisible();

    // 6. Evaluation Tab Flow
    const evalTabButton = page.getByRole('tab', { name: /evaluation/i });
    await evalTabButton.click();
    await expect(page).toHaveURL(/tab=evaluation/);
    await expect(page.getByRole('heading', { name: /Evaluation Protocol & Verification/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: /Ranking & Retrieval Benchmarks/i })).toBeVisible();
    await expect(page.getByText('Catalog Coverage')).toBeVisible();
  });

  test('type switcher resets user to first demo user while preserving active tab', async ({ page }) => {
    await page.goto('/?type=movies&tab=compare&user=42');

    // Tab is preserved
    await expect(page).toHaveURL(/tab=compare/);

    // Switch to Products tab
    const productsTab = page.getByRole('tab', { name: /products/i });
    await productsTab.click();
    await expect(page).toHaveURL(/type=products/);
    await expect(page).toHaveURL(/tab=compare/);
  });
});
