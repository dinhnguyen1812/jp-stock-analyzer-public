import React from "react";
import {
  ResponsiveContainer,
  ComposedChart,
  XAxis,
  YAxis,
  Tooltip,
  Bar,
  Line,
} from "recharts";
import type { BarProps } from "recharts";

type PriceData = {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
};

export default function MiniPriceChart({ data }: { data: PriceData[] }) {
  const chartData = data.map((d) => ({
    ...d,
    up: d.close >= d.open,
  }));

  return (
    <ResponsiveContainer width="100%" aspect={3 / 2}>
      <ComposedChart data={chartData}>
        <XAxis dataKey="date" hide />
        <YAxis domain={["dataMin", "dataMax"]} hide />
        <Tooltip
          contentStyle={{ fontSize: "0.75rem" }}
          formatter={(value, name) =>
            [value, typeof name === "string" ? name.toUpperCase() : name]
          }
        />
        <Line
          type="linear"
          dataKey="high"
          stroke="#000"
          dot={false}
          strokeWidth={1}
          connectNulls={false}
          isAnimationActive={false}
        />
        <Line
          type="linear"
          dataKey="low"
          stroke="#000"
          dot={false}
          strokeWidth={1}
          connectNulls={false}
          isAnimationActive={false}
        />
        <Bar
          dataKey="close"
          barSize={6}
          shape={(props: any) => {
            // use any here to access payload safely
            const { x, width, payload, y, yAxis } = props;

            if (!payload) return <g />;

            const yScale = yAxis?.scale;

            if (!yScale) {
              return (
                <rect
                  x={x}
                  y={y}
                  width={width}
                  height={5}
                  fill={payload.close >= payload.open ? "#28a745" : "#dc3545"}
                />
              );
            }

            const yOpen = yScale(payload.open);
            const yClose = yScale(payload.close);
            const rectY = Math.min(yOpen, yClose);
            const rectHeight = Math.abs(yClose - yOpen);
            const color = payload.close >= payload.open ? "#28a745" : "#dc3545";

            return (
              <rect
                x={x}
                y={rectY}
                width={width}
                height={rectHeight || 1}
                fill={color}
              />
            );
          }}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
