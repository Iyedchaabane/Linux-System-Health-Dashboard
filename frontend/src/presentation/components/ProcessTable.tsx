import { formatBytes, formatPercent } from "../../domain/format";
import type { ProcessRow } from "../../domain/types";
import { ProcessIcon } from "../processIcons";

/**
 * Compact process table. Renders every row the payload contains, exactly in
 * the server-supplied order — the client never truncates. The payload length
 * itself is bounded by the server's configured top-N (default 25, up to 100).
 */
export function ProcessTable({ items }: { items: ProcessRow[] }) {
  return (
    <div
      className="max-h-80 overflow-auto rounded-sm"
      role="region"
      aria-label="Running processes table"
      tabIndex={0} // eslint-disable-line jsx-a11y/no-noninteractive-tabindex -- Keyboard-scrollable region.
    >
      <table className="w-full table-fixed border-collapse text-left text-xs">
        <caption className="sr-only">
          Running processes from the latest snapshot, in the order reported by
          the server: name, CPU, memory (RSS), and PID.
        </caption>
        <colgroup>
          <col className="w-1/3" />
          <col className="w-1/5" />
          <col className="w-1/4" />
          <col className="w-1/5" />
        </colgroup>
        <thead className="sticky top-0 bg-surface">
          <tr className="border-b border-border-subtle text-muted">
            <th scope="col" className="py-1 pr-2 text-left font-medium">
              Name
            </th>
            <th scope="col" className="py-1 pr-2 text-right font-medium">
              CPU
            </th>
            <th scope="col" className="py-1 pr-2 text-right font-medium">
              Memory (RSS)
            </th>
            <th scope="col" className="py-1 text-right font-medium">
              PID
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((row) => (
            <tr key={row.pid} className="border-b border-border-subtle">
              <th
                scope="row"
                className="py-1 pr-2 text-left font-mono font-normal text-text"
                title={row.name === "" ? "Unnamed process" : row.name}
              >
                <span className="inline-flex max-w-full min-w-0 items-center gap-2">
                  <ProcessIcon
                    name={row.name === "" ? "Unnamed process" : row.name}
                    className="h-4 w-4 shrink-0"
                  />
                  <span className="min-w-0 truncate">
                    {row.name === "" ? "Unnamed process" : row.name}
                  </span>
                </span>
              </th>
              <td className="whitespace-nowrap py-1 pr-2 text-right tabular-nums text-text">
                {row.cpu_percent === null
                  ? "Measuring"
                  : formatPercent(row.cpu_percent)}
              </td>
              <td className="whitespace-nowrap py-1 pr-2 text-right tabular-nums text-text">
                {formatBytes(row.memory_rss_bytes)}
              </td>
              <td className="whitespace-nowrap py-1 text-right tabular-nums text-text">
                {row.pid}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
