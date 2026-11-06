import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";

import firefoxIcon from "../../../src/assets/process-icons/firefox.svg?no-inline";
import gitIcon from "../../../src/assets/process-icons/git.svg?no-inline";
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

  it("renders a brand image for Git and a neutral icon for unknown processes", () => {
    const items: ProcessRow[] = [
      { pid: 1, name: "git", cpu_percent: 1.5, memory_rss_bytes: 1024 },
      { pid: 2, name: "unknown-service", cpu_percent: 0, memory_rss_bytes: 0 },
    ];
    render(<ProcessTable items={items} />);
    const rowHeaders = within(screen.getByRole("table")).getAllByRole("rowheader");

    const gitImage = rowHeaders[0].querySelector("img");
    expect(gitImage).not.toBeNull();
    expect(gitImage).toHaveAttribute("src", gitIcon);
    expect(rowHeaders[0].textContent).toBe("git");

    expect(rowHeaders[1].querySelector("img")).toBeNull();
    expect(rowHeaders[1].querySelector("svg")).not.toBeNull();
  });

  it("renders a Firefox brand image alongside formatted metrics and unknown rows", () => {
    const items: ProcessRow[] = [
      { pid: 4242, name: "firefox", cpu_percent: 2.5, memory_rss_bytes: 2048 },
      { pid: 77, name: "unknown-daemon", cpu_percent: 0, memory_rss_bytes: 0 },
    ];
    render(<ProcessTable items={items} />);
    const table = screen.getByRole("table");
    const rowHeaders = within(table).getAllByRole("rowheader");
    expect(rowHeaders).toHaveLength(2);

    const firefoxImage = rowHeaders[0].querySelector("img");
    expect(firefoxImage).not.toBeNull();
    expect(firefoxImage).toHaveAttribute("src", firefoxIcon);
    expect(rowHeaders[0].textContent).toBe("firefox");
    expect(table.querySelectorAll("img")).toHaveLength(1);

    expect(screen.getByText("2.5%")).toBeInTheDocument();
    expect(screen.getByText("2.00 KiB")).toBeInTheDocument();
    expect(screen.getByText("4242")).toBeInTheDocument();

    expect(rowHeaders[1].querySelector("img")).toBeNull();
    expect(rowHeaders[1].querySelector("svg")).not.toBeNull();
  });

  it("keeps the formatted CPU, memory and PID text", () => {
    const items: ProcessRow[] = [
      { pid: 1234, name: "git", cpu_percent: 1.5, memory_rss_bytes: 1024 },
    ];
    render(<ProcessTable items={items} />);
    expect(screen.getByText("1.5%")).toBeInTheDocument();
    expect(screen.getByText("1.00 KiB")).toBeInTheDocument();
    expect(screen.getByText("1234")).toBeInTheDocument();
  });

  it("renders every row in the server-provided order", () => {
    const items: ProcessRow[] = [
      { pid: 30, name: "gamma", cpu_percent: 0, memory_rss_bytes: 0 },
      { pid: 10, name: "alpha", cpu_percent: 0, memory_rss_bytes: 0 },
      { pid: 20, name: "beta", cpu_percent: 0, memory_rss_bytes: 0 },
    ];
    render(<ProcessTable items={items} />);
    const rowHeaders = within(screen.getByRole("table")).getAllByRole("rowheader");
    expect(rowHeaders).toHaveLength(items.length);
    expect(rowHeaders.map((cell) => cell.textContent)).toEqual([
      "gamma",
      "alpha",
      "beta",
    ]);
  });

  it("preserves the full long name in text and title while truncating visually", () => {
    const longName = `${"very-long-process-name-".repeat(8)}end`;
    const items: ProcessRow[] = [
      { pid: 99, name: longName, cpu_percent: 0, memory_rss_bytes: 0 },
    ];
    render(<ProcessTable items={items} />);
    const rowHeader = within(screen.getByRole("table")).getByRole("rowheader");
    expect(rowHeader).toHaveAttribute("title", longName);
    expect(rowHeader.textContent).toBe(longName);
    const truncating = rowHeader.querySelector("span.truncate");
    expect(truncating).not.toBeNull();
    expect(truncating?.textContent).toBe(longName);
  });
});
