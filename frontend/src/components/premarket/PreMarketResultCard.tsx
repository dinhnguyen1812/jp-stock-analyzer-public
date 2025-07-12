import React from "react";
import { Card, ListGroup, Badge } from "react-bootstrap";
import type { PreMarketScanResult } from "../../types";

interface Props {
  result: PreMarketScanResult;
}

const verdictVariant = (verdict: string): string => {
  switch (verdict) {
    case "Decisive":
      return "success";
    case "Great":
      return "primary";
    case "Good":
      return "info";
    case "Neutral":
    default:
      return "secondary";
  }
};

const PreMarketResultCard: React.FC<Props> = ({ result }) => {
  return (
    <Card className="mt-4 p-3 shadow-sm bg-light">
      <Card.Title>📰 GPT-Evaluated Headlines</Card.Title>
      <ListGroup variant="flush">
        {result.news.map((item, index) => (
          <ListGroup.Item key={index} className="d-flex justify-content-between align-items-start">
            <div>
              <a href={item.url} target="_blank" rel="noopener noreferrer">
                {item.headline}
              </a>
              <br />
              <small className="text-muted">[{item.category}] {new Date(item.published_at).toLocaleString()}</small>
              <div className="mt-1">
                <Badge bg={verdictVariant(item.verdict)} className="me-2">
                  {item.verdict}
                </Badge>
                <span style={{ fontStyle: "italic", fontSize: "0.85rem" }}>{item.reason}</span>
              </div>
            </div>
          </ListGroup.Item>
        ))}
      </ListGroup>
    </Card>
  );
};

export default PreMarketResultCard;
