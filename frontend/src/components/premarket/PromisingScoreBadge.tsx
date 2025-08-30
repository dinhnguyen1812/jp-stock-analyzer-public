// components/premarket/PromisingScoreBadge.tsx
import React from "react";
import { Badge } from "react-bootstrap";

interface Props {
  score?: number;
}

const PromisingScoreBadge: React.FC<Props> = ({ score }) => {
  if (score === undefined) return null;

  const getScoreColor = (score: number): string => {
    if (score >= 80) return "success";
    if (score >= 60) return "info";
    if (score >= 40) return "warning";
    return "danger";
  };

  return (
    <div className="d-flex justify-content-center">
      <Badge
        bg={getScoreColor(score)}
        className="border"
        style={{ fontSize: "0.75rem" }}
      >
        Score: {score}
      </Badge>
    </div>
  );
};

export default PromisingScoreBadge;
