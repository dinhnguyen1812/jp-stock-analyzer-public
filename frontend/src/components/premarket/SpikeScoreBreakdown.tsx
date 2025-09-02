// components/premarket/SpikeScoreBreakdown.tsx
import React from "react";
import { Badge } from "react-bootstrap";
import type { SpikeInfo } from "./types";

interface Props {
  spikeInfo?: SpikeInfo;
}

const SpikeScoreBreakdown: React.FC<Props> = ({ spikeInfo }) => {
  if (!spikeInfo) return null;

  const getScoreColor = (score: number): string => {
    if (score >= 80) return "success";
    if (score >= 60) return "info";
    if (score >= 40) return "warning";
    return "danger";
  };

  const breakdown: { label: string; points: number; maxPoints: number; value?: any }[] = [
    { label: "Days since spike", value: spikeInfo.days_since_spike, points: spikeInfo.days_since_spike <= 2 ? 35 : spikeInfo.days_since_spike <= 5 ? 25 : spikeInfo.days_since_spike <= 10 ? 15 : spikeInfo.days_since_spike <= 15 ? 5 : 0, maxPoints: 35 },
    { label: "First Close↑High", value: spikeInfo.first_day_close_near_high ? "Yes" : "No", points: spikeInfo.first_day_close_near_high ? 10 : 0, maxPoints: 10 },
    { label: "First spike pct", value: spikeInfo.first_spike_pct + "%", points: spikeInfo.first_spike_pct >= 100 ? 20 : spikeInfo.first_spike_pct >= 40 ? 10 : 5, maxPoints: 20 },
    { label: "Respikes", value: spikeInfo.number_of_respikes, points: (spikeInfo.number_of_respikes ?? 0) > 3 ? 0 : Math.min(spikeInfo.number_of_respikes ?? 0, 1) * 5, maxPoints: 5 },
    { label: "Current Drop↓High", value: spikeInfo.drop_from_high_pct + "%", points: spikeInfo.drop_from_high_pct >= 40 ? 25 : spikeInfo.drop_from_high_pct >= 20 ? 18 : spikeInfo.drop_from_high_pct >= 10 ? 10 : 5, maxPoints: 25 },
    { label: "Current Close↓Low", value: spikeInfo.last_day_close_near_low ? "Yes" : "No", points: spikeInfo.last_day_close_near_low ? 15 : 0, maxPoints: 15 }
  ];

  return (
    <div className="d-flex flex-column gap-1">
      <div style={{ fontSize: "0.75rem", display: "flex", gap: "0.5rem", alignItems: "center" }}>
        Spike Day: 
        <span style={{ fontWeight: spikeInfo.spike_date ? "bold" : "normal", color: spikeInfo.spike_date ? "green" : "gray" }}>
          {spikeInfo.spike_date || "-"}
        </span>
        {spikeInfo.score != null && (
          <Badge bg={getScoreColor(spikeInfo.score)} className="border" style={{ fontSize: "0.75rem" }}>
            {spikeInfo.score}
          </Badge>
        )}
      </div>
      {breakdown.map((item, idx) => {
        const highlight = item.value !== null && item.value !== undefined && item.value !== "No" && item.value !== 0;
        return (
          <div key={idx} style={{ fontSize: "0.75rem", display: "flex", gap: "0.25rem", alignItems: "center" }}>
            <span>{item.label}:</span>
            <span style={{ fontWeight: highlight ? "bold" : "normal", color: highlight ? "green" : "black" }}>{item.value}</span>
            <span style={{ color: "red" }}> +{item.points}/{item.maxPoints}</span>
          </div>
        );
      })}
    </div>
  );
};

export default SpikeScoreBreakdown;
