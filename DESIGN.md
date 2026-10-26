# ProcuraFlow design

**Idea:** a calm ledger for money that is about to leave the building. Deep navy ink for trust, one emerald that means
"go" and "approved", one amber that means "look here". Numbers are the hero: large, tabular, right-aligned, never
decorated.

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

All values are CSS variables defined in `frontend/src/styles/tokens.css` and wired into `tailwind.config.ts`; components
use the semantic tokens (`--surface`, `--text`, `--brand`), never raw scale values.

### Colour scales

| Step | Ink (navy neutrals) | Emerald (brand) | Amber (accent) |
|---|---|---|---|
| 50 | `#F4F6FA` | `#ECFDF8` | `#FFFBEB` |
| 100 | `#E8ECF3` | `#D1FAEE` | `#FEF3C7` |
| 200 | `#D2D9E6` | `#A5F3DD` | `#FDE68A` |
| 300 | `#B0BBD0` | `#6FE6C7` | `#FCD34D` |
| 400 | `#8795B1` | `#34D0AB` | `#FBBF24` |
| 500 | `#647394` | `#14B592` | `#F59E0B` |
| 600 | `#4B5878` | `#0A9478` | `#D97706` |
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

Checked with a script, not by eye. Every text pairing below passes AA.

| Pairing | Ratio |
|---|---|
| Body: ink-900 on white / on ink-50 | 16.1 / 14.9 |
| Secondary text: ink-600 on white / on ink-50 | 7.1 / 6.5 |
| Placeholder: ink-500 on white | 4.8 |
| Primary button: white on **emerald-700** (hover emerald-800) | 5.5 |
| Link: emerald-700 on white / on emerald-50 | 5.5 / 5.2 |
| Accent button: ink-950 on amber-400 | 11.0 |
| Danger button: white on red-600 | 4.8 |
| Badges: emerald-800/100, amber-800/100, red-800/100, orange-800/100, blue-800/100 | 6.4 to 7.2 |
| Dark body: ink-50 on ink-950 / on ink-900 | 16.9 / 14.9 |
| Dark secondary: ink-300 on ink-900 | 8.3 |
| Dark placeholder: ink-400 on ink-900 | 5.3 |
| Dark link: emerald-300 on ink-900 | 10.6 |
| Dark primary button: ink-950 on emerald-400 | 9.4 |
| Dark badges (100 text on 800/900 fill) | 6.4 to 7.6 |

Two rules follow from the numbers: the light-theme primary button is **emerald-700, not 600** (white on emerald-600 is
only 3.8:1), and ink-400 is for disabled controls and borders only, never for text.

### Semantic tokens

| Token | Light | Dark |
|---|---|---|
| `--bg` page | ink-50 | ink-950 |
| `--surface` cards | white | ink-900 |
| `--surface-raised` modals, menus | white | ink-800 |
| `--border` | ink-200 | ink-700 |
| `--text` | ink-900 | ink-50 |
| `--text-muted` | ink-600 | ink-300 |
| `--brand` buttons, active nav | emerald-700 | emerald-400 |
| `--brand-contrast` text on brand | white | ink-950 |
| `--accent` highlights | amber-400 | amber-400 |
| `--focus` ring | emerald-600 | emerald-300 |

The company's own brand colour from Settings overrides `--brand` for the logo tile and sign-in panel only; buttons keep
the verified emerald so contrast never depends on a customer's colour choice.

### Spacing, radius, elevation, motion

- **Spacing:** 4 px base: 0, 2, 4, 8, 12, 16, 20, 24, 32, 40, 48, 64.
- **Radii:** 8 (inputs, buttons), 12 (cards, menus), 16 (modals, drawers), 20 (hero and brand panels).
- **Elevation:** three soft, layered levels, each a tight contact shadow plus a wide ambient one:
  1 `0 1px 2px rgb(15 20 36 / .06), 0 1px 3px rgb(15 20 36 / .08)` (cards),
  2 `0 4px 8px rgb(15 20 36 / .06), 0 8px 24px rgb(15 20 36 / .10)` (menus, popovers),
  3 `0 8px 16px rgb(15 20 36 / .08), 0 24px 56px rgb(15 20 36 / .18)` (modals, drawers). Dark theme uses the same
  geometry with higher opacity and a 1 px `--border` so edges stay visible.
- **Motion:** 120 ms (hover, focus), 200 ms (menus, toasts), 320 ms (drawers, modals); easing
  `cubic-bezier(.2, .8, .2, 1)`. Nothing moves when `prefers-reduced-motion: reduce`.

## Typography

**Plus Jakarta Sans**, self-hosted through `@fontsource` (pinned), weights 400, 500, 600, 700, 800; no other family
except a monospace for document numbers.

| Role | Size / line | Weight | Tracking |
|---|---|---|---|
| Display (landing hero) | 56 / 60 | 800 | -0.03em |
| H1 | 32 / 38 | 700 | -0.02em |
| H2 | 24 / 30 | 700 | -0.015em |
| H3 | 18 / 26 | 600 | -0.005em |
| Body | 15 / 24 | 400 | 0 |
| Small, table cells | 13 / 20 | 400 to 500 | 0 |
| Caption, labels | 12 / 16 | 600, uppercase optional | +0.04em |
| KPI figure | 32 / 36 | 700 | -0.02em |

- **Tabular numerals** (`font-variant-numeric: tabular-nums`) on every amount, table cell of numbers, KPI and chart
  axis.
- **Document numbers** (`PO-2026-00042`, `PR-2026-00007`) use a monospace face at 0.95 em so they read as identifiers.
- Money and dates are always produced with `Intl` from the company's currency and locale
  (`lib/formatting.ts`); no screen builds a currency or date string by hand.

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

## Accessibility

Visible focus ring (2 px `--focus` with a 2 px offset) on every interactive element, full keyboard operation, labelled
controls with unique names, `aria-live` for toasts and async results, no information carried by colour alone, 44 px
minimum touch targets on mobile, and axe-core checks in the frontend tests with zero serious or critical violations.
