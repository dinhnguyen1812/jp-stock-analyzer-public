import React, { useState } from "react";
import { Form, Button, Row, Col } from "react-bootstrap";

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
    <Form onSubmit={handleSubmit} className="mb-4">
      <Row className="align-items-end">
        <Col xs={8}>
          <Form.Label>Enter Stock Ticker (e.g., 5255)</Form.Label>
          <Form.Control
            type="text"
            placeholder="Enter ticker"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
          />
        </Col>
        <Col xs={4}>
          <Button type="submit" className="w-100">Search</Button>
        </Col>
      </Row>
    </Form>
  );
};
