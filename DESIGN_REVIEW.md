# DESIGN_REVIEW.md

Log of the visual QA passes (PLAN.md Phase 7, Step E). The tool is `npm run qa:capture` (frontend/scripts/qa-capture.mjs):
Playwright drives Chromium through every page, signed in through the demo endpoint (admin for the main app, the supplier
account for the portal; the landing, sign-in and forgot-password pages anonymously), at 1440x900, 1024x768 and 390x844, in
light and dark. Per capture it saves a full-page screenshot, runs axe-core and records horizontal overflow and browser
console errors. 34 pages x 3 viewports x 2 themes = 204 captures. The summary of the latest run is
`docs/qa-screens/report.json`; the PNGs (28 MB) are ignored by git and rebuilt by the command.

Checks that were run against the demo seed (`python -m app.cli.demo_reset`, `DEMO_MODE=true`), the backend on port
8010 and the dev server on 5180.

## Pass 0: wrong application captured

The first run captured another project's storefront, because Vite had silently moved to a different port after
5173 was taken. Nothing from that run is used. The script now refuses to start unless the page title says ProcuraFlow,
and the dev server is started with `--strictPort`.

## Pass 1: first real capture (1440x900, light)

34 captures, 30 with findings.

| Finding | Where | Fix |
| --- | --- | --- |
| axe `label-content-name-mismatch`: profile link named "Your profile" but showing the user's name | every page | the visible text is now the name; "Your profile" became a tooltip |
| axe `label` (critical): hidden logo file input had no name | settings | `aria-label` added |
| Chart axis showed ISO month keys (`2026-05`) | dashboard | new `formatMonth` (Intl, company locale); the bar chart takes `formatX` |
| 401 console errors on public pages | landing, sign-in | expected (silent session probe); the script no longer counts them |

## Pass 2: full matrix (204 captures)

80 captures with findings, four distinct causes.

| Finding | Where | Fix |
| --- | --- | --- |
| Logo tile text unreadable in dark mode (near-black on dark teal, axe `color-contrast`) | every page in dark mode, sign-in, portal | `readableTextOn()` chooses white or near-black from the tile's own colour, so any brand colour works |
| `aria-label` not containing the visible text: "Export data of X" vs "Export JSON", "Download X" vs "Download CSV" | personal data, exports | labels now start with the visible text |
| Horizontally scrolling line-item tables not keyboard-reachable (axe `scrollable-region-focusable`) | invoice and purchase order pages at 390 | labelled region with a tab stop |
| Leftover light-only `Badge` with raw `slate-/green-/amber-/red-` classes | payment runs, users, portal, email templates | replaced by `StatusBadge` (icon plus word, token colours); `Badge` deleted |

A grep for raw palette classes (`bg-slate-100`, `text-green-800`, `brand-NNN`, `bg-white`) over `src/` now finds none.

## Pass 3: capture fix

Screenshots cut long pages off, because the app shell scrolls inside a viewport-high container. The script now grows the
window by the hidden height before shooting. This made the captures usable for reviewing whole pages.

## Pass 4: final matrix

204 captures, 0 findings: no serious or critical axe violation, no horizontal overflow, no console error.

## What was looked at by eye, and what was not

Looked at in full: dashboard (light 1440, dark 1440, dark 390), landing page (1440 light), purchase order detail (1440 light,
390 light), invoice detail (1440 light), suppliers list (390 light), company settings (1024 dark).

Every other capture was judged by the automated checks only (axe, overflow, console). They are in `docs/qa-screens/`
locally after a run, but nobody has paged through all 204. Treat them as unreviewed by a person.

## Observations not fixed

- Purchase order lines show a numeric product id, not a name or SKU, because the order item response carries only
  `product_id`. Showing a name needs an additive field on the API response (recorded in RELEASE_CHECK.md).
- Recent activity on the dashboard prints the raw action ("Avery Quinn login").
- The lifecycle stepper on a phone stacks vertically; its connector line renders as a short bar beside each step.
- Wide tables (suppliers, orders) scroll sideways inside their card on a phone and truncate long emails. That is
  deliberate, but it is not a card layout.
- axe cannot judge colour contrast in jsdom, so the frontend axe tests (`src/test/accessibility.test.tsx`: landing,
  design system, exports) skip that one rule. Contrast is covered by the browser runs here and by `npm run check:contrast`.

## Theme default

`DEFAULT_THEME_MODE` in `frontend/src/lib/theme.tsx` was already `system` in the committed code, so no change was needed.
Dark mode is clean in the final matrix.
