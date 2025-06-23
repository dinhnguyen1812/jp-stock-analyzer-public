import { Card, ListGroup } from "react-bootstrap";

interface NewsCardProps {
  news: any[];
  height?: string | number;  // e.g. "400px" or 400
}

export const NewsCard: React.FC<NewsCardProps> = ({ news, height }) => (
  <Card className="mb-3" style={height ? { height, overflowY: "auto" } : undefined}>
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
