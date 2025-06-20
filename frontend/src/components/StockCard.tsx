import React from "react";
import { Card } from "react-bootstrap";

interface StockData {
  ticker: string;
  name: string;
  market: string;
  price: number;
  per: number;
  pbr: number;
  roe: number;
  eps: number;
  market_cap: number;
}

interface Props {
  stock: StockData;
}

export const StockCard: React.FC<Props> = ({ stock }) => {
  return (
    <Card>
      <Card.Body>
        <Card.Title>{stock.name} ({stock.ticker})</Card.Title>
        <Card.Subtitle className="mb-2 text-muted">{stock.market}</Card.Subtitle>
        <ul>
          <li><strong>Price:</strong> ¥{stock.price}</li>
          <li><strong>PER:</strong> {stock.per}</li>
          <li><strong>PBR:</strong> {stock.pbr}</li>
          <li><strong>ROE:</strong> {stock.roe}%</li>
          <li><strong>EPS:</strong> {stock.eps}</li>
          <li><strong>Market Cap:</strong> ¥{(stock.market_cap / 1e9).toFixed(2)}B</li>
        </ul>
      </Card.Body>
    </Card>
  );
};
