import { Card } from "react-bootstrap";

export const IndustryCard = ({ industry }: any) => (
  <Card className="mb-3">
    <Card.Header>🏭 Industry Averages</Card.Header>
    <Card.Body>
      {industry ? (
        <ul>
          <li>Industry: {industry.industry}</li>
          <li>PER: {industry.per}</li>
          <li>PBR: {industry.pbr}</li>
          <li>ROE: {industry.roe}</li>
        </ul>
      ) : (
        <p>No industry data found</p>
      )}
    </Card.Body>
  </Card>
);
