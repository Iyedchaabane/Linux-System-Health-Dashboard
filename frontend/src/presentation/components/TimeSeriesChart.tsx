import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export type TimeSeriesChartProps = {
  title: string;
  data: (number | null)[];
  unit?: string;
  domain?: [number | "auto", number | "auto"];
};

const MAX_RENDERED_POINTS = 60;

export function TimeSeriesChart({
  title,
  data,
  unit = "",
  domain,
}: TimeSeriesChartProps) {
  const bounded = (data ?? []).slice(-MAX_RENDERED_POINTS);
  const chartData = bounded.map((v, i) => ({ i, v }));
  const finiteValues = bounded.filter((v): v is number => typeof v === "number" && Number.isFinite(v));
  const isEmpty = finiteValues.length === 0;
  let latest: number | null = null;
  for (let i = bounded.length - 1; i >= 0; i -= 1) {
    const v = bounded[i];
    if (typeof v === "number" && Number.isFinite(v)) {
      latest = v;
      break;
    }
  }

  const isPercent = unit === "%";
  const isUsage = title.toLowerCase().includes("usage");
  const resolvedDomain: [number | "auto", number | "auto"] =
    domain ?? (isUsage || isPercent ? [0, 100] : [0, "auto"]);

  return (
    <div
      className="rounded-card border border-border-subtle bg-surface p-4"
      role="img"
      aria-label={`${title} chart`}
      data-domain={resolvedDomain.join(",")}
    >
      <h2 className="text-base font-medium text-text">{title}</h2>
      <div className="text-xs text-muted" aria-live="polite">
        {isEmpty ? "Waiting for data…" : `Latest ${latest}${unit}`}
      </div>
      <div className="mt-4 h-40 w-full">
        {isEmpty ? (
          <div className="h-full" />
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <XAxis hide dataKey="i" />
              <YAxis domain={resolvedDomain} hide />
              <Tooltip
                formatter={(value: unknown) => [`${value === null || value === undefined ? "--" : (value as number)}${unit}`, title]}
                labelFormatter={(label: number) => `sample ${label + 1}`}
                contentStyle={{ backgroundColor: "rgb(var(--color-surface))", color: "rgb(var(--color-text))", borderColor: "rgb(var(--color-border-subtle))" }}
              />
              <Line
                type="monotone"
                dataKey="v"
                stroke="rgb(var(--chart-1))"
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
                connectNulls={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
      <div className="sr-only">
        Chart showing {title} over time. {isEmpty ? "No data yet." : `Latest value ${latest}.`}
      </div>
    </div>
  );
}
