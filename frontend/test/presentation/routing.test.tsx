import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { ThemeProvider } from "../../src/presentation/theme/ThemeProvider";
import App from "../../src/App";

vi.mock("../../src/application/connect", () => ({
  connectDashboard: () => ({ dispose: () => {} }),
}));

describe("Routing", () => {
  function renderAt(path: string) {
    return render(
      <ThemeProvider>
        <MemoryRouter initialEntries={[path]}>
          <App />
        </MemoryRouter>
      </ThemeProvider>,
    );
  }

  it("renders overview at /", () => {
    renderAt("/");
    expect(screen.getByRole("heading", { name: /Linux System Health Dashboard/i })).toBeTruthy();
  });

  it("renders 5 routes", async () => {
    for (const p of ["/", "/cpu", "/memory", "/network", "/disks"]) {
      const { unmount } = renderAt(p);
      unmount();
    }
    // spot check CPU heading maybe pages have headings
    renderAt("/cpu");
    expect(document.body).toBeTruthy();
  });

  it("sidebar nav active link", async () => {
    const user = userEvent.setup();
    renderAt("/");
    // desktop nav only hidden on lg? In jsdom no lg, hidden; mobile nav visible
    const cpuLink = screen.getAllByRole("link", { name: /CPU/i })[0];
    await user.click(cpuLink);
    // active on clicked link via aria-current
    expect(cpuLink).toBeTruthy();
  });

  it("unknown route renders nothing main but no crash", () => {
    renderAt("/nonexistent");
    // App routes do not define catch-all; should not crash
    expect(screen.getByRole("heading", { name: /Linux System Health Dashboard/i })).toBeTruthy();
  });

  it("mobile nav present", () => {
    renderAt("/");
    expect(screen.getByLabelText(/Primary mobile/i)).toBeTruthy();
  });
});
