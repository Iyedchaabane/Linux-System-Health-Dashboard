import { AppWindow } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import * as React from "react";
import { useState } from "react";

export type ProcessIconResolution =
  | { kind: "brand"; src: string; key: string }
  | { kind: "fallback"; icon: LucideIcon };

/**
 * Brand assets are withheld pending exact-source and redistribution evidence.
 * Keep the public resolution contract; names, paths and URLs remain neutral.
 */
export function resolveProcessIcon(name: string): ProcessIconResolution {
  void name;
  return { kind: "fallback", icon: AppWindow };
}

/** Convenience fallback exported for callers that want the generic icon. */
export const fallbackProcessIcon: LucideIcon = AppWindow;

type ProcessIconProps = {
  name: string;
  className?: string;
  "data-testid"?: string;
};

/** React component rendering the resolved icon at the requested size. */
export function ProcessIcon({
  name,
  className,
  "data-testid": testId,
}: ProcessIconProps): React.ReactElement {
  const resolved = resolveProcessIcon(name);
  const [failedSources, setFailedSources] = useState<ReadonlySet<string>>(
    () => new Set(),
  );

  if (resolved.kind === "brand" && !failedSources.has(resolved.src)) {
    return React.createElement("img", {
      src: resolved.src,
      alt: "",
      "aria-hidden": "true",
      className,
      width: 16,
      height: 16,
      "data-testid": testId,
      onError: () =>
        setFailedSources((previous) => {
          if (previous.has(resolved.src)) return previous;
          return new Set([...previous, resolved.src]);
        }),
    } as React.ImgHTMLAttributes<HTMLImageElement>);
  }

  const Icon = resolved.kind === "fallback" ? resolved.icon : AppWindow;
  return React.createElement(Icon, {
    "aria-hidden": "true",
    className,
    size: 16,
    "data-testid": testId,
  } as React.ComponentProps<typeof AppWindow>);
}
