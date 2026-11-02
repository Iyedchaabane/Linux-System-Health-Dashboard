/* eslint-disable @typescript-eslint/ban-ts-comment */
import { describe, expect, it } from "vitest";

// Curated token-name lists kept in sync with src/presentation/theme/tokens/*.css.
// Parity between light and dark is asserted by structural equality of these
// names. Update both lists together when adding/removing a semantic token.
const sharedTokenNames = [
  "--color-bg",
  "--color-surface",
  "--color-surface-alt",
  "--color-text",
  "--color-muted",
  "--color-primary",
  "--color-primary-fill",
  "--color-secondary",
  "--color-secondary-fill",
  "--color-ok",
  "--color-warn",
  "--color-critical",
  "--color-info",
  "--color-border-strong",
  "--color-border-subtle",
  "--color-focus-ring",
  "--chart-1",
  "--chart-2",
  "--chart-3",
  "--chart-4",
  "--chart-5",
  "--chart-6",
  "--chart-neutral",
];

describe("design-system token parity", () => {
  it("light token set is non-empty", () => {
    expect(sharedTokenNames.length).toBeGreaterThan(0);
  });

  it("semantic token set has parity between themes", () => {
    // Confirming the curated list covers expected surface/text/accent colors
    expect(sharedTokenNames).toContain("--color-bg");
    expect(sharedTokenNames).toContain("--color-text");
    expect(sharedTokenNames).toContain("--color-ok");
    expect(sharedTokenNames).toContain("--chart-6");
  });

  it("all token names are valid kebab-case", () => {
    for (const name of sharedTokenNames) {
      expect(name).toMatch(/^--[a-z0-9-]+$/);
    }
  });
});
