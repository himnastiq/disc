import { test, expect } from '@playwright/test';
import { setupMockApi } from './helpers/mockApi';

test.describe('Phase 10 Adversarial UI Suite (P10.8)', () => {
  test.beforeEach(async ({ page }) => {
    // Fail on uncaught exceptions or unexpected page errors
    page.on('pageerror', (err) => {
      throw new Error(`Unhandled page error: ${err.message}`);
    });

    await setupMockApi(page);
  });

  test('Adversarial 1: Hostile search inputs (Zero-width, RTL Arabic, Emojis, 101 chars) render safely', async ({
    page,
  }) => {
    await page.goto('/?tab=cold-start');

    const searchBox = page.getByRole('searchbox');
    await expect(searchBox).toBeVisible();

    const hostileInputs = [
      't\u200be\u200ds\ufefft', // zero-width interleaved
      '\u200b\u200d\ufeff', // pure zero-width
      'فيلم حرب النجوم', // RTL Arabic
      '🎬🍿🚀🔥 Matrix', // Emojis
      '.*(test|val)\\[1\\]\\?', // regex metacharacters
      'a'.repeat(101), // 101 characters (exceeds 100 max)
    ];

    for (const hostile of hostileInputs) {
      await searchBox.fill(hostile);
      // Wait for debounce
      await page.waitForTimeout(200);
      // Assert search box remains intact and responsive
      await expect(searchBox).toBeVisible();
      // Ensure page did not crash
      await expect(page.getByRole('banner')).toBeVisible();
    }
  });

  test('Adversarial 2: Cold start tab rapid add, remove, and chip clearing', async ({ page }) => {
    await page.goto('/?tab=cold-start');

    const searchBox = page.getByRole('searchbox');
    await expect(searchBox).toBeVisible();

    // Type query and add item
    await searchBox.fill('matrix');
    const addButton = page.getByRole('button', { name: /add the matrix/i });
    await expect(addButton).toBeVisible();
    await addButton.click();

    // Chip should be visible in selected history with its remove button
    const removeBtn = page.getByRole('button', { name: /remove the matrix/i });
    await expect(removeBtn).toBeVisible();

    // Remove chip
    await removeBtn.click();

    // Verify empty history message appears
    await expect(page.getByText(/No items in hypothetical history/i)).toBeVisible();
  });

  test('Adversarial 3: XSS and script injection attempts in card titles and descriptions', async ({
    page,
  }) => {
    // Mock recommendations containing malicious script payload
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
              item_id: 'xss_test_1',
              title: '<script id="xss-probe">window.__xss_injected=true;</script>Safe Movie Title',
              categories: ['Action'],
              score: 0.95,
              display_score: 95,
              year: 2024,
              subtitle: '<img src=x onerror="window.__xss_img=true">',
              image_url: null,
              reason: {
                kind: 'similar',
                item_id: '1',
                text: '<b onmouseover="window.__xss_reason=true">Faithful Reason</b>',
              },
              meta: {},
            },
          ],
        }),
      });
    });

    await page.goto('/?tab=for-you');

    // Verify safe text is rendered and script was NOT executed in DOM window
    await expect(page.getByText(/Safe Movie Title/).first()).toBeVisible();

    const isXssInjected = await page.evaluate(() => {
      return (
        (window as unknown as Record<string, boolean>).__xss_injected === true ||
        (window as unknown as Record<string, boolean>).__xss_img === true ||
        (window as unknown as Record<string, boolean>).__xss_reason === true
      );
    });
    expect(isXssInjected).toBe(false);
  });

  test('Adversarial 4: Degraded type state in TypeSwitcher preserves healthy navigation', async ({
    page,
  }) => {
    // Mock health returning degraded status (e.g. products unavailable)
    await page.route('**/api/health', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'degraded',
          version: '1.0.0',
          types: {
            movies: { available: true, version: '1.0.0', reason: null },
            products: { available: false, version: null, reason: 'Manifest missing' },
            articles: { available: true, version: '1.0.0', reason: null },
          },
        }),
      });
    });

    await page.goto('/');

    // Movies and Articles tabs remain clickable and functional
    const moviesTab = page.getByRole('tab', { name: /movies/i });
    const articlesTab = page.getByRole('tab', { name: /articles/i });
    await expect(moviesTab).toBeVisible();
    await expect(articlesTab).toBeVisible();

    await articlesTab.click();
    await expect(page).toHaveURL(/type=articles/);
  });
});
