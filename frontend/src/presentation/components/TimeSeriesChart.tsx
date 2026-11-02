import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export type SeriesPoint = { x: number; y: number };

export type TimeSeriesChartProps = {
  title: string;
  data: number[];
  unit?: string;
  colorClass?: string;
};

export function TimeSeriesChart({ title, data, unit = "" }: TimeSeriesChartProps) {
  const chartData = data.map((v, i) => ({ i, v }));

  return (
    <div className="rounded-card border border-border-subtle bg-surface p-4">
      <h2 className="text-base font-medium text-text">{title}</h2>
      <div className="text-xs text-muted" aria-live="polite">
        {data.length === 0 ? "Waiting for data…" : `Latest ${data[data.length - 1]} ${unit ?? ""}`}
      </div>
      <div className="mt-4 h-40 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <XAxis hide dataKey="i" />
            <YAxis domain={title === "CPU usage" ? [0, 100] : [0, 100]} hide />
            <Tooltip
              formatter={(value: number) => [`${value}${unit}`, title]}
              labelFormatter={(label: number) => `sample ${label + 1}`}
              contentStyle={{ backgroundColor: "rgb(var(--color-surface))", color: "rgb(var(--color-text))", borderColor: "rgb(var(--color-border-subtle))" }}
            />
            <Line
              type="monotone"
              dataKey="v"
              stroke="rgb(var(--color-primary))"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="sr-only">
        Chart showing {title} over time. {data.length === 0 ? "No data yet." : `Latest value ${data[data.length - 1]}.`}
      </div>
    </div>
  );
}
