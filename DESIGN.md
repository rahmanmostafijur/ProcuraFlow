# ProcuraFlow design

**Idea:** ProcuraFlow is trustworthy procure-to-pay numbers, self-hosted, with no monthly fee. Deep navy ink for trust, one emerald that means "go" and "approved", one amber that means "look here"; numbers are the hero: large, tabular, right-aligned, never decorated.

All of this is original to ProcuraFlow. Nothing here copies another product's colours, layouts, copy or illustrations.

## Principles

1. **One primary action per view.** Everything else is secondary or a quiet text button.
2. **Numbers first.** Amounts use tabular numerals and sit right-aligned in tables; KPIs are the largest type on a page.
3. **State is never colour alone.** Every status badge carries a word, and focus, error and selection have a shape
   change (ring, icon, underline) as well as a colour.
4. **Calm by default, motion only to explain.** Transitions are short and ease out; `prefers-reduced-motion` turns
   them off.
5. **Dark mode is a first-class theme,** not an inversion: surfaces step up in lightness, accents step down in
   saturation.

## Tokens

All values are CSS variables defined in `frontend/src/styles/tokens.css` (imported by `index.css`) and wired into `tailwind.config.ts`. New
components use the semantic tokens (`bg-surface`, `text-text-primary`, `bg-brand`), never raw scale values. Red, orange and blue
ramps (50-950) are the Tailwind defaults; amber and the others are in the same file. `npm run check:contrast` verifies every pairing below in both themes (56 checks) and must stay green.

### Colour scales

| Step | Ink (navy neutrals) | Emerald (brand) | Amber (accent) |
|---|---|---|---|
| 50 | `#F4F6FA` | `#ECFDF8` | `#FFFBEB` |
| 100 | `#E8ECF3` | `#D1FAEE` | `#FEF3C7` |
| 200 | `#D2D9E6` | `#A5F3DD` | `#FDE68A` |
| 300 | `#B0BBD0` | `#6FE6C7` | `#FCD34D` |
| 400 | `#8795B1` | `#34D0AB` | `#FBBF24` |
| 500 | `#647394` | `#14B592` | `#F59E0B` |
| 600 | `#4B5878` | `#087D67` | `#D97706` |
| 700 | `#3A4561` | `#0B7762` | `#B45309` |
| 800 | `#283048` | `#0E5E4E` | `#92400E` |
| 900 | `#1A2036` | `#0F4D41` | `#78350F` |
| 950 | `#0F1424` | `#042F29` | n/a |

Status colours (used for badges, alerts and chart series that mean something):

| Meaning | Light text on tint | Solid |
|---|---|---|
| Danger / over budget / rejected | red-800 `#991B1B` on red-100 `#FEE2E2` | red-600 `#DC2626` |
| Attention / exception | orange-800 `#9A3412` on orange-100 `#FFEDD5` | orange-600 `#EA580C` |
| Information | blue-800 `#1E40AF` on blue-100 `#DBEAFE` | blue-700 `#1D4ED8` |
| Waiting / warning | amber-800 on amber-100 | amber-500 |
| Done / approved / paid | emerald-800 on emerald-100 | emerald-700 |

### Contrast (WCAG 2.2 AA: 4.5:1 for text, 3:1 for large text and UI shapes)

`frontend/scripts/check-contrast.mjs` reads `tokens.css` and checks 28 pairings in each theme (body, secondary and muted
text on bg, surface and raised surfaces; brand text and button labels; accent and danger buttons; every status badge;
focus ring; control borders), exits non-zero on any failure and also fails if the explicit and system dark blocks
drift apart. Its output is the authoritative table (light: lowest text pair 4.83:1, danger button; dark: lowest 4.98:1,
brand link on its tint).

Rules that follow: the primary button is **emerald-700 (hover 800), not 500/600**; ink-400 is for disabled controls and
decorative borders only, never text in light theme; `--border` is decorative and exempt, `--border-strong` is the
3:1 control edge.

### Semantic tokens

Defined per theme in `tokens.css`; Tailwind names in the last column.

| Token | Light | Dark | Tailwind |
|---|---|---|---|
| `--bg` page | ink-50 | ink-950 | `bg-bg` |
| `--surface` cards | white | ink-900 | `bg-surface` |
| `--surface-raised` modals, menus | white | ink-800 | `bg-surface-raised` |
| `--border` decorative dividers | ink-200 | ink-700 | `border-border` |
| `--border-strong` control edges (3:1) | ink-500 | ink-400 | `border-border-strong` |
| `--text-primary` | ink-900 | ink-50 | `text-text-primary` |
| `--text-secondary` | ink-600 | ink-200 | `text-text-secondary` |
| `--text-muted` placeholders, hints | ink-600 | ink-300 | `text-text-muted` |
| `--brand` buttons, links, active nav | emerald-700 | emerald-400 | `bg-brand`, `text-brand` |
| `--brand-hover` | emerald-800 | emerald-300 | `bg-brand-hover` |
| `--on-brand` text on brand | white | ink-950 | `text-on-brand` |
| `--brand-subtle` / `-fg` tint and its text | emerald-50 / 800 | emerald-900 / 200 | `bg-brand-subtle` |
| `--accent` / `--on-accent` | amber-400 / ink-950 | amber-400 / ink-950 | `bg-accent text-accent-fg` |
| `--focus` ring | emerald-600 | emerald-300 | `ring-focus` |
| `--success-*` bg / fg | emerald-100 / 800 | emerald-900 / 100 | `bg-success-bg text-success-fg` |
| `--warning-*` | amber-100 / 800 | amber-900 / 100 | `bg-warning-bg text-warning-fg` |
| `--danger-*` | red-100 / 800 | red-900 / 100 | `bg-danger-bg text-danger-fg` |
| `--danger-solid` / `--on-danger-solid` | red-600 / white | red-400 / ink-950 | `bg-danger-solid text-danger-on` |
| `--attention-*` | orange-100 / 800 | orange-900 / 100 | `bg-attention-bg text-attention-fg` |
| `--info-*` | blue-100 / 800 | blue-900 / 100 | `bg-info-bg text-info-fg` |

The company's own brand colour from Settings (`--company-brand`) is used for the logo tile and sign-in panel only;
buttons keep the verified emerald so contrast never depends on a customer's colour choice. Amber is a fill, never a
thin line on white (1.7:1), so it has no UI-boundary pairing.

### Spacing, radius, elevation, motion

- **Spacing:** 4 px base, Tailwind's scale (0, 0.5, 1, 2, 3, 4, 5, 6, 8, 10, 12, 16) plus `18` (72 px) and `22` (88 px).
- **Radii** (`rounded-control`, `-card`, `-overlay`, `-hero`): 8 (inputs, buttons), 12 (cards, menus), 16 (modals,
  drawers), 20 (hero and brand panels). The stock `rounded-md/lg` still exist for legacy screens.
- **Elevation** (`shadow-elev-1/2/3`), a tight contact shadow plus a wide ambient one:
  1 `0 1px 2px rgb(15 20 36 / .06), 0 1px 3px rgb(15 20 36 / .08)` (cards),
  2 `0 4px 8px rgb(15 20 36 / .06), 0 8px 24px rgb(15 20 36 / .10)` (menus, popovers),
  3 `0 8px 16px rgb(15 20 36 / .08), 0 24px 56px rgb(15 20 36 / .18)` (modals, drawers). Dark uses black at higher
  opacity; pair with a 1 px `border-border` so edges stay visible.
- **Motion** (`duration-fast/base/slow`, `ease-standard`): 120 ms (hover, focus), 200 ms (menus, toasts), 320 ms
  (drawers, modals); easing `cubic-bezier(.2, .8, .2, 1)`. Only animate `opacity` and `transform` where possible.
- **Reduced motion:** a global `@media (prefers-reduced-motion: reduce)` rule in `index.css` sets animation and
  transition durations to 0.01 ms and disables smooth scrolling. Never rely on motion to convey state.

## Themes and dark-mode rules

- Light is `:root`. Dark applies under `.dark` or `[data-theme="dark"]`; `prefers-color-scheme: dark` applies only when
  `<html>` has no `data-theme`. `lib/theme.tsx` (`ThemeProvider`, `useTheme()` returning `mode`, `resolved`, `setMode`)
  stores `light | dark | system` under the `pf-theme` localStorage key (failures are swallowed) and sets `data-theme` plus
  the `dark` class. `public/theme-init.js` applies it before first paint (an external file because the CSP is
  `script-src 'self'`). The default is `light` until every screen is tokenised (Step C), then `system`.
- Dark is not an inversion: surfaces step up in lightness (950, 900, 800), brand and status text step down in
  saturation, status badges use the 100 step on a 900 fill. Use semantic tokens so the switch is automatic; raw
  `slate-*`, `white` and `brand-NNN` classes do not adapt and are legacy.
- Use `dark:` variants only for one-off adjustments; they match `.dark` or `data-theme="dark"`.

## Accessibility rules (WCAG 2.2 AA)

- Text 4.5:1, large text (18 px bold or 24 px) and UI shapes (focus ring, control border, icon) 3:1, in both themes.
- Never put ink-400 or lighter on a light surface for text. Placeholders use `text-text-muted`.
- Visible focus ring on every interactive element: 2 px `--focus`, 2 px offset. Never `outline: none` without a ring.
- State is never colour alone: badges carry a word, errors an icon and message, selection a shape change.
- Full keyboard operation, labelled controls with unique names, `aria-live` for toasts and async results, 44 px touch
  targets on mobile, `prefers-reduced-motion` honoured.

## Typography

**Plus Jakarta Sans** (`@fontsource-variable/plus-jakarta-sans`, exact pin, weights 200-800) is `font-sans`. The only other
family is **JetBrains Mono** (`@fontsource-variable/jetbrains-mono`) for document numbers (`font-mono`, `.doc-number`).
Both are imported in `main.tsx` and bundled; no CDN.

| Role | Tailwind | Size / line | Weight | Tracking |
|---|---|---|---|---|
| Display (landing hero) | `text-display-xl` | 56 / 60 | 800 | -0.03em |
| Display large | `text-display-lg` | 40 / 44 | 800 | -0.025em |
| H1, KPI figure | `text-display-md` | 32 / 38 | 700 | -0.02em |
| H2 | `text-display-sm` | 24 / 30 | 700 | -0.015em |
| H3 | `text-title` | 18 / 26 | 600 | -0.005em |
| Body | `text-body` | 15 / 24 | 400 | 0 |
| Small, table cells | `text-cell` | 13 / 20 | 400 to 500 | 0 |
| Caption, labels | `text-caption` | 12 / 16 | 600, uppercase optional | +0.04em |

- **Tabular numerals** are applied by default (`index.css`) to `td`, `th`, `.tabular`, `.amount` (also right-aligned) and
  `[data-kpi]`; use `tabular-nums` on chart axes.
- **Document numbers** (`PO-2026-00042`, `PR-2026-00007`) use a monospace face at 0.95 em so they read as identifiers.

## Money, number and date formatting

All of it lives in `frontend/src/lib/format.ts` (re-exported from `lib/formatting.ts` and `lib/utils.ts`), uses `Intl`
only, and reads the company settings (`configureFormatting`: currency, time zone, date pattern, locale).

| Helper | Rule |
|---|---|
| `formatMoney(amount, currency?, locale?)` | Decimal strings are formatted exactly (no float round trip). Decimals come from the currency (JPY 0, EUR 2, BHD 3). Negatives keep the locale's minus sign. Right-align, class `amount`. |
| `formatCompactMoney` | 1.3M style for KPI tiles only; the exact figure goes in a tooltip or the detail view. |
| `formatNumber(value, options?)`, `formatPercent(points, digits = 1)` | Percent takes points (92.5 gives 92.5%), never divide first. |
| `formatDate`, `formatDateTime` | The company's `date_format` pattern in the company time zone; a calendar date is never shifted by zone; time is 24 h. |
| `formatRelative` | "3 hours ago" for feeds and notifications, with the absolute date in a title attribute. |
| null, undefined, "", unparsable | Show an em dash. |

Locale: the company stores a country, not a locale, so it is the browser language combined with the company country
(`deriveLocale`), falling back to the browser language, then en-US.

## Do and don't

- Do use semantic tokens, `rounded-card`, `shadow-elev-*`, `duration-base ease-standard`.
- Do right-align amounts with tabular numerals and give every status a word.
- Do keep one primary action per view.
- Do use the mono face (`.doc-number`) only for document numbers.
- Don't hand-build currency, percent or date strings, and don't call `toFixed` for display.
- Don't use raw hex values, ink-400 text, or amber as a thin line on white.
- Don't animate layout properties or ignore `prefers-reduced-motion`.
- Don't load fonts from a CDN; they are self-hosted and the CSP is `font-src 'self' data:`.

## Components (shown in the dev-only `/design-system` route in every state)

Buttons (primary, secondary, quiet, danger, accent; loading, disabled), inputs, selects, combobox, date range picker,
data table (sort, filter, column visibility, pagination, row selection, sticky header, compact and comfortable
density), status badges, KPI cards with sparkline, charts themed from tokens with custom tooltips, modal, drawer, tabs,
toasts, skeletons, empty states with original SVG illustrations in one line-and-fill style, confirm dialog, command
palette (Ctrl+K) with recent items and actions, keyboard shortcut help (?), lifecycle stepper, activity timeline, diff
viewer and file dropzone.

## Layout patterns

- **App shell:** collapsible sidebar grouped by workflow (Plan, Buy, Receive, Pay, Insight, Admin) with badges,
  breadcrumbs, global search, theme toggle, notification centre and user menu in the top bar.
- **Document pages** (request, order, invoice, payment run): lifecycle stepper on top, sticky action bar showing only
  the actions the signed-in user may take, a summary panel on the right, an activity timeline with comments below.
- **Forms:** inline validation next to the field, unsaved-changes warning, optimistic updates that roll back with an
  error toast.
- **Responsive:** designed down to 360 px; tables become stacked cards under 640 px; the sidebar becomes a drawer.
