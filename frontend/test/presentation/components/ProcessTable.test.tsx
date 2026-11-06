import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";

import { ProcessTable } from "../../../src/presentation/components/ProcessTable";
import type { ProcessRow } from "../../../src/domain/types";

describe("ProcessTable", () => {
  it("renders a 16px icon before each process name", () => {
    const items: ProcessRow[] = [
      { pid: 1, name: "python", cpu_percent: 1.5, memory_rss_bytes: 1024 },
      { pid: 2, name: "unknown-service", cpu_percent: null, memory_rss_bytes: 0 },
    ];
    render(<ProcessTable items={items} />);
    const table = screen.getByRole("table");
    const rowHeaders = within(table).getAllByRole("rowheader");
    expect(rowHeaders.map((cell) => cell.textContent)).toEqual([
      "python",
      "unknown-service",
    ]);
    const icons = table.querySelectorAll("img, svg");
    expect(icons.length).toBe(items.length);
    icons.forEach((icon) => {
      expect(icon).toHaveAttribute("aria-hidden", "true");
    });
  });
});