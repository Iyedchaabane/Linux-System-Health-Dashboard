import { beforeEach, describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import axe from "axe-core";

import { ProcessPanel } from "../../src/presentation/components/ProcessPanel";
import { useDashboardStore } from "../../src/application/store";

describe("ProcessPanel accessibility", () => {
  beforeEach(() => {
    useDashboardStore.getState().reset();
    useDashboardStore.getState().ingestSnapshot({
      seq: 1,
      ts: 1,
      groups: {
        processes: {
          status: "ok",
          partial: false,
          value: {
            items: [
              {
                pid: 1,
                name: "init",
                cpu_percent: 0.1,
                memory_rss_bytes: 1024 ** 2,
              },
              {
                pid: 2,
                name: "worker",
                cpu_percent: null,
                memory_rss_bytes: 2 * 1024 ** 2,
              },
            ],
            skipped: 0,
            total: 2,
          },
        },
      },
    });
    useDashboardStore.getState().setConnectionState("open");
  });

  it.each(["light", "dark"] as const)(
    "has no serious or critical violations in the %s theme",
    async (theme) => {
      document.documentElement.dataset.theme = theme;
      const { container } = render(<ProcessPanel />);
      const results = await axe.run(container, {
        runOnly: { type: "tag", values: ["wcag2a", "wcag2aa"] },
      });
      delete document.documentElement.dataset.theme;
      const bad = results.violations.filter(
        (violation) =>
          violation.impact === "serious" || violation.impact === "critical",
      );
      if (bad.length) {
        console.log(
          JSON.stringify(
            bad.map((violation) => ({
              id: violation.id,
              impact: violation.impact,
              nodes: violation.nodes.length,
            })),
            null,
            2,
          ),
        );
      }
      expect(bad).toHaveLength(0);
    },
  );
});
