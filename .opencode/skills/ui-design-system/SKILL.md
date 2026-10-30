---
name: ui-design-system
description: >
  Define and maintain the design system (tokens, status language, component
  specs, theming, accessibility rules) for a real-time system health dashboard.
  Use this skill whenever the user mentions design tokens, color palette, dark
  or light theme, typography, spacing scale, status colors (ok, warning,
  critical), how to show unavailable, partial or stale metrics, chart colors,
  component styles or variants, visual consistency, contrast, focus styles,
  density, Storybook, or "make the UI look consistent/professional", even if
  they do not say "design system". Also use it before adding a new color,
  size or component variant, and when reviewing UI for accessibility or
  visual drift.
---

# UI Design System Skill

The visual contract of the **Linux system health dashboard**. It defines *what*
the UI looks like; the `react-dashboard` skill defines *how* it is built and
wired. If the two disagree on tokens or states, this skill wins for visuals and
`react-dashboard` wins for code structure.

## 1. Non-negotiable rules

| # | Rule | Why |
|---|------|-----|
| 1 | **Components never contain raw color, size or font values.** They use semantic tokens only. | One place to change a theme; guaranteed light/dark parity. |
| 2 | **Three token tiers**: primitive -> semantic -> component. Components consume semantic (or component) tokens, never primitives. | Theme changes touch the semantic layer, not every component. |
| 3 | **Status is never conveyed by color alone.** Every status has color + icon + text label. | Color-blind users and honest, scannable status. |
| 4 | **Missing data has its own visual language** (unavailable, partial, stale), distinct from "ok" and "zero". | Mirrors the backend rule: never fake a value, never make a gap look healthy. |
| 5 | **Contrast is verified by tests, not by eye.** Every text/background and UI-boundary pair is asserted in CI for both themes. | Themes drift; automated checks catch it. |
| 6 | **Every component state is specified**: default, hover, focus-visible, active, disabled, loading, error. | Unspecified states get improvised inconsistently. |
| 7 | **A new token or variant needs a reason.** Reuse first; propose additions through the approval gate. | Systems die from token sprawl. |

## 2. Scope and ownership

| Owned here | Owned by `react-dashboard` |
|------------|----------------------------|
| Token names and values, palettes, type scale, spacing, motion | Folder layout of components, state stores, data flow |
| Visual spec for each component and each data state | Implementation, props, hooks, tests of behavior |
| Contrast and accessibility rules | Runtime theme switching code (provider, persistence) |
| Chart palette and chart styling rules | Recharts wrappers and performance handling |

Files (aligned with the frontend layout):

```
src/presentation/theme/
├── tokens/
│   ├── primitives.css      # raw scales: palette steps, spacing, radii (not used by components)
│   ├── semantic.css        # light theme semantic tokens (default)
│   └── semantic.dark.css   # [data-theme="dark"] overrides
├── tailwind.preset.ts      # maps Tailwind theme keys to semantic tokens only
├── chart-tokens.ts         # reads chart palette tokens for Recharts
└── ThemeProvider.tsx
src/presentation/components/ui/   # primitives built from tokens
docs/design-system/               # tokens.md, components.md, status-language.md, changelog.md
test/design-system/               # contrast.test.ts, token-usage.test.ts
```

## 3. Workflow

1. **Inventory** what exists; list real needs from dashboard widgets (not hypothetical ones).
2. **Define or extend tokens** (section 4-8) with the approval gate for new ones.
3. **Verify contrast** for every new pair in both themes (section 12) before using it.
4. **Specify the component** (section 10): anatomy, variants, all states, tokens used.
5. **Implement** via `react-dashboard` rules; use only tokens.
6. **Document** in `docs/design-system/` and update the changelog.
7. **Test**: contrast, token-usage lint, visual regression, accessibility (section 13).

## 4. Token architecture

**Tier 1 primitives** (raw scale, private): `--p-slate-50 ... --p-slate-950`, `--p-space-1 ... --p-space-16`, `--p-radius-sm/md/lg`.
**Tier 2 semantic** (public API of the system): `--color-bg`, `--color-surface`, `--color-text`, `--color-ok` ...
**Tier 3 component** (optional, only when a component needs its own knob): `--card-padding`, `--stat-value-size`.

Naming: `--{category}-{role}[-{variant}][-{state}]`, kebab-case, role-based not value-based (`--color-critical`, never `--color-red-700`).

Color values use space-separated RGB triples so Tailwind alpha utilities work (`rgb(var(--color-ok) / 0.12)`).

Enforcement:
- Stylelint / ESLint rule banning hex, `rgb(`, `hsl(` and arbitrary Tailwind values (`bg-[#...]`, `w-[13px]`) outside `theme/tokens/`.
- Tailwind preset **replaces** (not extends) the default palette, so off-system colors cannot be typed by accident.

## 5. Color tokens (brand-anchored, contrast verified)

**Fixed brand inputs from the user (never change without approval):**
Dark theme: background `#0A0A0A`, primary `#007BA7`, secondary `#FF2D95`.
Light theme: background `#E5E4E2` (platinum, decided), brown `#6F4E37` and lavender `#E6E0F0` as the accent colors.

**Assumption to confirm:** in the light theme, brown is the primary accent and lavender is a tint (selected rows, hover surfaces) because lavender on platinum is only 1.01:1 and cannot carry text or icons. The secondary *accent* for text and icons is a derived deeper purple (`#5B4B8A`).

Everything else below is **derived** around the brand values. Ratios were computed with the WCAG 2.x formula; re-verify in CI if any value changes. Write colors as `R G B` triples in CSS (so Tailwind alpha works); hex is shown here for readability.

| Token | Light | Contrast on `bg` / `surface` | Dark | Contrast on `bg` / `surface` |
|-------|-------|------------------------------|------|------------------------------|
| `bg` | `#E5E4E2` (brand) | - | `#0A0A0A` (brand) | - |
| `surface` (cards) | `#F4F3F1` | - | `#141414` | - |
| `surface-alt` (hover, selected) | `#E6E0F0` (brand lavender) | text-only, tested | `#1C1C1C` | text-only, tested |
| `text` | `#1C1917` | 13.8 / 15.8 | `#EDEDED` | 16.9 / 15.7 |
| `muted` | `#57534E` | 6.0 / 6.9 | `#A3A3A3` | 7.9 / 7.3 |
| `primary` (links, icons, active text) | `#6F4E37` (brand) | 5.9 / 6.7 | `#3DB8E0` (tint of brand `#007BA7`) | 8.6 / 8.0 |
| `primary-fill` (button background) | `#6F4E37` (brand) | label `#FFFFFF` 7.4 | `#007BA7` (brand) | fill vs bg 4.1 / 3.9 (passes 3:1); label `#FFFFFF` 4.8 |
| `secondary` (text, icons) | `#5B4B8A` (derived) | 5.9 / 6.7 | `#FF2D95` (brand) | 5.7 / 5.3 |
| `secondary-fill` label | `#FFFFFF` on `#5B4B8A` (tested) | - | `#0A0A0A` on `#FF2D95` | 5.7 |
| `ok` | `#166534` | 5.6 / 6.4 | `#4ADE80` | 11.4 / 10.6 |
| `warn` | `#92400E` | 5.6 / 6.4 | `#FBBF24` | 11.9 / 11.0 |
| `critical` | `#991B1B` | 6.5 / 7.5 | `#F87171` | 7.2 / 6.7 |
| `info` | same as `primary` | 5.9 / 6.7 | same as `primary` | 8.6 / 8.0 |
| `border-strong` (inputs, boundaries) | `#78716C` | 3.8 / 4.3 | `#737373` | 4.2 / 3.9 |
| `border-subtle` (decorative only) | `#CFCDC9` | decorative | `#262626` | decorative |
| `focus-ring` | `#1C1917` | 13.8 / 15.8 | `#7DD3FC` | 11.9 / 11.0 |

Status tints (12 % of the status color over `surface`) keep text above 4.5:1: light ok 5.4, warn 5.4, critical 6.1; dark ok 8.5, warn 8.7, critical 5.7. They are still asserted by test, not assumed.

Rules:
- Text at least 4.5:1 (large text 3:1); UI boundaries, icons and chart marks at least 3:1.
- Brand `#007BA7` as **small text** on `#0A0A0A` is 4.1:1 and fails; use `primary` (`#3DB8E0`) for text and keep `#007BA7` for fills, borders and large text.
- White text on brand `#FF2D95` is 3.5:1 and fails; pink fills use `#0A0A0A` labels.
- `critical` never uses the brand pink, so an accent is not mistaken for an alert. `critical` (`#F87171`) and the pink are both warm, so status always carries icon + text.
- A new color or a change to any derived value needs approval (section 15).

## 6. Status language

One shared vocabulary used by badges, stat cards, table cells, charts and banners.

| State | Meaning | Color token | Icon | Label example | Extra treatment |
|-------|---------|-------------|------|---------------|-----------------|
| `ok` | Within thresholds | `ok` | check-circle | "Normal" | none |
| `warn` | Approaching limit | `warn` | alert-triangle | "High" | none |
| `critical` | Beyond limit | `critical` | alert-octagon | "Critical" | none |
| `info` | Neutral notice | `info` | info | "Info" | none |
| `partial` | Only a visible subset was readable | `info` | circle-dashed or half-circle | "Partial data" | Tooltip explains why |
| `unavailable` | Not supported or not permitted on this host | `muted` | slash-circle / lock | "Not supported" or "Needs permission" | **No number, no chart**; dashed border; backend `reason` text |
| `stale` | Data older than 2x interval | `warn` (dimmed) | clock | "Updated 12 s ago" | Value at 60 % opacity, never hidden |
| `disconnected` | No live feed | `critical` (banner) | wifi-off | "Reconnecting..." | Widgets dimmed, retry status shown |
| `loading` | First data not yet received | `muted` | none | none | Skeleton with fixed size |

Rules:
- `unavailable` must never look like `ok` or like a zero. It is deliberately quiet, neutral and explanatory.
- Threshold-to-state mapping lives in `domain/thresholds.ts`, not in styling.
- Icons come from one set (e.g. `lucide-react`), 16 or 20 px, `aria-hidden` when a text label is adjacent.

## 7. Typography

- Font stack: system UI, no webfont dependency by default (`ui-sans-serif, system-ui, "Segoe UI", Roboto, sans-serif`); monospace stack for process names, paths and IDs (`ui-monospace, "SF Mono", Menlo, Consolas, monospace`). Webfonts need approval (performance, privacy).
- **Numbers**: use `font-variant-numeric: tabular-nums` for every live-changing value so digits do not jitter. Reserve width for the longest expected value (`min-width: 5ch`).
- Type scale (rem): `xs 0.75`, `sm 0.875`, `base 1`, `lg 1.125`, `xl 1.25`, `2xl 1.5`, `3xl 1.875` (hero stat). Line heights 1.25 (headings, stats) to 1.5 (body).
- Weights: 400 body, 500 labels, 600 values and headings. No more than three weights.
- Units are always shown, in `muted` color and smaller size next to the value (`72.4 %`, `1.2 GiB`, `340 MiB/s`). Use binary units (KiB, MiB, GiB) consistently or switch globally by setting, never mixed.
- Respect user font scaling; never use `px` for text.

## 8. Spacing, shape, elevation, motion, layers

- **Spacing**: 4 px base scale (`1=4, 2=8, 3=12, 4=16, 6=24, 8=32, 12=48, 16=64`). Card padding `4` (comfortable) or `3` (compact density). Gap between cards `4`.
- **Density**: `comfortable` (default) and `compact` as a root attribute (`data-density`) that swaps spacing and row-height tokens. No per-component one-offs.
- **Radius**: `sm 4`, `md 8`, `lg 12` (cards use `lg`), `full` for badges and pills.
- **Elevation**: flat by default; a single subtle shadow token for overlays (tooltip, popover). Cards are separated by `border-subtle` and a surface step, not heavy shadows. In dark mode use border and surface lightness, not shadow, to show depth.
- **Motion**: durations `fast 100 ms`, `base 200 ms`, `slow 300 ms`; easing `ease-out` for entering, `ease-in` for leaving. Never animate live metric values (no counting-up numbers, no chart animation). Wrap all non-essential motion in `@media (prefers-reduced-motion: no-preference)`.
- **Z-index tokens**: `base 0`, `sticky 10`, `overlay 20`, `modal 30`, `toast 40`. No raw z-index numbers.
- **Breakpoints**: `sm 640`, `md 768`, `lg 1024`, `xl 1280`, `2xl 1536`; content max-width token for ultrawide screens.
- **Forced colors / high contrast**: support `@media (forced-colors: active)`: keep borders on cards and badges (they carry boundaries), use system colors for focus, ensure icons are not background images.

## 9. Data visualization tokens

Chart marks need at least 3:1 against the card surface, and series must be distinguishable without color. 

| Series | Light (on `surface` `#F4F3F1`) | Dark (on `surface` `#141414`) |
|--------|-------------------------------|-------------------------------|
| 1 | `#0072B2` (4.7) | `#38A9DB` (6.9) |
| 2 | `#C2410C` (4.7) | `#E69F00` (8.2) |
| 3 | `#00875F` (4.1) | `#00B386` (6.8) |
| 4 | `#A8467F` (4.9) | `#F0E442` (13.9) |
| 5 | `#8A6D00` (4.4) | `#CC79A7` (6.0) |
| 6 | `#6D28D9` (6.4) | `#E8743B` (6.1) |
| Neutral | `#6B7280` (4.4) | `#A3A3A3` (7.3) |

Brand colors are reserved for UI chrome and are not chart series, so a brand accent is never read as data. Series colors come from the Okabe-Ito color-blind-safe family, adjusted per theme to pass 3:1 on the card surface.

Rules:
- Expose as `--chart-1 ... --chart-6, --chart-neutral`; Recharts reads them through `chart-tokens.ts`.
- Differentiate series by **line dash pattern or marker shape** as well as color when more than two series share a chart; label lines directly where space allows.
- Threshold lines use `warn` / `critical` tokens with a dashed stroke and a text label.
- Grid lines `border-subtle`; axis text `muted`, at least `xs` size; always show the unit on the axis or tooltip.
- Gaps (missing samples) are rendered as gaps, with an optional light hatched band for "unavailable" periods; never `0`.
- Percent charts use a fixed 0-100 domain; do not auto-scale a percentage to look dramatic.
- Provide a chart title, a one-sentence text summary, and a "view as table" toggle (specified here, built in `react-dashboard`).

## 10. Component specifications

Each component spec lists anatomy, variants, states, tokens. Build these primitives first, in this order; add others only on demand.

| Component | Variants | Key rules |
|-----------|----------|-----------|
| **Card** | default, compact, outlined | `surface` background, `border-subtle`, radius `lg`; header (title, optional status badge, optional actions), body, optional footer with "Updated N s ago". |
| **Stat** | sm, md, hero | Label (muted, `sm`), value (tabular, 600), unit (muted), optional delta/trend, optional status badge. Handles all states from section 6 internally. |
| **StatusBadge** | per state in section 6, sizes sm/md | Icon + label + tint; never color-only; `role="status"` only when it announces a change. |
| **ProgressBar / Gauge** | linear, segmented | Track `border-subtle`, fill by status; shows numeric value as text; threshold ticks labeled; `role="progressbar"` with `aria-valuenow`, or `meter` semantics. |
| **Sparkline** | line, area | No axes, no animation, last value marked, `aria-label` with summary. |
| **TimeSeriesChart** | line, area, stacked area | Section 9 rules; legend interactive via keyboard; tooltip also on focus. |
| **DataTable** | default, dense | Sticky header, sortable columns announce sort direction (`aria-sort`), numeric columns right-aligned and tabular, row cap, horizontal scroll container, empty and unavailable states. |
| **Banner** | info, warn, critical | Full-width; used for disconnected, stale feed, partial permissions; `role="alert"` only for new critical changes. |
| **Skeleton** | text, block, chart | Fixed dimensions equal to final content; static (no shimmer under reduced motion). |
| **Tooltip / Popover** | - | Opens on hover **and focus**, dismissible with Esc, content reachable by keyboard, never the only place for essential info. |
| **Button / IconButton / Toggle / Select / Segmented control** | primary, secondary, ghost; sm, md | Min target 44 px (touch) / 32 px (dense, pointer); visible focus ring; disabled uses `aria-disabled` and reduced contrast that still meets 3:1 for the boundary; icon buttons require an accessible name. |
| **ThemeToggle** | light / dark / system | A three-state control (not a single flip) with visible current state. |

Interaction states for every interactive component: hover (surface step, no layout change), `:focus-visible` (2 px `focus-ring` with 2 px offset, never removed), active, disabled, loading (spinner plus preserved width), error (border `critical` plus text message).

## 11. Dashboard patterns

- **Overview grid**: 4 hero stats (CPU, memory, disk, network), then time-series cards, then tables. Same card height per row to keep scanning easy.
- **Information hierarchy**: current value first, trend second, details on demand. Critical items surface to the top via a summary strip, not by reordering cards.
- **Alert presentation**: color + icon + text + timestamp; no sound; no auto-dismiss for critical.
- **Empty and unavailable are designed, not blank**: each has a title, a one-line explanation, and (if possible) a hint such as "Run with additional permissions to enable" that links to documentation.
- **Staleness**: a global "last updated" indicator in the header; stale widgets dim.
- **Process and path strings** are user-influenced: monospace, truncated with ellipsis and full text in the tooltip/title; never rendered as HTML.
- **Wall displays / TV mode** (optional, only if requested): larger type scale token set and higher density of whitespace; same colors.

## 12. Accessibility rules

- Target **WCAG 2.2 AA**.
- Contrast per section 5; focus indicators at least 3:1 and not obscured by sticky headers.
- Landmarks (`header`, `nav`, `main`), one `h1`, logical heading order, skip link.
- Everything operable by keyboard; logical tab order; no keyboard traps; visible focus.
- Live updates: do **not** announce every metric change to screen readers. Use a polite live region only for state changes (connected/disconnected, new critical alert) and rate-limit it.
- Charts and gauges have text equivalents (section 9, 10).
- Respect `prefers-reduced-motion`, `prefers-color-scheme`, `prefers-contrast`, and `forced-colors`.
- Touch targets at least 24 px by minimum standard, 44 px preferred for primary controls.
- Text can be zoomed to 200 % and reflowed at 320 px width without horizontal scrolling (tables excepted inside their scroll container).
- Semantic HTML first; ARIA only to fill gaps. Native `button`, `table`, `label`, `select` before custom widgets.

## 13. Testing and validation

| Check | Tool | Pass criterion |
|-------|------|----------------|
| Contrast matrix | `contrast.test.ts` (Vitest) computing WCAG ratios for every text/background and boundary pair in both themes, including status tints | All pairs meet the thresholds in section 5 |
| Token usage lint | Stylelint + ESLint rule, grep check in CI | Zero raw colors, hex values or arbitrary sizes outside `theme/tokens/` |
| Token parity | Unit test | Every light semantic token has a dark counterpart and vice versa |
| Accessibility | `axe` via Playwright / `vitest-axe` on Storybook or pages, both themes | No violations |
| Visual regression | Playwright screenshots (or Storybook + Chromatic if approved) for each component state, light/dark, comfortable/compact, 360 and 1280 px | No unreviewed diffs |
| Keyboard and focus | Playwright scripted tab-through | Order logical, focus always visible |
| Reduced motion / forced colors | Playwright emulation | No animation; boundaries preserved |
| Docs completeness | CI script | Every token and component appears in `docs/design-system/` |

## 14. Documentation and governance

- `docs/design-system/tokens.md`: auto-generated from token files (name, light, dark, contrast, usage).
- `components.md`: anatomy, variants, states, do/don't, accessibility notes.
- `status-language.md`: section 6 as the canonical reference.
- `changelog.md`: every token or variant change with reason, using semantic versioning for the system (breaking = renamed/removed token).
- **Deprecation**: mark, keep a codemod or alias for one release, then remove.
- **Storybook** is optional and improves review of states; it needs approval as a new dependency.
- Every PR that touches `theme/` must attach before/after screenshots in both themes.

## 15. Operations requiring user approval

Ask before:

- Changing the color system or any value in section 5 or 9.
- Adding a new design token, status state, or component variant.
- Changing component styles in a way that alters existing screens.
- Introducing a new theming system or replacing the three-tier token model.
- Adding webfonts, icon sets, Storybook, Chromatic, Style Dictionary, or any other dependency.
- Relaxing any accessibility threshold (never by default).

## 16. Common pitfalls

- Hex or pixel values written directly in components.
- Tokens named by value (`--blue-600`) instead of role (`--color-accent`).
- Dark theme made by inverting colors instead of designing its own contrast.
- Status shown by color only; red/green pairs with no icon or label.
- An unavailable metric styled like a healthy zero.
- Chart palette taken from a library default without contrast or color-blind checks.
- Proportional digits making live numbers jitter; no reserved width.
- Removing focus outlines for aesthetics.
- Animating live values or charts.
- Announcing every update to screen readers.
- Using shadows for depth in dark mode where they are invisible.
- Variant explosion: ten button styles used once each.
- Documentation that drifts from tokens because it is hand-written.
- Verifying contrast in one theme only.

## 17. Definition of done

- [ ] All three token tiers defined; components consume only semantic or component tokens.
- [ ] Light and dark themes have full token parity and verified contrast (automated test passing).
- [ ] Status language implemented identically across badges, stats, tables, charts and banners; unavailable, partial and stale states specified and built.
- [ ] Every component documented with anatomy, variants and all interaction states.
- [ ] Chart palette verified (3:1 minimum) and series distinguishable without color.
- [ ] Token-usage lint passes: no raw colors or arbitrary values outside the token files.
- [ ] Accessibility checks pass in both themes, including keyboard, reduced motion, forced colors and 200 % zoom.
- [ ] Visual regression baselines recorded for all states, both themes, both densities, mobile and desktop.
- [ ] Documentation and changelog current; generated token docs match the source.
- [ ] Any new dependency or token addition approved.

## 18. Dependencies

**Core:** `tailwindcss` (preset mapped to semantic tokens), one icon set (`lucide-react`), CSS custom properties (native, no package).

**Test and quality:** `vitest` (contrast and parity tests), `@playwright/test`, `vitest-axe` or `@axe-core/playwright`, `stylelint`, `eslint`.

**Optional (approval required):** `storybook`, `chromatic`, `style-dictionary` (only if tokens must also feed non-web targets), webfonts, headless accessible primitives such as Radix.