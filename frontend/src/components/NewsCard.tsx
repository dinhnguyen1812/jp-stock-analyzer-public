import React from "react";
import { Card, ListGroup } from "react-bootstrap";

export interface NewsItem {
  headline: string;
  url: string;
  published_at: string;
}

interface Props {
  news: NewsItem[];
}

export const NewsCard: React.FC<Props> = ({ news }) => {
  if (!news || news.length === 0) return null;

  return (
    <Card className="mt-4">
      <Card.Body>
        <Card.Title>Recent News</Card.Title>
        <ListGroup variant="flush">
          {news.map((item, idx) => (
            <ListGroup.Item key={idx}>
              <a href={item.url} target="_blank" rel="noopener noreferrer">
                {item.headline}
              </a>
              <div className="text-muted small">
                {new Date(item.published_at).toLocaleString()}
              </div>
            </ListGroup.Item>
          ))}
        </ListGroup>
      </Card.Body>
    </Card>
  );
};

