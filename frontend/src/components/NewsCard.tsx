import { Card, ListGroup } from "react-bootstrap";

export const NewsCard = ({ news }: any) => (
  <Card className="mb-3">
    <Card.Header>📰 Relevant News</Card.Header>
    <ListGroup variant="flush">
      {news.map((item: any, idx: number) => (
        <ListGroup.Item key={idx}>
          <a href={item.url} target="_blank" rel="noreferrer">{item.headline}</a><br />
          <small className="text-muted">{item.published_at}</small>
        </ListGroup.Item>
      ))}
    </ListGroup>
  </Card>
);
