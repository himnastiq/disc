# The Discovery Engine: Design Guide

Visual system only. Layout, routes and features are specified elsewhere.
Values marked **(inferred)** are not in the original spec; they are defaults chosen to fit it. Change them deliberately, not casually.

## 1. Identity

A consumer movie discovery product. It should feel like a real entertainment app, not a SaaS dashboard, a landing page, an IMDb clone or a Netflix clone.

- Colour language: red and black, inspired by Netflix. Do not copy its logo, typography or UI patterns.
- Character comes from **strong poster imagery, typography-driven hierarchy, restraint and negative space**, not from effects.
- Dark only. There is no light theme and no theme toggle.

## 2. Colour tokens

Define in `app/globals.css` (Tailwind v4). Use the tokens, never raw hex in components.

```css
@import "tailwindcss";

@theme {
  /* Surfaces */
  --color-bg: #0A0A0A;
  --color-surface: #141414;
  --color-elevated: #1F1F1F;
  --color-border: #2A2A2A;

  /* Text */
  --color-text: #F5F5F1;
  --color-text-secondary: #B3B3B3;
  --color-text-muted: #808080;

  /* Accent */
  --color-accent: #E50914;
  --color-accent-hover: #F6121D;
  --color-accent-active: #B20710;
  --color-accent-text: #FF4A53;

  /* Status */
  --color-success: #46D369;
  --color-error: #FF7A59;

  /* Type */
  --font-sans: var(--font-bricolage), sans-serif;

  /* Shape and size */
  --container-shell: 52rem;
  --radius-card: 6px;
}

:root {
  color-scheme: dark;
  --header-h: 64px;
  --nav-h: 64px;
}

body {
  background: var(--color-bg);
  color: var(--color-text);
  font-family: var(--font-sans);
}

:focus-visible {
  outline: 2px solid var(--color-accent-text);
  outline-offset: 2px;
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

### Token usage

| Token | Use |
|---|---|
| `bg` | Page background |
| `surface` | Inputs, cards without a poster, empty-state panels |
| `elevated` | Hover/pressed surfaces, menus, dropdowns, chips |
| `border` | All dividers and outlines. 1px. Separation comes from borders, not shadows |
| `text` | Titles, primary content |
| `text-secondary` | Descriptions, metadata |
| `text-muted` | Sub-labels, inactive nav, timestamps |
| `accent` | Fills (primary button, active indicator, liked heart, rating star), icons, large text |
| `accent-hover` / `accent-active` | Hover and pressed states of accent fills |
| `accent-text` | Red used as **small text** (e.g. the 12px active nav label) |
| `success` | Watched state only |
| `error` | Errors only. Always paired with an icon or message, never colour alone |

### Contrast notes

- `accent` on `bg` is about 4.1:1. Fine for icons, fills and large text. **Do not use it for small text**; use `accent-text` (about 6:1).
- White text on an `accent` fill is about 4.8:1 and passes.
- `text-muted` is about 5.0:1 on `bg` and 4.7:1 on `surface`, but only about 4.2:1 on `elevated`. **Do not put `text-muted` on `elevated`**; use `text-secondary` there.
- Red is an accent. It must not be used as a large background wash, gradient or decorative fill.

## 3. Typography

Single family: **Bricolage Grotesque**. Do not add another primary font. Do not fall back to Inter, Roboto or Arial as a design choice.

Load with `next/font/google` (self-hosted, no layout shift), not `<link>` tags:

```tsx
import { Bricolage_Grotesque } from 'next/font/google';

const bricolage = Bricolage_Grotesque({
  subsets: ['latin'],
  axes: ['opsz'],
  weight: ['400', '500', '600', '700', '800'],
  variable: '--font-bricolage',
  display: 'swap',
});

// <html lang="en" className={bricolage.variable}>
```

### Weights

| Weight | Use |
|---|---|
| 400 | Input text, secondary descriptions, sub-labels |
| 500 | Body text, navigation labels |
| 600 | Supporting headings, emphasised UI text |
| 700 | Primary headings, movie titles, buttons, badges |
| 800 | Rare display emphasis only |

### Scale **(inferred)**

| Role | Size / line height | Weight |
|---|---|---|
| Page title | 28px / 32px | 700 |
| Section heading | 20px / 28px | 700 |
| Movie title (card) | 14px / 18px | 700 |
| Movie title (detail) | 32px / 36px, tight tracking | 700 or 800 |
| Body | 15px / 24px | 500 |
| Metadata | 13px / 18px | 500, `text-secondary` |
| Nav label | 12px / 16px | 500 |

- Hierarchy comes from weight, size and colour contrast, not oversized type.
- No giant display text for visual drama.
- Use tabular numbers (`tabular-nums`) for ratings, years and runtimes.

## 4. Shell and layout tokens

- Shell max width **832px**, centred. Full viewport width on mobile.
- Page padding: **16px** on mobile, wider on tablet and up.
- Header: fixed to the viewport top, **64px**, 24px horizontal padding. Name left, actions right (search, notifications, settings). Icons 20–22px.
- Bottom nav: fixed to the viewport bottom, **64px + `env(safe-area-inset-bottom)`**. Four equal items, icon above label.
- Page content gets top padding of `var(--header-h)` and bottom padding of `var(--nav-h)` + safe-area so nothing hides behind the bars.
- Header and nav are lightweight and integrated: no card styling, no shadow. Use a `bg`-coloured surface with a 1px `border` edge so content scrolling behind stays legible. No blur or glass effect.
- Spacing on a 4/8px scale. Restrained, with deliberate negative space between sections. Content is dense but readable, with asymmetry where it helps, not symmetrical dashboard grids everywhere.
- Icons: Lucide, stroke style, consistent 1.75–2px stroke. No emoji as icons.

## 5. Component styling

### Header
Transparent-feeling, no container. Product name in 700 weight, `text`. Action icons are `text-secondary`, becoming `text` on hover, with a 40px minimum hit area.

### Bottom navigation
Inactive: `text-muted` icon and label. Active: `accent` icon and `accent-text` label, with a 2px `accent` indicator line at the top edge of the item. Label 12px / 500. Minimum 48px touch target per item.

### Movie card
The poster is the content.

- Poster ratio **2:3**, radius `--radius-card` (6px) **(inferred)**, `overflow-hidden`, `elevated` placeholder colour while loading.
- Title below the poster: 14px / 700, `text`, max two lines, clamped.
- Metadata line: year · runtime, 13px / 500, `text-secondary`.
- Rating: small `accent` star icon + number in `text`, with `tabular-nums`.
- Watched: small `success` check badge in the poster's top corner, solid `bg` backing, not a pill with a gradient.
- No shadows, no decorative overlays. A scrim is allowed only where text sits on the poster, and only if needed for contrast.
- Grid: 2 columns on mobile, 3 on tablet, 4 at shell width, 12–16px gap.
- Use Next.js `Image`. Lazy load everything except above-the-fold posters.

### Buttons
- Primary: `accent` fill, white text, 700 weight, radius 6px, 44px minimum height. Hover `accent-hover`, active `accent-active`.
- Secondary: transparent, 1px `border`, `text`. Hover `elevated`.
- Ghost/icon: no border, `text-secondary`, hover `text` on `elevated`.
- Avoid pill shapes unless the control is genuinely a tag or chip.

### Inputs and filters
`surface` fill, 1px `border`, radius 6px, 400-weight input text, `text-muted` placeholder. Focus uses the global accent outline. Filter controls expand in place (functional motion), not as modal overlays.

### Empty state (Home cold start)
A single centred icon in `text-muted`, one line of 600-weight heading and one line of `text-secondary` copy. No illustration, no gradient panel. Suggested copy: "It's empty in here. Add movies to your watchlist to generate feeds and personalised recommendations."

### Movie detail
Large poster or backdrop at the top, with the title block (title, year · runtime · genres, rating) beneath or beside it depending on width. Description in body style. Cast and director as labelled rows (`text-muted` label, `text` value, but see the contrast rule above). User actions (watched, watchlist, like, rate) grouped together directly under the title block, reusing the button and icon styles above.

## 6. Interaction states

| State | Treatment |
|---|---|
| Default | Token colours as defined above |
| Hover | One step up: text `text-secondary` → `text`; surface `bg`/`surface` → `elevated`; accent → `accent-hover`. Cards: poster scale to 1.02 at most |
| Focus | 2px `accent-text` outline, 2px offset, always visible. Never remove it |
| Active / pressed | `accent-active` for fills, `elevated` for ghost, scale 0.98 |
| Selected | `accent` icon/underline plus `text` label. Not colour alone: also use a filled icon or indicator |
| Disabled | 40% opacity, `cursor-not-allowed`, no hover effect, `aria-disabled` |
| Loading | `elevated` skeleton blocks matching the final shape (2:3 posters, title lines). Lightweight shimmer is optional and must stop under reduced motion |
| Watched | `success` check badge on card, `success` filled check on the detail action |
| Liked | Filled `accent` heart (outline when not liked) |
| Rated | Filled `accent` star with the user's value shown in `text` |

State must never rely on colour alone. Pair it with an icon shape change, fill change or label.

## 7. Motion

Subtle and functional only.

- Allowed: navigation state changes, hover/focus, card interactions, route transitions, expanding controls.
- Durations: **150ms** for hover/focus/press, **200ms** for expanding controls and route transitions. Easing `ease-out`.
- Route transitions: opacity (and at most a 4–8px translate). No sliding pages.
- Not allowed: floating or looping elements, parallax, decorative background animation, spring/bounce effects.
- Respect `prefers-reduced-motion` (handled globally in the CSS above).

## 8. Accessibility

- Semantic HTML: `header`, `nav`, `main`, `section`, headings in order, links for routes, buttons for actions.
- Every icon-only control has an `aria-label` (search, notifications, settings, like, watched, etc.).
- Bottom nav marks the active route with `aria-current="page"`.
- Visible keyboard focus on everything interactive.
- Touch targets at least 44px.
- Meaningful `alt` text on posters (e.g. the movie title). Decorative images get `alt=""`.
- Toggle actions (liked, watched, watchlist) use `aria-pressed`.
- Contrast: follow the notes in section 2.

## 9. Do not

- Oversized centred hero sections
- Gradients as visual elements, or purple gradients at all
- Glassmorphism / backdrop blur
- Heavily rounded cards, or pill-shaped controls without reason
- Floating decorative blobs or decorative illustrations
- Heavy or stacked shadows
- Giant typography for drama
- Inter, Roboto, Arial or generic system fonts as the design font
- "Premium dark mode" clichés: neon glows, glass panels, tinted card washes
- Predictable, symmetrical dashboard grids everywhere
- Emoji used as icons
- Copying Netflix or IMDb branding, logos, layouts or typography

## 10. Definition of done for any UI change

- Uses only tokens from section 2. No raw hex, no arbitrary colour values.
- Passes `npm run lint`, `npx tsc --noEmit` and `npm run build` with zero errors and zero warnings.
- Keyboard navigable with visible focus, and checked at 375px, 768px and 832px+ widths.
- Looks at home next to the existing screens. If a new pattern is needed, state why before adding it.
