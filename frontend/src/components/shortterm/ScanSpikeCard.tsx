import React from "react";
import { Card } from "react-bootstrap";

interface Props {
  report: string;
}

const ScanSpikeCard: React.FC<Props> = ({ report }) => {
  if (!report) return null;

  return (
    <Card className="mt-3 p-3 shadow-sm bg-light">
      <Card.Title>📈 Spike Scan Summary</Card.Title>
      <Card.Body style={{ whiteSpace: "pre-wrap", fontFamily: "monospace", fontSize: "0.9rem" }}>
        {report}
      </Card.Body>
    </Card>
  );
};

export default ScanSpikeCard;