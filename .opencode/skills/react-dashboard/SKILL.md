---
name: react-dashboard
description: >
  Build and review the React + TypeScript + Vite + Tailwind + Recharts frontend
  of a real-time system health dashboard. Use this skill whenever the user
  mentions React components, dashboard UI, charts or graphs of live metrics,
  Recharts, Tailwind layout, dark/light themes or color tokens, WebSocket
  client or reconnection, live-updating state, responsive or mobile layout,
  accessibility of charts, frontend testing (Vitest, Testing Library,
  Playwright), or bundle/render performance, even if they only say "frontend",
  "UI" or "make it look good". Also use it when rendering unavailable, partial
  or stale metrics, or when a chart re-renders too often.
---

# React Dashboard Skill

Guidance for the frontend of the **Linux system health dashboard**. It consumes
the API defined by the `python-backend` skill and displays data produced under
the rules of the `linux-monitoring` skill. The UI must stay honest about missing
data, stay fast under a continuous stream, and be usable by everyone.

## 1. Non-negotiable rules

| # | Rule | Why |
|---|------|-----|
| 1 | **Never display a fake value for missing data.** `unavailable`, `partial` and `stale` are first-class UI states. Never show `0`, `--%` styled as normal, or an empty chart. | Mirrors the backend rule; a fake `0 °C` looks healthy. |
| 2 | **Validate every server message at runtime** (Zod or equivalent) before it enters state. TypeScript types alone do not protect against bad data. | Contract drift must fail loudly in one place. |
| 3 | **Bound everything**: history window, points per chart, connection retries, rendered table rows. | A dashboard left open for days must not leak memory or lag. |
| 4 | **Live data lives outside React render churn.** Store updates are throttled and components subscribe to narrow selectors. | 1 Hz x many widgets re-rendering the whole tree is the top performance bug. |
| 5 | **Color is never the only signal.** Pair with text, icon or shape; meet WCAG AA contrast. | Accessibility and honest status display. |
| 6 | **Components do not talk to the network.** Only the infrastructure layer does. | Testability and swappable transports. |
| 7 | **All colors, spacing and radii come from tokens.** No hard-coded hex values in components. | One place to change themes, guaranteed dark/light parity. |

## 2. Workflow

1. **Read the contract**: REST schemas and WebSocket protocol from `python-backend` (envelope `v`, `type`, `seq`, `ts`, `data`). Get approval before assuming changes (section 12).
2. **Model types and Zod schemas** that mirror the contract, including the `ok | unavailable` metric shape.
3. **Build infrastructure**: REST client, WebSocket client with reconnection.
4. **Build application layer**: live store, selectors, hooks.
5. **Build design tokens and theme**, then **primitive components**, then **widgets**, then **pages**.
6. **Cover all states** for every widget: loading, ok, partial, unavailable, stale, disconnected, error.
7. **Test** (section 10), **measure performance** (section 9), **check accessibility**.

## 3. Architecture (clean layering on the frontend)

Dependencies point inward: `presentation -> application -> domain`; `infrastructure` implements what application needs.

```
src/
├── domain/                     # Pure TS. No React, no fetch, no browser APIs.
│   ├── metrics.ts              # MetricValue<T>, Snapshot, units
│   ├── thresholds.ts           # status from value (ok/warn/critical), pure functions
│   ├── format.ts               # formatBytes, formatPercent, formatDuration, formatRate
│   └── history.ts              # appendBounded(), downsample()
├── infrastructure/
│   ├── api/                    # REST client, Zod schemas, error mapping
│   ├── ws/                     # MetricsSocket (reconnect, heartbeat, seq tracking)
│   └── storage/                # safe localStorage wrapper (theme, settings)
├── application/
│   ├── stores/                 # live metrics store, connection store, settings store
│   ├── hooks/                  # useMetric(selector), useConnectionStatus, useTheme
│   └── services/               # startLiveFeed(): wires socket -> validation -> store
├── presentation/
│   ├── components/ui/          # primitives: Card, Badge, Stat, Skeleton, Tooltip, Button
│   ├── components/charts/      # TimeSeriesChart, Sparkline, GaugeBar (Recharts wrappers)
│   ├── features/               # cpu/, memory/, disk/, network/, processes/, system/
│   ├── layouts/                # DashboardLayout, Sidebar, Header
│   ├── pages/
│   └── theme/                  # tokens.css, tailwind preset, ThemeProvider
├── app/                        # main.tsx, providers, routes, error boundary
└── test/                       # setup, fixtures, MSW handlers, fake socket
```

Rules:

- `domain/` imports nothing from the other layers or from React.
- Feature folders hold their own widget, hook and tests; shared pieces move to `ui/` only after a second use.
- Use **`import-x` / `eslint-plugin-boundaries`** (or `dependency-cruiser`) to enforce the direction in CI.
- Prefer **composition and small components** (target under about 150 lines each); lift logic into hooks and pure functions.

## 4. Types: represent missing data explicitly

Align names with the backend schema. Adjust if the contract differs.

```ts
// domain/metrics.ts
export type UnavailableKind = "unsupported" | "permission" | "transient" | "disabled";

export type MetricValue<T> =
  | { status: "ok"; value: T; partial?: boolean }
  | { status: "unavailable"; kind: UnavailableKind; reason: string };

export interface CpuSnapshot {
  percentTotal: MetricValue<number>;      // 0..100
  perCore: MetricValue<number[]>;
  loadAvg: MetricValue<[number, number, number]>;
  coreCount: number;
}
```

- Use TypeScript `strict: true`, `noUncheckedIndexedAccess: true`, no `any`; `unknown` plus parsing at boundaries.
- Discriminated unions for states; exhaustive `switch` with a `never` check.
- Parse with Zod (`schema.safeParse`); invalid messages are counted, logged at debug level, and dropped, never stored.
- Branded or aliased unit types (`Bytes`, `Percent`) in `domain` to avoid unit mix-ups.

## 5. Live data: WebSocket client and state

### 5.1 Socket client (infrastructure)

Requirements:

- Connect to `/ws/v1/metrics` (derive URL from `window.location`, use `wss:` on https; dev proxy configured in Vite).
- **Reconnect with exponential backoff and jitter** (e.g. 1 s doubling to 30 s, +/- 20 %), reset on a stable connection.
- Track `seq`: a gap triggers a **resync** via `GET /api/v1/snapshot` and a "data gap" marker in history. Do not assume replay.
- Heartbeat: answer server `ping`; treat no message for `2 x interval + margin` as **stale** and force a reconnect.
- Pause or close the socket when the tab is hidden for a long time (`visibilitychange`) if the setting allows; resync on return.
- Expose connection state: `connecting | open | reconnecting | closed` plus `lastMessageAt`.
- Handle close codes: `1013` (server full) means longer backoff; `1008` (policy) means stop and show a clear error, no retry loop.
- Send only allowlisted client messages.

```ts
// infrastructure/ws/backoff.ts
export const nextDelay = (attempt: number, base = 1000, cap = 30000, rand = Math.random) => {
  const exp = Math.min(cap, base * 2 ** attempt);
  return exp * (0.8 + rand() * 0.4);         // jitter, injectable RNG for tests
};
```

### 5.2 Store (application)

- One store library: **Zustand** with selector subscriptions (small, no provider needed, easy to test). Do not mix with Redux.
- Keep `latest` snapshot separate from `history` (bounded ring: `maxPoints = windowSeconds / interval`).
- **Throttle UI updates** to at most one commit per animation frame or per second; the socket may be faster than the screen.
- Components use narrow selectors (`useStore(s => s.latest.cpu.percentTotal)`), never the whole store.
- **TanStack Query** for REST (snapshot resync, system info, history on first load): caching, retries, and `staleTime` are handled; do not hand-roll fetch state.
- Server state is not copied into component state.

## 6. Components and states

Every widget implements all of these, with a test for each:

| State | Display |
|-------|---------|
| Loading (no data yet) | Skeleton with fixed dimensions (no layout shift) |
| OK | Value with unit, trend or chart |
| Partial | Value plus a visible "partial data" badge and tooltip explaining why |
| Unavailable | Neutral card: "Not supported on this host" or "Needs elevated permission" using the `reason`; no number, no empty chart |
| Stale | Dimmed value, "Updated 12 s ago" label, warning badge |
| Disconnected | Global banner plus dimmed widgets; retry status visible |
| Error | Error boundary fallback per widget, so one failure never blanks the page |

Guidelines:

- Wrap each feature in its own **error boundary**.
- Provide a `<MetricState>` wrapper component that renders the states above so widgets stay small and consistent.
- Status is derived in `domain/thresholds.ts` (pure, unit-tested), not inside JSX.
- Use stable `key`s, `React.memo` on pure presentational widgets, `useMemo` only for measured hot spots. Do not memoize everything by default.
- Forms and settings (interval, theme, window) are controlled, validated, and clamp to backend-allowed ranges.

## 7. Charts with Recharts

- Wrap Recharts in project components (`TimeSeriesChart`, `Sparkline`) so the library is replaceable and defaults are consistent.
- For streaming data: `isAnimationActive={false}`, `dot={false}`, fixed `YAxis` domain for percentages (`[0, 100]`), `type="monotone"` optional.
- **Limit points** (e.g. 60 to 300 per series); **downsample** older history (min/max bucket) rather than rendering thousands of SVG nodes.
- Use `ResponsiveContainer` inside a parent with an explicit height to avoid zero-size charts.
- Render **gaps** for missing samples (`null` values with `connectNulls={false}`), never interpolate across unavailable data and never plot `0`.
- Format ticks and tooltips with `domain/format.ts` (units always visible).
- Memoize the data array passed to the chart so unrelated store updates do not re-render it.
- **Accessibility**: give each chart a text title and summary (`role="img"` with `aria-label` or `aria-describedby`), and offer a "View as table" toggle with the same data. Use colors with patterns or labeled direct values, not color alone. Respect `prefers-reduced-motion`.
- If a chart still lags at the target rate, profile first (React Profiler). Switch to canvas-based charts only with approval (section 12).

## 8. Theming, tokens, and responsive design

### Tokens

Define semantic tokens as CSS variables and map Tailwind to them.

```css
/* presentation/theme/tokens.css */
:root {
  --color-bg: 255 255 255;
  --color-surface: 248 250 252;
  --color-text: 15 23 42;
  --color-muted: 71 85 105;
  --color-ok: 22 101 52;
  --color-warn: 146 64 14;
  --color-critical: 153 27 27;
  --color-accent: 29 78 216;
  --radius-card: 0.75rem;
}
:root[data-theme="dark"] {
  --color-bg: 2 6 23;
  --color-surface: 15 23 42;
  --color-text: 226 232 240;
  --color-muted: 148 163 184;
  --color-ok: 74 222 128;
  --color-warn: 251 191 36;
  --color-critical: 248 113 113;
  --color-accent: 96 165 250;
}
```

```ts
// tailwind preset (v3 style shown; use the equivalent @theme mapping in v4)
colors: { bg: "rgb(var(--color-bg) / <alpha-value>)", surface: "rgb(var(--color-surface) / <alpha-value>)",
          ok: "rgb(var(--color-ok) / <alpha-value>)" /* ... */ }
```

- Use **semantic names** (`ok`, `warn`, `critical`, `surface`), not raw palette names, in components.
- Theme modes: `light | dark | system`. Default `system` via `prefers-color-scheme`; apply `data-theme` **before first paint** (small inline script in `index.html`) to avoid a flash.
- Persist the choice via the safe storage wrapper (`try/catch`; the app must work when storage is blocked).
- Charts read colors from tokens (via `getComputedStyle` or CSS variables in SVG props) so they follow the theme.
- Verify AA contrast (4.5:1 text, 3:1 UI) for **both** themes; automate with axe and a token-contrast unit test.

### Responsive

- **Mobile-first** Tailwind classes; layout with CSS grid (`grid-cols-1 sm:grid-cols-2 xl:grid-cols-4`), cards with `min-w-0` to prevent overflow.
- Tables (processes, mounts) scroll inside their own `overflow-x-auto` container or collapse to a card list on small screens.
- Touch targets at least 44 px; no hover-only information.
- Test at 360, 768, 1280 and 1920 px widths; wide ultrawide layouts cap content width.
- Respect user text scaling (`rem` units).

## 9. Performance

- Targets (tune per host): initial JS under about 200 KB gzip for the main route; first meaningful paint under 2 s on a mid-range laptop; steady state under 5 % main-thread CPU at 1 Hz with all widgets visible; no heap growth over a 1-hour soak.
- Route-level **code splitting** (`React.lazy`) and lazy-load the charts bundle; analyze with `rollup-plugin-visualizer`.
- Import named icons only; avoid pulling full icon sets or utility libraries (`lodash` whole-package).
- Virtualize long lists (process table beyond about 100 rows; otherwise cap rows server-side via `limit`).
- Avoid layout shift: fixed skeleton sizes, reserved chart heights.
- Use React Profiler and Chrome Performance panel before optimizing; record results.
- Production build via Vite with hashed assets, gzip/brotli served by the backend or reverse proxy.

## 10. Testing strategy

| Layer | What to test | Tools |
|-------|--------------|-------|
| Unit (domain) | thresholds, formatters, bounded history, downsampling, backoff delay | **Vitest** (Vite-native; do not use Jest here) |
| Schema | Zod accepts valid fixtures, rejects malformed or unknown messages | Vitest with recorded real payloads in `test/fixtures/` |
| Socket client | reconnect timing, jitter, seq gap triggers resync, close-code handling, stale detection | Vitest fake timers + fake WebSocket |
| Store / hooks | throttling, bounded history, selector isolation | Vitest + `@testing-library/react` `renderHook` |
| Components | every state in section 6, labels, units, keyboard interaction | Testing Library, `user-event`, MSW for REST |
| Accessibility | axe violations, landmarks, focus order, contrast in both themes | `vitest-axe` / `@axe-core/playwright` |
| Visual | snapshot of key widgets in light/dark and mobile/desktop | Playwright screenshots (use sparingly, review diffs) |
| E2E | app boots against a stub or real backend; disconnect and recovery; theme persists | **Playwright** |
| Performance | render counts of widgets per update, bundle size budget | Profiler tests, `size-limit` in CI |

Rules:

- Test behavior and visible output, not implementation details; query by role and label.
- Never hard-code fake metrics in production code; fixtures and fakes live under `test/`.
- Coverage: **>= 85 % overall, >= 95 % on `domain/` and `infrastructure/ws`**. Coverage is a floor, not proof.
- Tooling in CI: `tsc --noEmit`, ESLint (`typescript-eslint`, `jsx-a11y`, `react-hooks`), Prettier, Vitest, Playwright, `size-limit`, `npm audit`.

## 11. Security and configuration

- React escapes by default. **Never use `dangerouslySetInnerHTML`** with server data (process names and command lines are attacker-influenced strings).
- Keep a strict Content Security Policy compatible with the build (no inline scripts except the hashed theme bootstrap), served by the backend or proxy.
- `VITE_*` variables are **public**; never put secrets or tokens in them. Auth tokens, if used, live in memory or an `HttpOnly` cookie and never in logs or URLs shown to the user.
- Do not log full server payloads or command lines in the browser console in production.
- Runtime config: API base URL and WebSocket path via env at build time or `/config.json` at runtime; validate with Zod on startup.
- Dev server: Vite `server.proxy` for `/api` and `/ws` (with `ws: true`) so no CORS needed in development.
- Serve over HTTPS when not on localhost; use `wss:` accordingly.
- Keep the UI read-only, matching the API; no controls that imply host mutation.

## 12. Operations requiring user approval

Ask before:

- Adding any UI or component library (MUI, Ant Design, Chakra, Radix/shadcn primitives, Emotion, styled-components). The default is Tailwind plus small in-house primitives. Accessible headless primitives (Radix or similar) are the first thing to propose when a complex widget is needed.
- Adding state or data libraries beyond Zustand and TanStack Query.
- Changing the component architecture or layering rules.
- Introducing a new theming system or changing the token structure.
- Changing build configuration (Vite config, chunking, target browsers, CSP).
- Replacing Recharts with canvas or WebGL charting.
- Changing assumptions about the API or WebSocket contract.

## 13. Common pitfalls

- Plotting `0` or interpolating through missing samples.
- Treating `null`, `0` and "unavailable" as the same thing.
- Re-rendering the whole dashboard on every message because components subscribe to the entire store.
- Unbounded history arrays, or too many SVG points per chart.
- Recharts animation left on for streaming data.
- `ResponsiveContainer` inside a parent without a height (invisible chart).
- Hard-coded colors that break in dark mode; charts not following the theme.
- Flash of the wrong theme because it is applied after first paint.
- No reconnect backoff (hammering the server), or no resync after a gap.
- Mixing component state, store state and query cache for the same data.
- Missing stale and disconnected states: the screen looks live while the data is minutes old.
- Using Jest in a Vite project, creating duplicate transform configs.
- Mixing several styling systems and UI kits in one app.
- Color-only status indicators and charts without text alternatives.
- Rendering unsanitized HTML from process names.

## 14. Definition of done

- [ ] Every widget handles loading, ok, partial, unavailable, stale, disconnected and error states, each tested.
- [ ] No fake or placeholder metric values anywhere; unavailable metrics show the backend-provided reason.
- [ ] All server messages validated by Zod; invalid ones dropped and counted.
- [ ] WebSocket client: backoff with jitter, seq gap resync, heartbeat or stale detection, close-code handling, all tested.
- [ ] History and rendered points bounded; 1-hour soak shows no memory growth; performance targets in section 9 met and recorded.
- [ ] Tokens drive all colors; light, dark and system themes verified; no flash on load; contrast AA in both themes.
- [ ] Layout verified at 360, 768, 1280 and 1920 px with no horizontal page scroll.
- [ ] Charts have text alternatives and a table view; keyboard navigation and focus order verified; axe reports no violations.
- [ ] Layer boundaries enforced in CI; `tsc`, ESLint, Vitest, Playwright and bundle-size checks pass.
- [ ] No `dangerouslySetInnerHTML`, no secrets in `VITE_*`, CSP configured.
- [ ] Contract assumptions documented and matching the `python-backend` schemas.

## 15. Dependencies

**Core:** `react`, `react-dom`, `typescript`, `vite`, `tailwindcss`, `recharts`, `zod`, `zustand`, `@tanstack/react-query`, `react-router-dom` (only if more than one page)

**Dev and test:** `vitest`, `@testing-library/react`, `@testing-library/user-event`, `@testing-library/jest-dom`, `jsdom`, `msw`, `@playwright/test`, `vitest-axe` or `@axe-core/playwright`, `eslint` with `typescript-eslint`, `eslint-plugin-react-hooks`, `eslint-plugin-jsx-a11y`, `prettier`, `size-limit`, `rollup-plugin-visualizer`, `dependency-cruiser` or `eslint-plugin-boundaries`

**Not included by default (approval required, see section 12):** Redux or RTK Query, Emotion, styled-components, Material-UI, Ant Design, Chakra UI, canvas chart libraries.

Pin versions with a lockfile and run `npm audit` in CI.