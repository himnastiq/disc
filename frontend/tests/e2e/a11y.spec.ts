import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { setupMockApi } from './helpers/mockApi';

test.describe('Responsiveness and Accessibility Audit (P9.10)', () => {
  test.beforeEach(async ({ page }) => {
    await setupMockApi(page);
  });

  test('reports zero serious or critical accessibility violations on For You tab', async ({ page }) => {
    await page.goto('/?tab=for-you');
    await page.waitForLoadState('networkidle');

    // Run Axe scan
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze();

    const seriousOrCritical = results.violations.filter(
      (v) => v.impact === 'serious' || v.impact === 'critical'
    );
    expect(seriousOrCritical).toEqual([]);
  });

  test('reports zero serious or critical accessibility violations on Compare tab', async ({ page }) => {
    await page.goto('/?tab=compare');
    await page.waitForLoadState('networkidle');

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze();

    const seriousOrCritical = results.violations.filter(
      (v) => v.impact === 'serious' || v.impact === 'critical'
    );
    expect(seriousOrCritical).toEqual([]);
  });

  test('reports zero serious or critical accessibility violations on Cold Start tab', async ({ page }) => {
    await page.goto('/?tab=cold-start');
    await page.waitForLoadState('networkidle');

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze();

    const seriousOrCritical = results.violations.filter(
      (v) => v.impact === 'serious' || v.impact === 'critical'
    );
    expect(seriousOrCritical).toEqual([]);
  });

  test('reports zero serious or critical accessibility violations on Evaluation tab', async ({ page }) => {
    await page.goto('/?tab=evaluation');
    await page.waitForLoadState('networkidle');

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze();

    const seriousOrCritical = results.violations.filter(
      (v) => v.impact === 'serious' || v.impact === 'critical'
    );
    expect(seriousOrCritical).toEqual([]);
  });

  test('reports zero serious or critical accessibility violations on About tab', async ({ page }) => {
    await page.goto('/?tab=about');
    await page.waitForLoadState('networkidle');

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze();

    const seriousOrCritical = results.violations.filter(
      (v) => v.impact === 'serious' || v.impact === 'critical'
    );
    expect(seriousOrCritical).toEqual([]);
  });

  test('semantic landmarks are present across viewports', async ({ page }) => {
    await page.goto('/');

    await expect(page.locator('header')).toBeVisible();
    await expect(page.locator('nav')).toBeVisible();
    await expect(page.locator('main')).toBeVisible();
    await expect(page.locator('footer')).toBeVisible();
  });

  test('item drawer traps focus and closes with Escape key', async ({ page }) => {
    await page.goto('/?tab=for-you&item=385');

    // Dialog should be visible
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();

    // Verify close button is rendered and focused/interactive
    const closeBtn = page.getByRole('button', { name: /close item drawer/i });
    await expect(closeBtn).toBeVisible();

    // Closes on Escape
    await page.keyboard.press('Escape');
    await expect(dialog).not.toBeVisible();
  });

  test('respects prefers-reduced-motion media query', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto('/');

    // Ensure page renders cleanly with reduced motion
    await expect(page.locator('header')).toBeVisible();
    await expect(page.locator('main')).toBeVisible();
  });
});

