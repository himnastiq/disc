<!-- BEGIN:nextjs-agent-rules -->

## This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

# Frontend rules
- Stack: Next.js App Router, React 19, TypeScript strict, Tailwind. Read package.json
  for exact versions before writing code.
- Definition of done: `npm run lint && npx tsc --noEmit && npm run build` all pass
  with zero errors AND zero warnings. Paste the actual output. Never say "done" otherwise.
- Never use eslint-disable, @ts-ignore, or `any` to silence a problem. Fix the root cause.
- Don't assume your memory of an API is current. If unsure, look up the docs for the
  installed version first.
- Don't add a dependency without telling me why. Prefer what's already installed.
- Don't set state inside useEffect just to detect mount; use useSyncExternalStore
  or restructure.
- Fix lint warnings you introduced (like unused types) instead of leaving them.
