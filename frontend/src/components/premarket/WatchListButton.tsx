import React, { useState, useEffect } from "react";
import { Row, Col, Button, Modal, Form, ListGroup, Alert } from "react-bootstrap";
import { getWatchlist, addToWatchlistBatch, removeFromWatchlist } from "../../api";
import MiniCandleChart from "./MiniPriceChart";

export interface TickerInfo {
  ticker: string;
  name: string;
  current_price: number;
  recent_prices?: {
    date: string;
    open: number;
    high: number;
    low: number;
    close: number;
  }[];
}

export function WatchListButton() {
  const [show, setShow] = useState(false);
  const [tickers, setTickers] = useState<TickerInfo[]>([]);
  const [newTickerInput, setNewTickerInput] = useState("");
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  const loadWatchlist = async () => {
    try {
      const data = await getWatchlist();
      setTickers(data);
      setError("");
    } catch {
      setError("Failed to load watchlist.");
    }
  };

  useEffect(() => {
    if (show) {
      loadWatchlist();
    }
  }, [show]);

  const handleAdd = async () => {
    const input = newTickerInput.trim();
    if (!input) return;

    try {
      const added = await addToWatchlistBatch(input);
      setSuccessMessage(`Added: ${added.join(", ")}`);
      setNewTickerInput("");
      setError("");

      // Refresh full watchlist with details
      const updated = await getWatchlist();
      setTickers(updated);
    } catch (err: any) {
      setError(err.message || "Failed to add tickers.");
      setSuccessMessage("");
    }
  };

  const handleRemoveTicker = async (ticker: string) => {
    try {
      await removeFromWatchlist(ticker);
      const updated = await getWatchlist();
      setTickers(updated);
      setSuccessMessage(`Removed: ${ticker}`);
      setError("");
    } catch (err: any) {
      setError(err.message || `Failed to remove ${ticker}.`);
      setSuccessMessage("");
    }
  };

  return (
    <>
      <Button onClick={() => setShow(true)}>Manage Watchlist</Button>

      <Modal size="xl" show={show} onHide={() => setShow(false)}>
        <Modal.Header closeButton>
          <Modal.Title>Watchlist</Modal.Title>
        </Modal.Header>

        <Modal.Body>
          {error && <Alert variant="danger">{error}</Alert>}
          {successMessage && <Alert variant="success">{successMessage}</Alert>}

          <Form.Group>
            <Form.Label>Add New Ticker(s)</Form.Label>
            <Form.Control
              type="text"
              value={newTickerInput}
              onChange={(e) => setNewTickerInput(e.target.value)}
              placeholder="e.g., 4565, 7890, 1234"
            />
            <Form.Text className="text-muted">
              Separate multiple tickers with commas
            </Form.Text>
          </Form.Group>

          <Button onClick={handleAdd} className="mt-2">
            Add
          </Button>

          <hr />
          <h5>Current Watchlist</h5>
          <ListGroup>
            {tickers.map(({ ticker, name, current_price, recent_prices }, idx) => (
              <ListGroup.Item key={idx}>
                <Row className="align-items-center">
                  <Col xs={2} sm={1}>
                    <strong>
                      <a
                        href={`https://kabutan.jp/stock/chart?code=${ticker}`}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {ticker}
                      </a>
                    </strong>
                  </Col>
                  <Col xs={3} sm={3}>
                    {name}
                  </Col>
                  <Col xs={1} sm={1}>
                    {current_price}円
                  </Col>
                  <Col xs={12} sm={4}>
                    {recent_prices && recent_prices.length > 0 ? (
                      <MiniCandleChart
                        data={recent_prices.map(p => ({
                          date: p.date,
                          open: p.open,
                          high: p.high,
                          low: p.low,
                          close: p.close,
                        }))}
                      />
                    ) : (
                      <small className="text-muted">No price data</small>
                    )}
                  </Col>
                  <Col xs={2} sm={2} className="text-end">
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() => handleRemoveTicker(ticker)}
                    >
                      &times;
                    </Button>
                  </Col>
                </Row>
              </ListGroup.Item>
            ))}
          </ListGroup>
        </Modal.Body>

        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShow(false)}>
            Close
          </Button>
        </Modal.Footer>
      </Modal>
    </>
  );
}
