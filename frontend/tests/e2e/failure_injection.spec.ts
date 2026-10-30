import { test, expect } from '@playwright/test';
import { setupFailureInjectionMocks, setupConsoleErrorSpy } from './mock_api';
import recommendFixture from '../fixtures/recommend_movies_1.json' with { type: 'json' };

test.describe('Failure Injection & Robustness Suite (P10.2)', () => {
  test('Scenario 1: API Down (connection refused) displays full-page error banner and recovers on retry', async ({
    page,
  }) => {
    const spy = setupConsoleErrorSpy(page);

    // Initial state: API completely down
    await setupFailureInjectionMocks(page, { apiDown: true });
    await page.goto('/');

    // Verify full-page error banner
    await expect(page.getByRole('alert')).toBeVisible();
    await expect(page.getByText('Recommender Service Unavailable')).toBeVisible();
    await expect(
      page.getByText('Could not connect to the Discovery Engine backend API')
    ).toBeVisible();

    const tryAgainButton = page.getByRole('button', { name: /try again/i });
    await expect(tryAgainButton).toBeVisible();

    // Verify not a blank page
    const pageContent = await page.content();
    expect(pageContent.length).toBeGreaterThan(500);

    // Recover: restore healthy API mocks
    await page.unrouteAll();
    await setupFailureInjectionMocks(page);

    // Click retry
    await tryAgainButton.click();

    // Verify recovery to full running dashboard
    await expect(page.getByText('Personalized Recommendations')).toBeVisible();
    await expect(page.getByText('The Matrix (1999)').first()).toBeVisible();

    spy.assertNoUnexpectedErrors();
  });

  test('Scenario 2: 500 error on recommend shows inline error banner; other tabs remain unaffected', async ({
    page,
  }) => {
    const spy = setupConsoleErrorSpy(page);

    await setupFailureInjectionMocks(page, { status500: { recommend: true } });
    await page.goto('/?tab=for-you');

    // Inline error banner in For You tab
    await expect(page.getByText('Failed to fetch recommendations')).toBeVisible();
    const tryAgain = page.getByRole('button', { name: /try again/i });
    await expect(tryAgain).toBeVisible();

    // Switch to About tab - must be completely unaffected
    const aboutTab = page.getByRole('tab', { name: /about/i });
    await aboutTab.click();
    await expect(page.getByText('Architectural Blueprint')).toBeVisible();
    await expect(page.getByText('Performance & Budgets')).toBeVisible();

    // Switch back to For You tab
    const forYouTab = page.getByRole('tab', { name: /for you/i });
    await forYouTab.click();

    // Recover recommend endpoint
    await page.route('**/api/types/*/recommend*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(recommendFixture),
      });
    });

    await tryAgain.click();
    await expect(page.getByText('The Matrix (1999)').first()).toBeVisible();

    spy.assertNoUnexpectedErrors();
  });

  test('Scenario 3: 404 unknown user displays clear message; unmodelled user displays popularity fallback', async ({
    page,
  }) => {
    const spy = setupConsoleErrorSpy(page);

    // Case A: Unmodelled user receives popularity fallback mode
    await setupFailureInjectionMocks(page, { notInModelPopularFallback: true });
    await page.goto('/?user=99999');
    await expect(page.getByText('Mode: Popular')).toBeVisible();
    await expect(page.getByText('The Matrix (1999)').first()).toBeVisible();

    // Case B: Completely unknown user (404)
    await page.unrouteAll();
    await setupFailureInjectionMocks(page, { unknownUser404: true });
    await page.goto('/?user=99999999');

    // Must show graceful error state, no crash
    await expect(page.getByText(/Could not load profile/i)).toBeVisible();
    await expect(page.getByText(/Failed to fetch recommendations/i)).toBeVisible();

    spy.assertNoUnexpectedErrors();
  });

  test('Scenario 4: Malformed JSON is caught by schemas, never causes a blank page or unhandled error', async ({
    page,
  }) => {
    const spy = setupConsoleErrorSpy(page);

    await setupFailureInjectionMocks(page, { malformedJson: { recommend: true } });
    await page.goto('/?tab=for-you');

    // Must display error state
    await expect(page.getByText('Failed to fetch recommendations')).toBeVisible();
    const tryAgain = page.getByRole('button', { name: /try again/i });
    await expect(tryAgain).toBeVisible();

    // Must not be a blank page
    const pageHtml = await page.content();
    expect(pageHtml.length).toBeGreaterThan(500);

    // Recover
    await page.route('**/api/types/*/recommend*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(recommendFixture),
      });
    });

    await tryAgain.click();
    await expect(page.getByText('The Matrix (1999)').first()).toBeVisible();

    spy.assertNoUnexpectedErrors();
  });

  test('Scenario 5: Slow response shows skeletons with zero layout shift (CLS < 0.1), and 504 proxy timeout renders error', async ({
    page,
  }) => {
    const spy = setupConsoleErrorSpy(page);

    // Part A: Signal-deferred slow response
    let releaseRoute: () => void = () => {};
    const signalPromise = new Promise<void>((resolve) => {
      releaseRoute = resolve;
    });

    await setupFailureInjectionMocks(page, { slowSignal: signalPromise });

    // Navigate to page
    await page.goto('/?tab=for-you');

    // Track CLS via PerformanceObserver
    await page.evaluate(() => {
      (window as unknown as { __cls: number }).__cls = 0;
      try {
        const observer = new PerformanceObserver((entryList) => {
          for (const entry of entryList.getEntries()) {
            if (!(entry as unknown as { hadRecentInput: boolean }).hadRecentInput) {
              (window as unknown as { __cls: number }).__cls += (
                entry as unknown as { value: number }
              ).value;
            }
          }
        });
        observer.observe({ type: 'layout-shift', buffered: true });
      } catch {
        // Fallback if observer not supported
      }
    });

    // Verify loading skeletons are rendered while request is in-flight
    const skeletons = page.locator('.animate-pulse');
    await expect(skeletons.first()).toBeVisible();

    // Release delayed route
    releaseRoute();

    // Verify recommendations load
    await expect(page.getByText('The Matrix (1999)').first()).toBeVisible();

    // Measure CLS
    const cls = await page.evaluate(
      () => (window as unknown as { __cls: number }).__cls ?? 0
    );
    expect(cls).toBeLessThan(0.1);

    // Part B: Proxy 504 Gateway Timeout
    await page.unrouteAll();
    await setupFailureInjectionMocks(page, { proxyTimeout504: true });
    await page.goto('/?tab=for-you');

    await expect(page.getByText('Failed to fetch recommendations')).toBeVisible();
    await expect(page.getByRole('button', { name: /try again/i })).toBeVisible();

    spy.assertNoUnexpectedErrors();
  });

  test('Scenario 6: Empty results render explicit EmptyState, never empty whitespace', async ({
    page,
  }) => {
    const spy = setupConsoleErrorSpy(page);

    await setupFailureInjectionMocks(page, { emptyResults: { recommend: true } });
    await page.goto('/?tab=for-you');

    // Verify explicit empty state
    await expect(page.getByText('No recommendations generated')).toBeVisible();
    await expect(
      page.getByText(/The model did not return any recommendations/i)
    ).toBeVisible();

    // Cold Start search with 0 results
    await page.unrouteAll();
    await setupFailureInjectionMocks(page, { emptyResults: { search: true } });
    await page.goto('/?tab=cold-start');

    const searchBox = page.getByRole('searchbox');
    await searchBox.fill('xyznonexistent');
    await expect(page.getByText(/No items found/i)).toBeVisible();

    spy.assertNoUnexpectedErrors();
  });

  test('Scenario 7: One unavailable type shows degraded state; other types work normally', async ({
    page,
  }) => {
    const spy = setupConsoleErrorSpy(page);

    // Articles is degraded/offline
    await setupFailureInjectionMocks(page, { degradedType: 'articles' });
    await page.goto('/?type=movies');

    // Verify movies works normally
    await expect(page.getByText('The Matrix (1999)').first()).toBeVisible();

    // Verify products works normally
    const productsTab = page.getByRole('tab', { name: /products/i });
    await productsTab.click();
    await expect(page).toHaveURL(/type=products/);

    // Verify articles has offline indicator
    await expect(page.getByText('(offline)')).toBeVisible();

    spy.assertNoUnexpectedErrors();
  });
});
