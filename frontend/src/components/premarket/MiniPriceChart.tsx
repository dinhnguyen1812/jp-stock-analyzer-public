import React, { useState } from "react";
import { Button, ButtonGroup } from "react-bootstrap";
import {
  ResponsiveContainer,
  ComposedChart,
  XAxis,
  YAxis,
  Tooltip,
  Bar,
  Line,
} from "recharts";

type PriceData = {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
};

export default function MiniPriceChart({ data }: { data: PriceData[] }) {
  const [days, setDays] = useState(30); // default to 30 days

  const chartData = data
    .slice(-days) // take only last `days` points
    .map((d) => ({
      ...d,
      up: d.close >= d.open,
    }));

  const lows = chartData.map((d) => d.low).filter((v) => v > 0);
  const highs = chartData.map((d) => d.high).filter((v) => v > 0);

  const ymin = lows.length > 0 ? Math.min(...lows) : 0;
  const ymaxRaw = highs.length > 0 ? Math.max(...highs) : 1;
  const ymax = Math.max(ymaxRaw, 1.3 * ymin); // ensure ymax ≥ 1.3 * ymin

  return (
    <div>
      <ButtonGroup className="mb-2">
        {[5, 10, 20, 30, 50].map((d) => (
          <Button
            key={d}
            size="sm"
            variant={days === d ? "primary" : "outline-primary"}
            onClick={() => setDays(d)}
          >
            {d}日
          </Button>
        ))}
      </ButtonGroup>

      <ResponsiveContainer width="100%" aspect={3 / 2} style={{ marginBottom: 0 }}>
        <ComposedChart data={chartData} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
          <XAxis dataKey="date" hide />
          <YAxis domain={[ymin, ymax]} hide />
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
              const { x, width, payload, yAxis } = props;
              if (!payload) return <g />;
              const yScale = yAxis?.scale;
              if (!yScale) {
                return (
                  <rect
                    x={x}
                    y={props.y}
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
              return <rect x={x} y={rectY} width={width} height={rectHeight || 1} fill={color} />;
            }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
