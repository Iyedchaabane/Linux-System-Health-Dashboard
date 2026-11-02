import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

export type ThemePreference = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

interface ThemeContextValue {
  preference: ThemePreference;
  theme: ResolvedTheme;
  setPreference: (p: ThemePreference) => void;
  toggle: () => void;
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

const STORAGE_KEY = "theme";

function readStoredPreference(): ThemePreference {
  try {
    const v = window.localStorage.getItem(STORAGE_KEY);
    if (v === "light" || v === "dark" || v === "system") return v;
  } catch {
    // storage may be blocked; fall back to system
  }
  return "system";
}

function writeStoredPreference(pref: ThemePreference): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, pref);
  } catch {
    // ignore blocked storage
  }
}

function resolvePreference(pref: ThemePreference): ResolvedTheme {
  if (pref === "light") return "light";
  if (pref === "dark") return "dark";
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

const CYCLE: ThemePreference[] = ["light", "dark", "system"];

export interface ThemeProviderProps {
  children: React.ReactNode;
  initialPreference?: ThemePreference;
}

export function ThemeProvider({ children, initialPreference }: ThemeProviderProps) {
  const [preference, setPreferenceState] = useState<ThemePreference>(
    initialPreference ?? readStoredPreference(),
  );
  const [resolved, setResolved] = useState<ResolvedTheme>(() => resolvePreference(initialPreference ?? readStoredPreference()));

  const applyResolved = useCallback((next: ResolvedTheme) => {
    if (typeof document !== "undefined") {
      document.documentElement.dataset.theme = next;
    }
  }, []);

  const setPreference = useCallback((next: ThemePreference) => {
    setPreferenceState(next);
    writeStoredPreference(next);
    const r = resolvePreference(next);
    setResolved(r);
    applyResolved(r);
  }, [applyResolved]);

  const toggle = useCallback(() => {
    setPreferenceState((prev) => {
      const idx = CYCLE.indexOf(prev);
      const next = CYCLE[(idx + 1) % CYCLE.length];
      writeStoredPreference(next);
      const r = resolvePreference(next);
      setResolved(r);
      applyResolved(r);
      return next;
    });
  }, [applyResolved]);

  // React to system changes only while in "system" mode.
  useEffect(() => {
    if (preference !== "system") return;
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    const mql = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => {
      const r = mql.matches ? "dark" : "light";
      setResolved(r);
      applyResolved(r);
    };
    if (typeof mql.addEventListener === "function") {
      mql.addEventListener("change", handler);
    } else {
      // Safari < 14 fallback
      mql.addListener(handler);
    }
    return () => {
      if (typeof mql.removeEventListener === "function") {
        mql.removeEventListener("change", handler);
      } else {
        mql.removeListener(handler);
      }
    };
  }, [preference, applyResolved]);

  // Initial apply (covers SSR / tests where effect ordering matters)
  useEffect(() => {
    applyResolved(resolved);
  }, [applyResolved, resolved]);

  const value = useMemo<ThemeContextValue>(
    () => ({ preference, theme: resolved, setPreference, toggle }),
    [preference, resolved, setPreference, toggle],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}
