import { Card, Table } from "react-bootstrap";

export const IndicatorsCard = ({ indicators }: any) => (
  <Card className="mb-3">
    <Card.Header>📊 Realtime Indicators</Card.Header>
    <Card.Body>
      <Table striped bordered size="sm">
        <tbody>
          <tr><td>Ticker</td><td>{indicators.ticker}</td></tr>
          <tr><td>Name</td><td>{indicators.name}</td></tr>
          <tr><td>Price</td><td>¥{indicators.price}</td></tr>
          <tr><td>PER</td><td>{indicators.per}</td></tr>
          <tr><td>PBR</td><td>{indicators.pbr}</td></tr>
          <tr><td>EPS</td><td>{indicators.eps}</td></tr>
          <tr><td>ROE</td><td>{indicators.roe}</td></tr>
          <tr><td>Dividend Yield</td><td>{indicators.dividend_yield}%</td></tr>
          <tr><td>Debt Ratio</td><td>{indicators.debt_ratio}%</td></tr>
        </tbody>
      </Table>
    </Card.Body>
  </Card>
);
