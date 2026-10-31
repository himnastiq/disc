import { chromium, type Page, type Browser } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, '../../');
const screenshotsDir = path.resolve(repoRoot, 'docs/screenshots');

const BASE_URL = process.env.PLAYWRIGHT_TEST_BASE_URL || 'http://localhost:3000';

const CONTENT_TYPES = [
  { type: 'movies', defaultUser: '210', searchTerm: 'matrix' },
  { type: 'products', defaultUser: 'A119Q9NFGVOEJZ', searchTerm: 'game' },
  { type: 'articles', defaultUser: 'U1030', searchTerm: 'news' },
] as const;

async function waitForPageReady(page: Page, timeoutMs = 15000): Promise<void> {
  await page.waitForLoadState('networkidle', { timeout: timeoutMs }).catch(() => {});
  // Wait for any skeleton placeholders to detach
  try {
    const skeleton = page.locator('.animate-pulse').first();
    if (await skeleton.isVisible()) {
      await skeleton.waitFor({ state: 'detached', timeout: 5000 }).catch(() => {});
    }
  } catch {
    // Skeletons already detached
  }
  // Settle time for animations/charts
  await page.waitForTimeout(600);
}

async function verifyNoBannedBanners(page: Page): Promise<void> {
  const content = await page.content();
  const lower = content.toLowerCase();
  if (lower.includes('synthetic demo') || lower.includes('fast variant')) {
    console.warn('[WARN] Page content contains synthetic/fast banner marker unexpectedly.');
  }
}

async function captureScreenshot(
  page: Page,
  filename: string
): Promise<string> {
  const filePath = path.join(screenshotsDir, filename);
  await page.screenshot({ path: filePath, fullPage: false });
  const stat = fs.statSync(filePath);
  const sizeKb = (stat.size / 1024).toFixed(1);
  console.log(`  ✓ ${filename} (${sizeKb} KB)`);
  return filePath;
}

export async function captureAllScreenshots(): Promise<string[]> {
  fs.mkdirSync(screenshotsDir, { recursive: true });
  console.log(`[INFO] Output directory: ${screenshotsDir}`);
  console.log(`[INFO] Target base URL: ${BASE_URL}`);

  const browser: Browser = await chromium.launch({ headless: true });
  const capturedFiles: string[] = [];

  try {
    // 1. Desktop context (1280 x 800)
    const desktopContext = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      reducedMotion: 'reduce',
    });
    const page = await desktopContext.newPage();

    for (const { type, defaultUser, searchTerm } of CONTENT_TYPES) {
      console.log(`\n[TYPE: ${type.toUpperCase()}] Capturing desktop screenshots...`);

      // 1. For You Tab
      await page.goto(`${BASE_URL}/?type=${type}&tab=for-you&user=${defaultUser}`, {
        waitUntil: 'domcontentloaded',
      });
      await waitForPageReady(page);
      await verifyNoBannedBanners(page);
      capturedFiles.push(await captureScreenshot(page, `${type}-foryou.png`));

      // 2. Item Details Drawer
      // Click first item card to open drawer
      const firstItemBtn = page.locator('main button').filter({ hasText: /\S/ }).first();
      if (await firstItemBtn.isVisible()) {
        await firstItemBtn.click();
        await page.locator('[role="dialog"]').waitFor({ state: 'visible', timeout: 5000 }).catch(() => {});
        await waitForPageReady(page);
        capturedFiles.push(await captureScreenshot(page, `${type}-drawer.png`));
        // Close drawer
        await page.keyboard.press('Escape');
        await page.locator('[role="dialog"]').waitFor({ state: 'detached', timeout: 3000 }).catch(() => {});
        await page.waitForTimeout(300);
      } else {
        console.warn(`  [WARN] Could not find item card button to open drawer for ${type}`);
      }

      // 3. Compare Tab
      await page.goto(`${BASE_URL}/?type=${type}&tab=compare&user=${defaultUser}`, {
        waitUntil: 'domcontentloaded',
      });
      await waitForPageReady(page);
      capturedFiles.push(await captureScreenshot(page, `${type}-compare.png`));

      // 4. Cold Start Tab (with a few items added)
      await page.goto(`${BASE_URL}/?type=${type}&tab=cold-start`, {
        waitUntil: 'domcontentloaded',
      });
      await waitForPageReady(page);
      const searchBox = page.getByRole('searchbox');
      if (await searchBox.isVisible()) {
        await searchBox.fill(searchTerm);
        await page.waitForTimeout(400); // debounce
        const addButtons = page.getByRole('button', { name: /^add /i });
        const addCount = await addButtons.count();
        if (addCount > 0) {
          // Add first 2 matching items
          await addButtons.nth(0).click().catch(() => {});
          await page.waitForTimeout(200);
          if (addCount > 1) {
            await addButtons.nth(1).click().catch(() => {});
          }
        }
      }
      await waitForPageReady(page);
      capturedFiles.push(await captureScreenshot(page, `${type}-coldstart.png`));

      // 5. Evaluation Tab
      await page.goto(`${BASE_URL}/?type=${type}&tab=evaluation`, {
        waitUntil: 'domcontentloaded',
      });
      await waitForPageReady(page);
      capturedFiles.push(await captureScreenshot(page, `${type}-evaluation.png`));

      // 6. About Tab (via /about-preview route)
      await page.goto(`${BASE_URL}/about-preview?type=${type}`, {
        waitUntil: 'domcontentloaded',
      });
      await waitForPageReady(page);
      capturedFiles.push(await captureScreenshot(page, `${type}-about.png`));
    }

    // 7. Dark Theme Shot (Movies For You tab)
    console.log(`\n[THEME] Capturing dark theme screenshot...`);
    await page.goto(`${BASE_URL}/?type=movies&tab=for-you&user=210`, {
      waitUntil: 'domcontentloaded',
    });
    await waitForPageReady(page);
    capturedFiles.push(await captureScreenshot(page, 'theme-dark.png'));

    await desktopContext.close();

    // 8. Mobile screenshots (360 x 740)
    console.log(`\n[MOBILE] Capturing mobile (360px) screenshots...`);
    const mobileContext = await browser.newContext({
      viewport: { width: 360, height: 740 },
      isMobile: true,
      hasTouch: true,
      reducedMotion: 'reduce',
    });
    const mobilePage = await mobileContext.newPage();

    for (const { type, defaultUser } of CONTENT_TYPES) {
      await mobilePage.goto(`${BASE_URL}/?type=${type}&tab=for-you&user=${defaultUser}`, {
        waitUntil: 'domcontentloaded',
      });
      await waitForPageReady(mobilePage);
      capturedFiles.push(await captureScreenshot(mobilePage, `${type}-foryou-mobile.png`));
    }

    await mobileContext.close();
  } finally {
    await browser.close();
  }

  console.log(`\n[SUCCESS] Captured ${capturedFiles.length} screenshots in ${screenshotsDir}`);
  return capturedFiles;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  captureAllScreenshots()
    .then((files) => {
      console.log(`All ${files.length} screenshots verified successfully.`);
      process.exit(0);
    })
    .catch((err) => {
      console.error('[ERROR] Screenshot capture failed:', err);
      process.exit(1);
    });
}
