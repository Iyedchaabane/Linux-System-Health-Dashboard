import { describe, expect, it, vi, beforeEach } from "vitest";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeProvider, useTheme } from "../../src/presentation/theme/ThemeProvider";
import { ThemeToggle } from "../../src/presentation/theme/ThemeToggle";

function Consumer() {
  const { preference, theme } = useTheme();
  return <span data-testid="state">{preference}:{theme}</span>;
}

describe("ThemeProvider", () => {
  beforeEach(() => {
    localStorage.clear();
    // default system light
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: (query: string) => ({
        matches: false,
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

  it("defaults to system", () => {
    render(<ThemeProvider><Consumer /></ThemeProvider>);
    expect(screen.getByTestId("state").textContent).toBe("system:light");
  });

  it("supports initialPreference", () => {
    render(<ThemeProvider initialPreference="dark"><Consumer /></ThemeProvider>);
    expect(screen.getByTestId("state").textContent).toBe("dark:dark");
  });

  it("light/dark/system via setPreference persists", async () => {
    const user = userEvent.setup();
    function C() {
      const { setPreference, preference, theme } = useTheme();
      return (
        <>
          <button onClick={() => setPreference("dark")}>dark</button>
          <button onClick={() => setPreference("light")}>light</button>
          <button onClick={() => setPreference("system")}>system</button>
          <span>{preference}:{theme}</span>
        </>
      );
    }
    render(<ThemeProvider><C /></ThemeProvider>);
    await user.click(screen.getByText("dark"));
    expect(localStorage.getItem("theme")).toBe("dark");
    expect(screen.getByText("dark:dark")).toBeTruthy();
    await user.click(screen.getByText("light"));
    expect(localStorage.getItem("theme")).toBe("light");
    expect(screen.getByText("light:light")).toBeTruthy();
  });

  it("toggle cycles light->dark->system (starting system)", () => {
    function C() {
      const { toggle, preference } = useTheme();
      return <button onClick={toggle}>{preference}</button>;
    }
    render(<ThemeProvider initialPreference="system"><C /></ThemeProvider>);
    const btn = screen.getByRole("button");
    expect(btn.textContent).toBe("system");
    act(() => { btn.click(); });
    expect(screen.getByRole("button").textContent).toBe("light");
    act(() => { screen.getByRole("button").click(); });
    expect(screen.getByRole("button").textContent).toBe("dark");
  });

  it("safe storage: blocked localStorage falls back to system", () => {
    const getItemSpy = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
    const setItemSpy = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
    render(<ThemeProvider><Consumer /></ThemeProvider>);
    expect(screen.getByTestId("state").textContent).toBe("system:light");
    getItemSpy.mockRestore();
    setItemSpy.mockRestore();
  });

  it("system mode reacts to media changes", () => {
    const mql: { matches: boolean; addEventListener: (ev: string, cb: () => void) => void } & Record<string, unknown> = {
      matches: false,
      media: "",
      onchange: null,
      addEventListener: (ev: string, cb: () => void) => { if (ev === "change") changeHandler = cb; },
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    };
    let changeHandler: (() => void) | null = null;
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: () => mql,
    });
    function C() {
      const { theme } = useTheme();
      return <span>{theme}</span>;
    }
    render(<ThemeProvider initialPreference="system"><C /></ThemeProvider>);
    expect(screen.getByText("light")).toBeTruthy();
    mql.matches = true;
    act(() => { changeHandler?.(); });
    expect(screen.getByText("dark")).toBeTruthy();
  });

  it("data-theme attribute applied", () => {
    render(<ThemeProvider initialPreference="dark"><Consumer /></ThemeProvider>);
    expect(document.documentElement.dataset.theme).toBe("dark");
  });
});

describe("ThemeToggle", () => {
  it("renders and cycles", async () => {
    const user = userEvent.setup();
    render(<ThemeProvider><ThemeToggle /></ThemeProvider>);
    const btn = screen.getByRole("button");
    expect(btn).toHaveAttribute("aria-label");
    await user.click(btn);
    // no crash
  });
});