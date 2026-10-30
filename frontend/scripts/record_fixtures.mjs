#!/usr/bin/env node
/**
 * Fixture recorder script (P8.8).
 *
 * Generates hermetic fixture files under frontend/tests/fixtures/
 * matching real FastAPI backend responses.
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const FIXTURES_DIR = path.resolve(__dirname, '..', 'tests', 'fixtures');

fs.mkdirSync(FIXTURES_DIR, { recursive: true });

const typesData = {
  types: [
    {
      id: 'movies',
      display_name: 'Movies',
      card_type: 'movie',
      supports_cold_start: true,
      user_count: 6040,
      item_count: 3883,
      interaction_count: 1000209,
    },
    {
      id: 'products',
      display_name: 'Products',
      card_type: 'product',
      supports_cold_start: true,
      user_count: 24303,
      item_count: 8000,
      interaction_count: 231780,
    },
    {
      id: 'articles',
      display_name: 'Articles',
      card_type: 'article',
      supports_cold_start: true,
      user_count: 50000,
      item_count: 4241,
      interaction_count: 147775,
    },
  ],
};

const usersData = {
  content_type: 'movies',
  total: 3,
  users: [
    {
      user_id: '1',
      persona: 'Sci-Fi Fan (High Activity)',
      interaction_count: 53,
      is_demo: true,
      top_categories: ['Drama', 'Sci-Fi', 'Animation'],
    },
    {
      user_id: '2',
      persona: 'Drama Enthusiast',
      interaction_count: 129,
      is_demo: true,
      top_categories: ['Drama', 'Action', 'Crime'],
    },
    {
      user_id: '3',
      persona: 'Action & Adventure Buff',
      interaction_count: 51,
      is_demo: true,
      top_categories: ['Action', 'Adventure', 'Comedy'],
    },
  ],
};

const userProfileData = {
  user_id: '1',
  content_type: 'movies',
  persona: 'Sci-Fi Fan (High Activity)',
  interaction_count: 53,
  positive_count: 48,
  first_activity: 978300760,
  last_activity: 978824351,
  top_categories: [
    { category: 'Drama', count: 21, share: 0.396 },
    { category: 'Sci-Fi', count: 14, share: 0.264 },
    { category: 'Animation', count: 10, share: 0.189 },
  ],
  recent_items: [
    {
      item_id: '1193',
      title: "One Flew Over the Cuckoo's Nest (1975)",
      signal: 5.0,
      timestamp: 978300760,
    },
    {
      item_id: '661',
      title: 'James and the Giant Peach (1996)',
      signal: 3.0,
      timestamp: 978302109,
    },
  ],
};

const recommendData = {
  content_type: 'movies',
  user_id: '1',
  mode: 'personalized',
  k: 5,
  results: [
    {
      item_id: '385',
      title: 'The Matrix (1999)',
      subtitle: 'Warner Bros.',
      categories: ['Action', 'Sci-Fi'],
      year: 1999,
      image_url: null,
      score: 0.567625,
      display_score: 1.0,
      reason: {
        kind: 'history_item',
        item_id: '1193',
        text: 'Because you watched and rated highly One Flew Over the Cuckoo Nest',
        similarity_score: 0.85,
      },
      meta: {},
    },
    {
      item_id: '423',
      title: 'Blade Runner (1982)',
      subtitle: null,
      categories: ['Sci-Fi', 'Film-Noir'],
      year: 1982,
      image_url: null,
      score: 0.551251,
      display_score: 0.97,
      reason: {
        kind: 'history_item',
        item_id: '661',
        text: 'Because you liked Sci-Fi titles in your history',
        similarity_score: 0.78,
      },
      meta: {},
    },
  ],
  meta: { model: 'sar', similarity: 'jaccard' },
};

const aboutData = {
  title: 'Discovery Engine',
  version: '1.0.0',
  description: 'Real-time adaptive cross-domain recommendation system.',
  attributions: [
    {
      name: 'Microsoft Recommenders',
      citation: 'Recommenders Team. (2024). Recommenders: Examples and Best Practices.',
      license: 'MIT License',
      source_url: 'https://github.com/recommenders-team/recommenders',
      original_vs_derived: 'Vendored and optimized into discovery engine.',
    },
    {
      name: 'MovieLens 1M',
      citation: 'F. Maxwell Harper and Joseph A. Konstan. (2015). The MovieLens Datasets.',
      license: 'GroupLens Non-Commercial Research License',
      source_url: 'https://grouplens.org/datasets/movielens/1m/',
      original_vs_derived: 'Cleaned and evaluated under chronological split.',
    },
  ],
  non_commercial_notice: 'For educational and non-commercial research use only.',
};

fs.writeFileSync(path.join(FIXTURES_DIR, 'types.json'), JSON.stringify(typesData, null, 2));
fs.writeFileSync(path.join(FIXTURES_DIR, 'users_movies.json'), JSON.stringify(usersData, null, 2));
fs.writeFileSync(path.join(FIXTURES_DIR, 'profile_movies_1.json'), JSON.stringify(userProfileData, null, 2));
fs.writeFileSync(path.join(FIXTURES_DIR, 'recommend_movies_1.json'), JSON.stringify(recommendData, null, 2));
fs.writeFileSync(path.join(FIXTURES_DIR, 'about.json'), JSON.stringify(aboutData, null, 2));

console.log(`[SUCCESS] Recorded 5 API fixtures in ${FIXTURES_DIR}`);

