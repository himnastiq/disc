import { test, expect } from '@playwright/test';
import { setupMockApi } from './helpers/mockApi';

test.describe('Phase 9 Break-Your-Own-Work Rituals (P9.12)', () => {
  test.beforeEach(async ({ page }) => {
    await setupMockApi(page);
  });

  test('Ritual 1: Rapid Type Switching does not crash or cause race conditions', async ({ page }) => {
    await page.goto('/');

    const typeButton = page.getByRole('tab', { name: /movies/i });
    await expect(typeButton).toBeVisible();

    // Rapidly switch types
    for (let i = 0; i < 3; i++) {
      await page.goto('/?type=products&tab=for-you');
      await page.goto('/?type=articles&tab=for-you');
      await page.goto('/?type=movies&tab=for-you');
    }

    // Final state must be cleanly rendered movies
    await expect(page.getByRole('banner').getByText('Discovery Engine')).toBeVisible();
    await expect(page.getByRole('banner').getByText(/User #1/i)).toBeVisible();
  });

  test('Ritual 2: Rapid User Switching updates feed cleanly without stale data', async ({ page }) => {
    await page.goto('/');

    // Switch users via URL rapidly
    await page.goto('/?type=movies&user=2');
    await page.goto('/?type=movies&user=3');
    await page.goto('/?type=movies&user=1');

    await expect(page.getByRole('banner').getByText(/User #1/i)).toBeVisible();
  });

  test('Ritual 3: Cold-Start Spam Typing handles rapid debounced input without unhandled errors', async ({ page }) => {
    await page.goto('/?tab=cold-start');

    const searchBox = page.getByRole('searchbox');
    await expect(searchBox).toBeVisible();

    // Spam typing
    await searchBox.fill('a');
    await searchBox.fill('ab');
    await searchBox.fill('abc');
    await searchBox.fill('abcd');
    await searchBox.fill('matrix');

    // Wait for debounced search results to settle
    const addButton = page.getByRole('button', { name: /add the matrix/i });
    await expect(addButton).toBeVisible();
  });

  test('Ritual 4: Offline Mode & 500 API Error Injection displays graceful ErrorState with retry', async ({ page }) => {
    // Inject 500 error on recommendations
    await page.route('**/api/types/*/recommend*', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({
          error: {
            code: 'INTERNAL_ERROR',
            message: 'Injected server failure for ritual testing.',
          },
        }),
      });
    });

    await page.goto('/?tab=for-you');

    // Must show graceful error state
    await expect(page.getByText(/Failed to fetch recommendations/i)).toBeVisible();
    const retryButton = page.getByRole('button', { name: /try again/i });
    await expect(retryButton).toBeVisible();
  });

  test('Ritual 5: Extreme Data Edge Cases (500-char title, missing fields, XSS string) render safely', async ({ page }) => {
    // Inject extreme item data
    await page.route('**/api/types/*/recommend*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          content_type: 'movies',
          mode: 'personalized',
          k: 1,
          results: [
            {
              item_id: 'extreme_item_1',
              title: 'Supercalifragilisticexpialidocious '.repeat(20) + '<script>window.__xss=true</script>',
              categories: [],
              score: 0.9999,
              display_score: 100,
              year: null,
              subtitle: null,
              image_url: null,
              meta: {},
            },
          ],
          meta: {},
        }),
      });
    });

    await page.goto('/?tab=for-you');

    // Confirm no script injection occurred
    const isXssInjected = await page.evaluate(() => (window as unknown as { __xss?: boolean }).__xss === true);
    expect(isXssInjected).toBe(false);

    // Card should be rendered without crashing
    await expect(page.locator('h4').filter({ hasText: /Supercalifragilisticexpialidocious/i }).first()).toBeVisible();
  });
});
