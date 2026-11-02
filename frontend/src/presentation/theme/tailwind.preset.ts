import type { Config } from "tailwindcss";

const color = (token: string) => `rgb(var(--${token}) / <alpha-value>)`;

export const preset: Partial<Config> = {
  darkMode: ["selector", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        bg: color("color-bg"),
        surface: color("color-surface"),
        "surface-alt": color("color-surface-alt"),
        text: color("color-text"),
        muted: color("color-muted"),
        primary: color("color-primary"),
        "primary-fill": color("color-primary-fill"),
        secondary: color("color-secondary"),
        "secondary-fill": color("color-secondary-fill"),
        ok: color("color-ok"),
        warn: color("color-warn"),
        critical: color("color-critical"),
        info: color("color-info"),
        "border-strong": color("color-border-strong"),
        "border-subtle": color("color-border-subtle"),
        "focus-ring": color("color-focus-ring"),
        chart: {
          1: color("chart-1"),
          2: color("chart-2"),
          3: color("chart-3"),
          4: color("chart-4"),
          5: color("chart-5"),
          6: color("chart-6"),
          neutral: color("chart-neutral"),
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)"],
        mono: ["var(--font-mono)"],
      },
      fontSize: {
        xs: ["var(--font-size-xs)", { lineHeight: "1.25" }],
        sm: ["var(--font-size-sm)", { lineHeight: "1.25" }],
        base: ["var(--font-size-base)", { lineHeight: "1.5" }],
        lg: ["var(--font-size-lg)", { lineHeight: "1.25" }],
        xl: ["var(--font-size-xl)", { lineHeight: "1.25" }],
        "2xl": ["var(--font-size-2xl)", { lineHeight: "1.25" }],
        "3xl": ["var(--font-size-3xl)", { lineHeight: "1.25" }],
      },
      spacing: {
        1: "var(--space-1)",
        2: "var(--space-2)",
        3: "var(--space-3)",
        4: "var(--space-4)",
        6: "var(--space-6)",
        8: "var(--space-8)",
        12: "var(--space-12)",
        16: "var(--space-16)",
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
        full: "var(--radius-full)",
      },
    },
  },
};
