import { Card } from "react-bootstrap";

interface IndustryCardProps {
  industry: any;
  height?: string | number;  // e.g. "300px" or 300
}

export const IndustryCard: React.FC<IndustryCardProps> = ({ industry, height }) => (
  <Card 
    className="mb-3" 
    style={height ? { height, overflowY: "auto" } : undefined}
  >
    <Card.Header>🏭 Industry Averages</Card.Header>
    <Card.Body>
      {industry ? (
        <ul>
          <li>Industry: {industry.industry}</li>
          <li>PER: {industry.per}</li>
          <li>PBR: {industry.pbr}</li>
          {/* <li>ROE: {industry.roe}</li> */}
        </ul>
      ) : (
        <p>No industry data found</p>
      )}
    </Card.Body>
  </Card>
);
