"use client";

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
import type { BankrollPoint } from "@/lib/types";

interface BankrollChartProps {
  points: BankrollPoint[];
  initial: number;
}

function formatTick(value: string) {
  if (!value || value === "Départ") return "départ";
  return value.slice(5);
}

export default function BankrollChart({ points, initial }: BankrollChartProps) {
  return (
    <div className="h-[320px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 12, right: 16, bottom: 4, left: -12 }}>
          <CartesianGrid stroke="#1f2837" strokeDasharray="3 6" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fill: "#64748b", fontSize: 10, fontFamily: "ui-monospace" }}
            tickLine={false}
            axisLine={{ stroke: "#1f2837" }}
            minTickGap={64}
            tickFormatter={formatTick}
          />
          <YAxis
            domain={["auto", "auto"]}
            tick={{ fill: "#64748b", fontSize: 10, fontFamily: "ui-monospace" }}
            tickLine={false}
            axisLine={false}
            width={56}
            tickFormatter={(value: number) => `${value.toFixed(0)}`}
          />
          <ReferenceLine
            y={initial}
            stroke="#475569"
            strokeDasharray="4 6"
            label={{
              value: `départ ${initial.toFixed(0)} u`,
              fill: "#64748b",
              fontSize: 10,
              position: "insideBottomRight",
            }}
          />
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
              typeof value === "number" ? `${value.toFixed(2)} u` : value,
              name === "flat" ? "Flat 1 u" : "Quarter-Kelly",
            ]}
          />
          <Line
            type="monotone"
            dataKey="flat"
            name="flat"
            stroke="#4cc9f0"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
          <Line
            type="monotone"
            dataKey="kelly"
            name="kelly"
            stroke="#f5b942"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
