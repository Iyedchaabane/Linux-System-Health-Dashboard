import { Line, LineChart, ResponsiveContainer, YAxis } from "recharts";
import { formatBytes, formatPercent, formatRate } from "../../domain/format";

type Series = {
  label: string;
  data: (number | null)[];
  token: "1" | "2" | "3" | "4";
};

/** A bounded, compact history with a keyboard-accessible text alternative. */
export function Sparkline({
  title,
  series,
  unit,
}: {
  title: string;
  series: Series[];
  unit: "%" | "B" | "B/s";
}) {
  const bounded = series.map((s) => ({ ...s, data: s.data.slice(-60) }));
  const count = Math.max(0, ...bounded.map((s) => s.data.length));
  const points = Array.from({ length: count }, (_, i) =>
    Object.fromEntries(bounded.map((s, index) => [index, s.data[i] ?? null])),
  );
  const hasData = bounded.some((s) =>
    s.data.some((v) => v !== null && Number.isFinite(v)),
  );
  const format = unit === "%" ? formatPercent : unit === "B" ? formatBytes : formatRate;
  return (
    <div className="mt-3 border-t border-border-subtle pt-2">
      {hasData ? (
        <>
          <div
            className="metric-history min-w-0"
            role="img"
            aria-label={`${title}: recent ${count} samples, ${unit === "%" ? "0–100% scale" : unit === "B/s" ? "bytes per second" : "cumulative bytes"}. Missing readings appear as gaps.`}
          >
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={points}
                margin={{ top: 4, right: 4, bottom: 4, left: 4 }}
              >
                <YAxis hide domain={unit === "%" ? [0, 100] : [0, "auto"]} />
                {bounded.map((s, i) => (
                  <Line
                    key={s.label}
                    name={s.label}
                    dataKey={String(i)}
                    type="linear"
                    stroke={`rgb(var(--chart-${s.token}))`}
                    strokeWidth={2}
                    strokeDasharray={i === 0 ? undefined : "4 3"}
                    dot={({ cx, cy, index }) => (
                      <circle
                        key={index}
                        cx={cx}
                        cy={cy}
                        r={index === count - 1 ? 2 : 0}
                        fill={`rgb(var(--chart-${s.token}))`}
                      />
                    )}
                    isAnimationActive={false}
                    connectNulls={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
          <details className="text-xs text-muted">
            <summary className="flex cursor-pointer items-center rounded-sm">
              View {count} recent samples
            </summary>
            {/* Keyboard focus is required to scroll the bounded data table. */}
            <div
              className="max-h-48 overflow-auto"
              tabIndex={0} // eslint-disable-line jsx-a11y/no-noninteractive-tabindex -- Keyboard-scrollable region.
              role="region"
              aria-label={`${title} table`}
            >
              <table className="w-full text-right tabular-nums">
                <caption className="sr-only">
                  {title}; oldest to newest. Sample positions do not imply
                  elapsed time.
                </caption>
                <thead>
                  <tr>
                    <th scope="col" className="p-1 text-left">
                      Sample
                    </th>
                    {bounded.map((s) => (
                      <th scope="col" className="p-1" key={s.label}>
                        {s.label} ({unit})
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {points.map((point, i) => (
                    <tr key={i}>
                      <th scope="row" className="p-1 text-left font-normal">
                        {i + 1}
                      </th>
                      {bounded.map((s, index) => (
                        <td className="p-1" key={s.label}>
                          {point[index] === null
                            ? "Unavailable"
                            : format(point[index])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
          {series.length > 1 && (
            <p className="text-xs text-muted">
              Receive — solid · Transmit — dashed
            </p>
          )}
        </>
      ) : (
        <p className="py-4 text-xs text-muted">History unavailable</p>
      )}
    </div>
  );
}
