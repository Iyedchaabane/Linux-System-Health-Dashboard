import { Moon, Monitor, Sun } from "lucide-react";
import { useTheme } from "./ThemeProvider";

export function ThemeToggle() {
  const { preference, theme, setPreference } = useTheme();
  const resolvedTheme = theme;
  const cycle = () => {
    const next = preference === "system" ? "light" : preference === "light" ? "dark" : "system";
    setPreference(next);
  };
  const Icon = resolvedTheme === "dark" ? Moon : Sun;
  return (
    <button
      type="button"
      onClick={cycle}
      className="inline-flex items-center gap-2 rounded-pill border border-border-strong bg-surface px-3 py-1.5 text-sm text-text"
      aria-label={`Theme switch: currently ${preference}`}
    >
      <Icon aria-hidden="true" className="h-4 w-4" />
      <Monitor aria-hidden="true" className="h-4 w-4 text-muted" />
      <span className="hidden sm:inline">{preference}</span>
    </button>
  );
}
