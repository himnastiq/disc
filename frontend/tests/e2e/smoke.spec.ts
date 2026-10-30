import { test, expect } from '@playwright/test';

test.describe('Discovery Engine App Shell & Viewports (P8.7, P8.8)', () => {
  test('renders dashboard header, tabs, and footer across viewports', async ({ page }) => {
    await page.goto('/');

    // 1. Verify App Header
    await expect(page.getByText('Discovery Engine')).toBeVisible();

    // 2. Verify Tab Navigation
    await expect(page.getByRole('tab', { name: /for you/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /compare/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /cold start/i })).toBeVisible();

    // 3. Verify Active Tab Content: Profile Card and Recommendations
    await expect(page.getByText(/user #1/i)).toBeVisible();
    await expect(page.getByText(/top recommendations/i)).toBeVisible();

    // 4. Verify Footer
    await expect(page.getByText(/microsoft recommenders/i)).toBeVisible();
    await expect(page.getByText(/movielens 1m/i)).toBeVisible();
  });

  test('renders design system primitives catalog on dev route', async ({ page }) => {
    await page.goto('/dev/components');
    await expect(page.getByText('Design System Primitives Catalog')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Primary' })).toBeVisible();
  });
});

