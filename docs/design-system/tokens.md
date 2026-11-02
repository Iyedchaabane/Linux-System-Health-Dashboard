# Design tokens

Tokens are defined in three tiers under `frontend/src/presentation/theme/tokens/`:

1. `primitives.css` — raw scales (spacing, radii, z-index, motion, typography). Private; components do not consume.
2. `semantic.css` — light theme semantic tokens (default).
3. `semantic.dark.css` — dark overrides via `[data-theme="dark"]`.

Values are space-separated RGB triples (`R G B`) so Tailwind alpha utilities work: `rgb(var(--color-bg) / <alpha-value>)`.

Tailwind mapping lives in `frontend/src/presentation/theme/tailwind.preset.ts`.

Theme switching is handled by `ThemeProvider.tsx` (`useTheme`), persisting to `localStorage["theme"]` and applying `data-theme` before first paint via the inline script in `index.html`.

Charts read their palette through `chart-tokens.ts` (`readChartTokens`), which reads the CSS variables at runtime with fallbacks.

Generated docs should list name, light value, dark value, contrast, and usage; update this file (or regenerate) whenever tokens change.
