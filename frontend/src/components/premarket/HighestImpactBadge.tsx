// components/premarket/HighestImpactBadge.tsx
import React from "react";
import { Badge } from "react-bootstrap";

interface Props {
  keyword?: string;
  rank?: string;
}

const verdictColors: Record<string, string> = {
  "S+": "danger", "S": "success", "A+": "primary", "A": "warning",
  "A-": "info", "B": "secondary", "C": "dark", "D": "danger"
};

const HighestImpactBadge: React.FC<Props> = ({ keyword, rank }) => {
  if (!keyword || !rank) return null;
  const color = verdictColors[rank.toUpperCase()] ?? "light";

  return (
    <div className="d-flex justify-content-center mb-2">
      <Badge bg={color} className="border" style={{ fontSize: "0.75rem" }}>
        {keyword}: {rank}
      </Badge>
    </div>
  );
};

export default HighestImpactBadge;
