# Discovery Engine Frontend

A Next.js dashboard that talks to the FastAPI recommender through its own `/api/*` route handlers.

## Requirements

- Node.js 22

## Setup

```bash
npm ci
npm run dev
```

## Environment Variables

- `API_BASE_URL`: Base URL for the backend recommender service (defaults to `http://127.0.0.1:8000`).
- `API_KEY` or `RECOMMENDER_API_KEY`: Optional secret key sent as `x-api-key` header to backend requests (server-only, never use a `NEXT_PUBLIC_` prefix).
- `NEXT_PUBLIC_ALLOW_DEV_ROUTES`: Set to `'true'` at build time to expose `/dev/components` in production builds.

## Scripts

- `npm run dev`: Starts the Next.js development server (`next dev`).
- `npm run build`: Builds the application for production (`next build`).
- `npm run start`: Starts the Next.js production server (`next start`).
- `npm run lint`: Runs ESLint code style and syntax checks (`eslint`).
- `npm run type-check`: Performs TypeScript type checking without emitting files (`tsc --noEmit`).
- `npm run test`: Runs the Vitest test suite once (`vitest run`).
- `npm run test:watch`: Runs the Vitest test suite in interactive watch mode (`vitest`).
- `npm run test:e2e`: Runs Playwright end-to-end browser tests (`playwright test`).
- `npm run check-secrets`: Scans client bundles to ensure no server secrets are leaked (`node scripts/check_bundle_secrets.mjs`).
- `npm run generate:types`: Exports OpenAPI schema and generates TypeScript API types (`python ../tools/export_openapi.py && openapi-typescript openapi.json -o src/lib/api/generated.ts`).
- `npm run record-fixtures`: Records live API responses into mock test fixtures (`node scripts/record_fixtures.mjs`).

## Folder Layout

- `app`: Next.js App Router pages and `/api/*` server route handlers.
- `components`: Reusable React components divided into `shell`, `tabs`, `features`, and `ui`.
- `lib`: Core application utilities divided into `api`, `hooks`, and `server`.
- `tests`: Test suites divided into `unit`, `e2e`, `fixtures`, and `mocks`.

## Notes

Read `AGENTS.md` before changing Next.js code.
