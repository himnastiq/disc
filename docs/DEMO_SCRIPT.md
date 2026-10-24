# Demo Script

> Estimated time: 5–7 minutes

## Setup

1. Ensure the API and frontend are running: `make demo`
2. Open http://localhost:3000

## Walkthrough

### 1. Movies (MovieLens + SAR) — ~2 min

<!-- TODO: Fill in after Phase 9 -->

- Select "Movies" from the type switcher
- Pick a demo user (e.g., a "Heavy user, Sci-Fi fan")
- **For You tab:** Show profile card and personalised recommendations with reason badges
- **Compare tab:** Show "Popular for everyone" vs "Personalised" — highlight overlaps and differences
- **Cold Start tab:** Search for 3–5 movies, add them as liked, watch recommendations update live
- **Evaluation tab:** Show metrics table, model vs baselines chart, cold-start curve

### 2. Products (Amazon + SAR) — ~1.5 min

<!-- TODO: Fill in after Phase 9 -->

- Switch to "Products"
- Show how the same engine adapts: different cards, different signals, same interface
- Point out product-specific features (brand, category, image)

### 3. Articles (MIND + TF-IDF) — ~1.5 min

<!-- TODO: Fill in after Phase 9 -->

- Switch to "Articles"
- Show how the content model differs: text-based profile, freshness window
- Cold-start demo: add a few articles, see text-driven recommendations

### 4. Cross-Cutting Points — ~1 min

- **About tab:** Show attribution, architecture, original vs derived
- **Evaluation tab:** Honest metrics, confidence intervals, limitations
- Point out: one engine, three content types, no core code changes

## Likely Evaluator Questions

<!-- TODO: Fill in after Phase 11 -->

| Question | Answer |
|---|---|
| Why SAR for movies and products? | <!-- TODO --> |
| Why TF-IDF for articles? | <!-- TODO --> |
| How does cold start work? | <!-- TODO --> |
| What is original vs derived? | <!-- TODO --> |
| How was data leakage prevented? | <!-- TODO --> |
| What are the limitations? | <!-- TODO --> |
