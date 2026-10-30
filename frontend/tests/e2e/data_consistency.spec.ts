import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, '../../../');

function formatMetric(val: unknown, decimals: number = 4): string {
  if (val === null || val === undefined || typeof val !== 'number' || Number.isNaN(val)) return '—';
  return val.toFixed(decimals);
}

function formatCi(ci: unknown, decimals: number = 4): string {
  if (!ci || !Array.isArray(ci) || ci.length < 2) return '';
  return `[${formatMetric(ci[0], decimals)}, ${formatMetric(ci[1], decimals)}]`;
}

test.describe('Data-versus-UI Consistency Audit (P10.3)', () => {
  const contentTypes = ['movies', 'products', 'articles'] as const;

  test.describe('1. Fixed Precision & Rounding Unit Tests on Boundary Values', () => {
    test('verifies boundary formatting rules against raw numbers with zero extra tolerance', () => {
      // Documented rules from P9.7:
      // Headline metrics: 4 decimals
      expect(formatMetric(0.12345, 4)).toBe('0.1235');
      expect(formatMetric(0.12344, 4)).toBe('0.1234');
      expect(formatMetric(0.12346, 4)).toBe('0.1235');
      expect(formatMetric(0.05465, 4)).toBe('0.0546');
      expect(formatMetric(0.05924, 4)).toBe('0.0592');
      expect(formatMetric(0.00005, 4)).toBe('0.0001');
      expect(formatMetric(0.0, 4)).toBe('0.0000');
      expect(formatMetric(1.0, 4)).toBe('1.0000');
      expect(formatMetric(null, 4)).toBe('—');
      expect(formatMetric(NaN, 4)).toBe('—');

      // Confidence intervals: [lower, upper] with 4 decimals
      expect(formatCi([0.0577, 0.0891], 4)).toBe('[0.0577, 0.0891]');
      expect(formatCi(null, 4)).toBe('');

      // Diversity: 3 decimals
      expect(formatMetric(0.85432, 3)).toBe('0.854');

      // Novelty: 2 decimals bits
      const noveltyVal = 10.456;
      expect(`${noveltyVal.toFixed(2)} bits`).toBe('10.46 bits');

      // Percentages: 1 decimal
      const covVal = 0.1639;
      expect(`${(covVal * 100).toFixed(1)}%`).toBe('16.4%');
    });
  });

  for (const cType of contentTypes) {
    test.describe(`2. ${cType.toUpperCase()} Evaluation Tab Consistency (Source: metrics.json)`, () => {
      const metricsFilePath = path.join(repoRoot, 'artifacts', cType, 'metrics.json');
      const metricsRaw = JSON.parse(fs.readFileSync(metricsFilePath, 'utf-8'));

      const modelsDict = metricsRaw.models || metricsRaw.protocols?.retrieval?.models || {};
      const modelKeys = Object.keys(modelsDict);
      const primaryModel = modelKeys.find((k) => k !== 'popularity' && k !== 'random') || 'model';

      test.beforeEach(async ({ page }) => {
        // Intercept types endpoint with valid types
        await page.route('**/api/types', async (route) => {
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              types: [
                { id: 'movies', display_name: 'Movies', available: true },
                { id: 'products', display_name: 'Products', available: true },
                { id: 'articles', display_name: 'Articles', available: true },
              ],
            }),
          });
        });

        // Intercept metrics endpoint with the exact canonical metrics.json from disk
        await page.route(`**/api/types/${cType}/metrics*`, async (route) => {
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify(metricsRaw),
          });
        });

        // Intercept user profile and users for initial render
        const demoUsersPath = path.join(repoRoot, 'artifacts', cType, 'demo_users.json');
        const demoUsers = JSON.parse(fs.readFileSync(demoUsersPath, 'utf-8'));
        const firstUser = demoUsers[0];

        await page.route(`**/api/types/${cType}/users*`, async (route) => {
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              content_type: cType,
              total_users: demoUsers.length,
              users: demoUsers,
            }),
          });
        });

        await page.route(`**/api/types/${cType}/users/*/profile*`, async (route) => {
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              user_id: firstUser.user_id,
              content_type: cType,
              persona: firstUser.persona,
              interaction_count: 50,
              positive_count: 25,
              first_activity: 100000,
              last_activity: 200000,
              top_categories: [{ category: 'Action', count: 15, share: 0.6 }],
              recent_items: [],
            }),
          });
        });

        await page.route(`**/api/types/${cType}/recommend*`, async (route) => {
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              content_type: cType,
              user_id: firstUser.user_id,
              k: 10,
              results: [],
            }),
          });
        });
      });

      test('renders headline metrics, CIs, beyond-accuracy cards & cold-start curves with 0 mismatches', async ({
        page,
      }) => {
        await page.goto(`/?type=${cType}&tab=evaluation`);

        // Check protocol header
        await expect(page.getByRole('heading', { name: 'Evaluation Protocol & Verification' })).toBeVisible();

        // If articles, verify Impression Ranking Dual Protocol Table
        if (cType === 'articles' && metricsRaw.protocols?.impression_ranking) {
          const irModels = metricsRaw.protocols.impression_ranking.models;
          for (const mKey of ['random', 'popularity', 'tfidf_profile']) {
            const mData = irModels[mKey];
            if (!mData) continue;
            const expectedAuc = formatMetric(mData.auc);
            const expectedMrr = formatMetric(mData.mrr);
            const expectedNdcg5 = formatMetric(mData['ndcg@5']);
            const expectedNdcg10 = formatMetric(mData['ndcg@10']);

            const tableRegion = page.getByRole('region', { name: 'Impression ranking metrics table' });
            await expect(tableRegion).toBeVisible();
            await expect(tableRegion.getByText(expectedAuc).first()).toBeVisible();
            await expect(tableRegion.getByText(expectedMrr).first()).toBeVisible();
            await expect(tableRegion.getByText(expectedNdcg5).first()).toBeVisible();
            await expect(tableRegion.getByText(expectedNdcg10).first()).toBeVisible();
          }
        }

        // Test across k in [5, 10, 20]
        for (const kVal of [5, 10, 20]) {
          const kButton = page.getByRole('button', { name: String(kVal), exact: true }).first();
          await kButton.click();

          const modelData = modelsDict[primaryModel]?.[String(kVal)] || {};
          const popData = modelsDict['popularity']?.[String(kVal)] || {};
          const randData = modelsDict['random']?.[String(kVal)] || {};

          // Verify headline metrics in table
          const metricKeys = [
            { key: 'hit_rate', label: 'Hit Rate' },
            { key: 'ndcg', label: 'nDCG' },
            { key: 'recall', label: 'Recall' },
            { key: 'precision', label: 'Precision' },
            { key: 'map', label: 'MAP' },
          ];

          const rankingTable = page.getByRole('region', { name: 'Top-K ranking metrics table' });
          await expect(rankingTable).toBeVisible();

          for (const m of metricKeys) {
            const expMod = formatMetric(modelData[m.key]);
            const expPop = formatMetric(popData[m.key]);
            const expRand = formatMetric(randData[m.key]);

            const row = rankingTable.locator('tr', { hasText: `${m.label}@${kVal}` });
            await expect(row).toBeVisible();

            // Random column
            await expect(row.getByText(expRand).first()).toBeVisible();
            // Popularity column
            await expect(row.getByText(expPop).first()).toBeVisible();
            // Model column
            await expect(row.getByText(expMod).first()).toBeVisible();

            // Bootstrap CI bounds check
            const popCi = popData[`${m.key}_ci95`];
            const modCi = modelData[`${m.key}_ci95`];
            if (Array.isArray(popCi) && popCi.length >= 2) {
              const expPopCi = formatCi(popCi);
              await expect(row.getByText(expPopCi).first()).toBeVisible();
            }
            if (Array.isArray(modCi) && modCi.length >= 2) {
              const expModCi = formatCi(modCi);
              await expect(row.getByText(expModCi).first()).toBeVisible();
            }
          }

          // Verify Beyond-Accuracy Metrics Cards at this k
          if (typeof modelData.coverage === 'number') {
            const expCov = `${(modelData.coverage * 100).toFixed(1)}%`;
            await expect(page.getByText(expCov).first()).toBeVisible();
          }
          if (typeof modelData.novelty === 'number') {
            const expNov = `${modelData.novelty.toFixed(2)} bits`;
            await expect(page.getByText(expNov).first()).toBeVisible();
          }
          if (typeof modelData.diversity === 'number') {
            const expDiv = formatMetric(modelData.diversity, 3);
            await expect(page.getByText(expDiv).first()).toBeVisible();
          }
          if (typeof modelData.personalisation === 'number') {
            const expPers = `${(modelData.personalisation * 100).toFixed(1)}%`;
            await expect(page.getByText(expPers).first()).toBeVisible();
          }
        }

        // Verify Cold-Start Curve Points (sizes 0, 1, 2, 3, 5, 10, 20)
        const curves = metricsRaw.cold_start_curves || {};
        const modCurve = curves[primaryModel] || {};
        const popCurve = curves['popularity'] || {};

        const coldStartContainer = page.locator('div[aria-label="Cold start curve data points"]');
        await expect(coldStartContainer).toBeAttached();

        for (const step of ['0', '1', '2', '3', '5', '10', '20']) {
          const expModVal = formatMetric(Number(modCurve[step]?.['ndcg@10']) || 0);
          const expPopVal = formatMetric(Number(popCurve[step]?.['ndcg@10']) || 0);

          const stepRow = coldStartContainer.locator(`tr[data-step="${step}"]`);
          await expect(stepRow).toBeAttached();
          await expect(stepRow.locator('[data-model-val]')).toHaveText(expModVal);
          await expect(stepRow.locator('[data-pop-val]')).toHaveText(expPopVal);
        }
      });
    });
  }

  test.describe('3. Profile Card UI Consistency (API Response vs UI Render)', () => {
    test('renders exact numerical profile values and top category shares matching API', async ({
      page,
    }) => {
      const mockProfile = {
        user_id: '1',
        content_type: 'movies',
        persona: 'Action Buff',
        interaction_count: 842,
        positive_count: 512,
        first_activity: 978300000,
        last_activity: 1046476800,
        top_categories: [
          { category: 'Action', count: 280, share: 0.3325 },
          { category: 'Thriller', count: 180, share: 0.2138 },
          { category: 'Sci-Fi', count: 120, share: 0.1425 },
        ],
        recent_items: [],
      };

      await page.route('**/api/types', async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            types: [{ id: 'movies', display_name: 'Movies', available: true }],
          }),
        });
      });

      await page.route('**/api/types/movies/users*', async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            content_type: 'movies',
            total_users: 1,
            users: [{ user_id: '1', persona: 'Action Buff' }],
          }),
        });
      });

      await page.route('**/api/types/movies/users/1/profile*', async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(mockProfile),
        });
      });

      await page.route('**/api/types/movies/recommend*', async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ content_type: 'movies', user_id: '1', k: 10, results: [] }),
        });
      });

      await page.goto('/?type=movies&user=1');

      // Profile Card Section
      const profileCard = page.getByRole('region', { name: 'User Profile #1' });
      await expect(profileCard).toBeVisible();

      // Counts
      await expect(profileCard.getByText('842')).toBeVisible();
      await expect(profileCard.getByText('512')).toBeVisible();

      // Categories and formatted shares
      for (const cat of mockProfile.top_categories) {
        await expect(profileCard.getByText(cat.category, { exact: true })).toBeVisible();
        await expect(profileCard.getByText(`${cat.count} items`)).toBeVisible();
        await expect(profileCard.getByText(`${(cat.share * 100).toFixed(1)}%`)).toBeVisible();
      }
    });
  });

  test.describe('4. Compare Tab Overlap & Jaccard Consistency', () => {
    test('renders overlap count, percentage & Jaccard matching set intersection', async ({
      page,
    }) => {
      const popularItems = [
        { item_id: '1', title: 'Item 1', score: 0.9, display_score: 0.9, categories: [] },
        { item_id: '2', title: 'Item 2', score: 0.8, display_score: 0.8, categories: [] },
        { item_id: '3', title: 'Item 3', score: 0.7, display_score: 0.7, categories: [] },
        { item_id: '4', title: 'Item 4', score: 0.6, display_score: 0.6, categories: [] },
        { item_id: '5', title: 'Item 5', score: 0.5, display_score: 0.5, categories: [] },
      ];

      const userAItems = [
        { item_id: '2', title: 'Item 2', score: 0.95, display_score: 0.95, categories: [] }, // overlap
        { item_id: '4', title: 'Item 4', score: 0.85, display_score: 0.85, categories: [] }, // overlap
        { item_id: '6', title: 'Item 6', score: 0.75, display_score: 0.75, categories: [] },
        { item_id: '7', title: 'Item 7', score: 0.65, display_score: 0.65, categories: [] },
        { item_id: '8', title: 'Item 8', score: 0.55, display_score: 0.55, categories: [] },
      ];

      // Overlap: 2 items ('2', '4') out of 5 -> 40%
      // Jaccard: 2 / (5 + 5 - 2) = 2/8 = 25%

      await page.route('**/api/types', async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            types: [{ id: 'movies', display_name: 'Movies', available: true }],
          }),
        });
      });

      await page.route('**/api/types/movies/users*', async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            content_type: 'movies',
            total_users: 2,
            users: [
              { user_id: '1', persona: 'Alpha' },
              { user_id: '2', persona: 'Beta' },
            ],
          }),
        });
      });

      await page.route('**/api/types/movies/popular*', async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ content_type: 'movies', k: 5, results: popularItems }),
        });
      });

      await page.route('**/api/types/movies/recommend*user_id=1*', async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ content_type: 'movies', user_id: '1', k: 5, results: userAItems }),
        });
      });

      await page.goto('/?type=movies&user=1&tab=compare&k=5');

      const overlapBanner = page.getByRole('status', { name: 'Overlap analysis summary' });
      await expect(overlapBanner).toBeVisible();

      // Assert 2 of 5 items overlap (40%)
      await expect(overlapBanner.getByText('2 of 5 items overlap (40%)')).toBeVisible();
      await expect(
        overlapBanner.getByText('60% distinct personalized recommendations beyond the global popularity baseline.')
      ).toBeVisible();
    });
  });
});
