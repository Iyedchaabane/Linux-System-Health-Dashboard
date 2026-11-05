import { describe, expect, it, vi, beforeAll } from "vitest";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ThemeProvider } from "../../src/presentation/theme/ThemeProvider";
import App from "../../src/App";
import axe from "axe-core";

vi.mock("../../src/application/connect", () => ({
  connectDashboard: () => ({ dispose: () => {} }),
}));

// Disable animations via prefers-reduced-motion
beforeAll(() => {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      matches: query.includes("prefers-reduced-motion"),
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }),
  });
});

async function runAxe(theme: "light" | "dark") {
  const { container } = render(
    <ThemeProvider initialPreference={theme}>
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    </ThemeProvider>,
  );
  const results = await axe.run(container, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa"] } });
  return results;
}

describe("Accessibility axe", () => {
  it("light theme has no serious/critical violations", async () => {
    const r = await runAxe("light");
    const bad = r.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
    if (bad.length) console.log(JSON.stringify(bad.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length })), null, 2));
    expect(bad).toHaveLength(0);
  });

  it("dark theme has no serious/critical violations", async () => {
    const r = await runAxe("dark");
    const bad = r.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
    if (bad.length) console.log(JSON.stringify(bad.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length })), null, 2));
    expect(bad).toHaveLength(0);
  });
});
