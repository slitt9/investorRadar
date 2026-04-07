"use client";

import { Line, LineChart, ResponsiveContainer, Tooltip } from "recharts";
import type { SeriesPoint } from "../types";

export function StockSparkline({
  data,
  color,
}: {
  data: SeriesPoint[];
  color: string;
}) {
  const chartData = data.map((d) => ({ t: d.t, v: d.v }));

  return (
    <div className="h-10 w-[140px]">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData}>
          <Tooltip contentStyle={{ display: "none" }} />
          <Line
            type="monotone"
            dataKey="v"
            stroke={color}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

