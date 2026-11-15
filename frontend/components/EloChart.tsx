"use client";

import { useMemo } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { EloPoint } from "@/lib/types";

interface EloChartProps {
  home: { team: string; points: EloPoint[] };
  away: { team: string; points: EloPoint[] };
}

/** Fusionne deux séries Elo (dates disjointes) avec report de la dernière valeur. */
function mergeSeries(home: EloPoint[], away: EloPoint[]) {
  const homeMap = new Map(home.map((point) => [point.date, point.elo]));
  const awayMap = new Map(away.map((point) => [point.date, point.elo]));
  const dates = Array.from(new Set([...homeMap.keys(), ...awayMap.keys()])).sort();

  let lastHome: number | null = null;
  let lastAway: number | null = null;

  return dates.map((date) => {
    if (homeMap.has(date)) lastHome = homeMap.get(date) ?? lastHome;
    if (awayMap.has(date)) lastAway = awayMap.get(date) ?? lastAway;
    return { date, home: lastHome, away: lastAway };
  });
}

export default function EloChart({ home, away }: EloChartProps) {
  const data = useMemo(() => mergeSeries(home.points, away.points), [home.points, away.points]);
  const baseline = 1500;

  return (
    <div className="h-[280px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 10, right: 12, bottom: 0, left: -18 }}>
          <CartesianGrid stroke="#1f2837" strokeDasharray="3 6" vertical={false} />
          <XAxis
            dataKey="date"
            tick={{ fill: "#64748b", fontSize: 10, fontFamily: "ui-monospace" }}
            tickLine={false}
            axisLine={{ stroke: "#1f2837" }}
            minTickGap={48}
            tickFormatter={(value: string) => value.slice(5)}
          />
          <YAxis
            domain={["dataMin - 25", "dataMax + 25"]}
            tick={{ fill: "#64748b", fontSize: 10, fontFamily: "ui-monospace" }}
            tickLine={false}
            axisLine={false}
            width={52}
          />
          <ReferenceLine y={baseline} stroke="#334155" strokeDasharray="4 6" />
          <Tooltip
            contentStyle={{
              background: "#0b0f16",
              border: "1px solid #1f2837",
              borderRadius: 10,
              fontSize: 12,
              color: "#e2e8f0",
            }}
            labelStyle={{ color: "#94a3b8", fontFamily: "ui-monospace", fontSize: 11 }}
            formatter={(value: number | string, name: string) => [
              typeof value === "number" ? value.toFixed(1) : value,
              name,
            ]}
          />
          <Line
            type="monotone"
            dataKey="home"
            name={home.team}
            stroke="#00e08a"
            strokeWidth={2}
            dot={false}
            connectNulls
            isAnimationActive={false}
          />
          <Line
            type="monotone"
            dataKey="away"
            name={away.team}
            stroke="#4cc9f0"
            strokeWidth={2}
            dot={false}
            connectNulls
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
