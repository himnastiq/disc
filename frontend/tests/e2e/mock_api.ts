import type { Page } from '@playwright/test';
import { expect } from '@playwright/test';
import typesFixture from '../fixtures/types.json' with { type: 'json' };
import usersFixture from '../fixtures/users_movies.json' with { type: 'json' };
import profileFixture from '../fixtures/profile_movies_1.json' with { type: 'json' };
import recommendFixture from '../fixtures/recommend_movies_1.json' with { type: 'json' };
import metricsFixture from '../fixtures/metrics_movies.json' with { type: 'json' };
import aboutFixture from '../fixtures/about.json' with { type: 'json' };

export interface FailureOptions {
  apiDown?: boolean;
  status500?: {
    types?: boolean;
    recommend?: boolean;
    users?: boolean;
    similar?: boolean;
    search?: boolean;
  };
  unknownUser404?: boolean;
  notInModelPopularFallback?: boolean;
  malformedJson?: {
    recommend?: boolean;
    users?: boolean;
    types?: boolean;
  };
  emptyResults?: {
    recommend?: boolean;
    search?: boolean;
  };
  degradedType?: string;
  slowSignal?: Promise<void>;
  proxyTimeout504?: boolean;
}

export function setupConsoleErrorSpy(page: Page) {
  const unexpectedErrors: string[] = [];

  const allowedPatterns = [
    /Failed to load resource/i,
    /net::ERR_CONNECTION_REFUSED/i,
    /status of 500/i,
    /status of 502/i,
    /status of 503/i,
    /status of 504/i,
    /status of 404/i,
    /Unexpected response from server/i,
    /\[Zod ValidationError\]/i,
    /API request failed with status/i,
    /Invalid JSON response/i,
    /malformed JSON/i,
    /recommender service/i,
  ];

  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      const text = msg.text();
      const isAllowed = allowedPatterns.some((pattern) => pattern.test(text));
      if (!isAllowed) {
        unexpectedErrors.push(text);
      }
    }
  });

  page.on('pageerror', (err) => {
    unexpectedErrors.push(`Uncaught exception: ${err.message}`);
  });

  return {
    assertNoUnexpectedErrors: () => {
      expect(unexpectedErrors).toEqual([]);
    },
    getErrors: () => unexpectedErrors,
  };
}

export async function setupFailureInjectionMocks(page: Page, options: FailureOptions = {}) {
  // Scenario 1: API Down (connection refused)
  if (options.apiDown) {
    await page.route('**/api/**', async (route) => {
      await route.abort('connectionrefused');
    });
    return;
  }

  // Types endpoint
  await page.route('**/api/types', async (route) => {
    if (options.status500?.types) {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ error: { code: 'INTERNAL_ERROR', message: 'Injected 500 on types' } }),
      });
      return;
    }
    if (options.malformedJson?.types) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: '{"types": [ {"id": "movies"', // Truncated JSON
      });
      return;
    }

    const typesCopy = JSON.parse(JSON.stringify(typesFixture));
    if (options.degradedType) {
      for (const t of typesCopy.types) {
        if (t.id === options.degradedType) {
          t.available = false;
          t.error = `${t.display_name} backend degraded`;
        }
      }
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(typesCopy),
    });
  });

  // Users endpoint
  await page.route('**/api/types/*/users', async (route) => {
    if (options.status500?.users) {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ error: { code: 'INTERNAL_ERROR', message: 'Injected 500 on users' } }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(usersFixture),
    });
  });

  // User Profile endpoint
  await page.route('**/api/types/*/users/*/profile', async (route) => {
    if (options.unknownUser404) {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({
          error: {
            code: 'NOT_FOUND',
            message: 'User not found in user catalogue',
          },
        }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(profileFixture),
    });
  });

  // Recommendations endpoint
  await page.route('**/api/types/*/recommend*', async (route) => {
    if (options.proxyTimeout504) {
      await route.fulfill({
        status: 504,
        contentType: 'application/json',
        body: JSON.stringify({
          error: {
            code: 'GATEWAY_TIMEOUT',
            message: 'Backend request timed out after 10000ms: /v1/types/movies/recommend',
          },
        }),
      });
      return;
    }

    if (options.slowSignal) {
      await options.slowSignal;
    }

    if (options.status500?.recommend) {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({
          error: {
            code: 'INTERNAL_ERROR',
            message: 'Injected 500 failure on recommendation engine',
          },
        }),
      });
      return;
    }

    if (options.malformedJson?.recommend) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: '{"content_type": "movies", "results": [ {"item_id":', // Truncated body
      });
      return;
    }

    if (options.emptyResults?.recommend) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          content_type: 'movies',
          mode: 'personalized',
          k: 5,
          results: [],
        }),
      });
      return;
    }

    if (options.notInModelPopularFallback) {
      const fallbackRecs = JSON.parse(JSON.stringify(recommendFixture));
      fallbackRecs.mode = 'popular';
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(fallbackRecs),
      });
      return;
    }

    if (options.unknownUser404) {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({
          error: {
            code: 'NOT_FOUND',
            message: 'User not found in user catalogue',
          },
        }),
      });
      return;
    }

    // Default healthy recommendations
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(recommendFixture),
    });
  });

  // Popular endpoint
  await page.route('**/api/types/*/popular*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(recommendFixture),
    });
  });

  // Similar endpoint
  await page.route('**/api/types/*/similar*', async (route) => {
    if (options.status500?.similar) {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ error: { code: 'INTERNAL_ERROR', message: 'Injected 500 on similar' } }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(recommendFixture),
    });
  });

  // Item detail endpoint
  await page.route('**/api/types/*/items/*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        item_id: '385',
        title: 'The Matrix (1999)',
        categories: ['Action', 'Sci-Fi'],
        year: 1999,
        text: 'A computer hacker learns from mysterious rebels about the true nature of his reality.',
        popularity_rank: 1,
        meta: {},
      }),
    });
  });

  // Search items endpoint
  await page.route('**/api/types/*/search*', async (route) => {
    if (options.status500?.search) {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ error: { code: 'INTERNAL_ERROR', message: 'Injected 500 on search' } }),
      });
      return;
    }
    if (options.emptyResults?.search) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          content_type: 'movies',
          query: 'xyznonexistent',
          total_matches: 0,
          results: [],
        }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        content_type: 'movies',
        query: 'matrix',
        total_matches: 1,
        results: [
          {
            item_id: '385',
            title: 'The Matrix (1999)',
            categories: ['Action', 'Sci-Fi'],
            year: 1999,
            popularity_rank: 1,
          },
        ],
      }),
    });
  });

  // Metrics endpoint
  await page.route('**/api/types/*/metrics', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(metricsFixture),
    });
  });

  // About endpoint
  await page.route('**/api/about', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(aboutFixture),
    });
  });
}
