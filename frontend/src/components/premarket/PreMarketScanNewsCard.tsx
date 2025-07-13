import React, { useState } from "react";
import { Card, Row, Col, Form, Button, Spinner, InputGroup } from "react-bootstrap";
import { scanNewsBulk } from "../../api"; // Make sure your path is correct

const PreMarketScanNewsCard: React.FC = () => {
  const [fromPage, setFromPage] = useState(1);
  const [toPage, setToPage] = useState(5);
  const [priceThreshold, setPriceThreshold] = useState(300);
  const [loading, setLoading] = useState(false);
  const [alertTickers, setAlertTickers] = useState<string[]>([]);

  const handleScanNews = async () => {
    setLoading(true);
    setAlertTickers([]);
    try {
      const result = await scanNewsBulk(); // optional: pass params here
      setAlertTickers(result.alert_tickers || []);
    } catch (err) {
      alert("Scan failed: " + err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="mb-3 px-3 py-3 shadow-sm">
      <Card.Title>📰 Kabutan News Scanner</Card.Title>
      <Row className="g-3 align-items-center">
        <Col xs={12} md={3}>
          <InputGroup>
            <InputGroup.Text>From</InputGroup.Text>
            <Form.Control
              type="number"
              value={fromPage}
              min={1}
              onChange={(e) => setFromPage(Number(e.target.value))}
              disabled={loading}
            />
          </InputGroup>
        </Col>
        <Col xs={12} md={3}>
          <InputGroup>
            <InputGroup.Text>To</InputGroup.Text>
            <Form.Control
              type="number"
              value={toPage}
              min={fromPage}
              onChange={(e) => setToPage(Number(e.target.value))}
              disabled={loading}
            />
          </InputGroup>
        </Col>
        <Col xs={12} md={3}>
          <InputGroup>
            <InputGroup.Text>Price ≤</InputGroup.Text>
            <Form.Control
              type="number"
              value={priceThreshold}
              onChange={(e) => setPriceThreshold(Number(e.target.value))}
              disabled={loading}
            />
            <InputGroup.Text>¥</InputGroup.Text>
          </InputGroup>
        </Col>
        <Col xs={12} md={3}>
          <Button
            className="w-100"
            variant="danger"
            onClick={handleScanNews}
            disabled={loading}
          >
            {loading ? <Spinner animation="border" size="sm" /> : "Scan News"}
          </Button>
        </Col>
      </Row>

      {alertTickers.length > 0 && (
        <div className="mt-3">
          <h6>⚠️ Positive News Detected for:</h6>
          <div style={{ fontSize: "0.9rem" }}>
            {alertTickers.map((ticker) => (
              <span key={ticker} className="badge bg-success me-2">
                {ticker}
              </span>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
};

export default PreMarketScanNewsCard;
