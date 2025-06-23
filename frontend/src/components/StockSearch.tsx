import React, { useState } from "react";
import { Form, Button, Row, Col, Card } from "react-bootstrap";

interface StockSearchProps {
  onSearch: (ticker: string) => void;
}

export const StockSearch: React.FC<StockSearchProps> = ({ onSearch }) => {
  const [ticker, setTicker] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (ticker.trim() !== "") {
      onSearch(ticker.trim());
    }
  };

  return (
    <Card className="mb-4 text-center">
      <Card.Body>
        {/* <Card.Title>📊 JP Stock Search</Card.Title> */}
        <Form onSubmit={handleSubmit}>
          <Row className="justify-content-center align-items-end">
            <Col xs={12} className="mb-2">
              <Form.Label><strong>Enter Stock Ticker (e.g., 7203)</strong></Form.Label>
            </Col>
            <Col xs={6} md={4} className="mb-2">
              <Form.Control
                type="text"
                placeholder="Enter ticker"
                value={ticker}
                onChange={(e) => setTicker(e.target.value)}
              />
            </Col>
            <Col xs={6} md={2} className="mb-2">
              <Button type="submit" className="w-200">Search</Button>
            </Col>
          </Row>
        </Form>
      </Card.Body>
    </Card>
  );
};
