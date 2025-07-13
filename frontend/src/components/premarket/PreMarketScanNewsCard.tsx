import React, { useState } from "react";
import { Card, Row, Col, Form, Button, Spinner, InputGroup } from "react-bootstrap";
import { scanNewsBulk, getPositiveNewsTickers } from "../../api";

interface PositiveNewsItem {
  ticker: string;
  headline: string;
  verdict: string;
  reason: string;
  created_at: string;
}

const PreMarketScanNewsCard: React.FC = () => {
  const [fromPage, setFromPage] = useState(1);
  const [toPage, setToPage] = useState(5);
  const [priceThreshold, setPriceThreshold] = useState(300);
  const [loadingScan, setLoadingScan] = useState(false);
  const [loadingPositive, setLoadingPositive] = useState(false);
  const [alertTickers, setAlertTickers] = useState<PositiveNewsItem[]>([]);

  const handleScanNews = async () => {
    setLoadingScan(true);
    setAlertTickers([]);
    try {
      // Assuming your scanNewsBulk accepts parameters now, else adjust accordingly
      const result = await scanNewsBulk(fromPage, toPage, priceThreshold);
      // The backend returns alert_tickers as array of strings (tickers),
      // so just map to simple PositiveNewsItem with ticker only for display here or clear alertTickers
      setAlertTickers(result.alert_tickers.map((ticker: string) => ({ ticker } as PositiveNewsItem)) || []);
    } catch (err) {
      alert("Scan failed: " + err);
    } finally {
      setLoadingScan(false);
    }
  };

  const handleFetchPositiveNews = async () => {
    setLoadingPositive(true);
    try {
      const result = await getPositiveNewsTickers();
      setAlertTickers(result);
    } catch (err) {
      alert("Failed to fetch positive news tickers: " + err);
    } finally {
      setLoadingPositive(false);
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
              disabled={loadingScan || loadingPositive}
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
              disabled={loadingScan || loadingPositive}
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
              disabled={loadingScan || loadingPositive}
            />
            <InputGroup.Text>¥</InputGroup.Text>
          </InputGroup>
        </Col>
        <Col xs={12} md={3}>
          <Row className="g-2">
            <Col>
              <Button
                className="w-100"
                variant="danger"
                onClick={handleScanNews}
                disabled={loadingScan || loadingPositive}
              >
                {loadingScan ? <Spinner animation="border" size="sm" /> : "Scan News"}
              </Button>
            </Col>
            <Col>
              <Button
                className="w-100"
                variant="success"
                onClick={handleFetchPositiveNews}
                disabled={loadingScan || loadingPositive}
              >
                {loadingPositive ? (
                  <Spinner animation="border" size="sm" />
                ) : (
                  "Fetch Positive"
                )}
              </Button>
            </Col>
          </Row>
        </Col>
      </Row>

      {alertTickers.length > 0 && (
        <div className="mt-3">
          <h6>✅ Positive News Detected:</h6>
          <div style={{ fontSize: "0.9rem" }}>
            {alertTickers.map((item) => (
              <div
                key={`${item.ticker}-${item.created_at || Math.random()}`}
                className="mb-2 p-2 border rounded bg-light"
              >
                <div>
                  <strong>
                    <a
                      href={`https://kabutan.jp/stock/news?code=${item.ticker}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ textDecoration: "none", color: "#0d6efd" }}
                    >
                      {item.ticker}
                    </a>
                  </strong>{" "}
                  -{" "}
                  <em>
                    {item.created_at
                      ? new Date(item.created_at).toLocaleString()
                      : "Date unknown"}
                  </em>
                </div>
                {item.headline && (
                  <div>
                    <strong>Headline: </strong>
                    {item.headline}
                  </div>
                )}
                {item.verdict && (
                  <div>
                    <strong>Verdict: </strong>
                    <span
                      className={
                        item.verdict === "Decisive"
                          ? "text-danger"
                          : item.verdict === "Great"
                          ? "text-success"
                          : item.verdict === "Good"
                          ? "text-primary"
                          : item.verdict === "Neutral"
                          ? "text-muted"
                          : "text-secondary"
                      }
                    >
                      {item.verdict}
                    </span>
                  </div>
                )}
                {item.reason && (
                  <div>
                    <strong>Reason: </strong>
                    {item.reason}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
};

export default PreMarketScanNewsCard;
