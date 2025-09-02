import React from "react";
import { Badge } from "react-bootstrap";

interface Props {
  keyword?: string;
  rank?: string;
  newsScore?: number;
}

const verdictColors: Record<string, string> = {
  "S+": "danger",
  "S": "success",
  "A+": "primary",
  "A": "warning",
  "A-": "info",
  "B": "secondary",
  "C": "dark",
  "D": "danger",
};

const getScoreColor = (score: number): string => {
  if (score >= 80) return "success";
  if (score >= 60) return "info";
  if (score >= 40) return "warning";
  return "danger";
};

const HighestImpactBadge: React.FC<Props> = ({ keyword, rank, newsScore }) => {
  if (!keyword || !rank) return null;
  const color = verdictColors[rank.toUpperCase()] ?? "light";

  return (
    <div className="d-flex flex-column align-items-center mb-2">
      <Badge
        bg={color}
        className="border text-wrap text-center mb-1"
        style={{
          fontSize: "0.75rem",
          maxWidth: "120px",
          whiteSpace: "normal",
          wordBreak: "break-word",
        }}
      >
        {keyword}: {rank}
      </Badge>

      {typeof newsScore === "number" && (
        <Badge
          bg={getScoreColor(newsScore)}
          className="border"
          style={{ fontSize: "0.75rem" }}
        >
          {newsScore}
        </Badge>
      )}
    </div>
  );
};

export default HighestImpactBadge;
