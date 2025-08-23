import React, { useState, useEffect } from "react";
import {
  Row,
  Col,
  Button,
  Modal,
  Form,
  ListGroup,
  Alert,
  Spinner,
} from "react-bootstrap";
import {
  getWatchlist,
  addToWatchlistBatch,
  removeFromWatchlist,
  analyzeSingleTicker,
} from "../../api";
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
  info?: {
    [key: string]: string;
  };
}

export function WatchListButton() {
  const [show, setShow] = useState(false);
  const [tickers, setTickers] = useState<TickerInfo[]>([]);
  const [newTickerInput, setNewTickerInput] = useState("");
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [loadingTicker, setLoadingTicker] = useState<string | null>(null); // 🔹 track ticker loading

  const loadWatchlist = async () => {
    try {
      const data = await getWatchlist();
      console.log("Fetched watchlist:", data);

      const mapped = data.map((item: any) => {
        const { ticker, name, current_price, recent_prices, ...rest } = item;
        return {
          ticker,
          name,
          current_price,
          recent_prices,
          info: rest,
        };
      });

      setTickers(mapped);
      setError("");
    } catch (err) {
      console.error("Failed to load watchlist:", err);
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

      <Modal size="xl" show={show} onHide={() => setShow(false)} centered>
        <Modal.Header closeButton className="bg-light border-0">
          <Modal.Title className="fw-bold">📌 Watchlist Manager</Modal.Title>
        </Modal.Header>

        <Modal.Body>
          {error && <Alert variant="danger">{error}</Alert>}
          {successMessage && <Alert variant="success">{successMessage}</Alert>}

          {/* Add form */}
          <div className="mb-4 p-3 border rounded bg-light">
            <Form.Group>
              <Form.Label className="fw-semibold">➕ Add New Ticker(s)</Form.Label>
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
            <Button onClick={handleAdd} className="mt-2" variant="primary">
              Add to Watchlist
            </Button>
          </div>

          {/* Watchlist */}
          <h5 className="fw-bold mb-3">📊 Current Watchlist</h5>
          <ListGroup>
            {tickers.map(({ ticker, name, current_price, recent_prices, info }, idx) => (
              <ListGroup.Item key={idx} className="py-2">
                <Row className="align-items-center" style={{ minHeight: "48px" }}>
                  {/* 🔹 Ticker + Name */}
                  <Col
                    xs={2}
                    sm={2}
                    className="d-flex flex-column align-items-center border-end"
                  >
                    <strong>
                      <a
                        href={`https://kabutan.jp/stock/chart?code=${ticker}`}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {ticker}
                      </a>
                    </strong>
                    <div style={{ fontSize: "0.85rem" }}>{name}</div>
                    <div style={{ fontSize: "0.9rem" }}>{current_price}円</div>
                  </Col>

                  {/* 🔹 Chart */}
                  <Col xs={8} sm={3} className="border-end">
                    {recent_prices && recent_prices.length > 0 ? (
                      <MiniCandleChart
                        data={recent_prices.map((p) => ({
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

                  {/* 🔹 Info box */}
                  <Col xs={6} sm={5} className="border-end">
                    {info && Object.keys(info).length > 0 && (
                      <div
                        className="p-1 border rounded"
                        style={{
                          maxHeight: 200,
                          overflowY: "auto",
                          backgroundColor: "#f8f9fa",
                          fontSize: "0.8rem",
                        }}
                      >
                        {Object.entries(info).map(([key, value], i) => {
                          let color = "black";
                          if (value.includes("(good)")) color = "green";
                          else if (value.includes("(neutral)")) color = "blue";
                          else if (value.includes("(bad)")) color = "red";

                          return (
                            <div key={i} style={{ marginBottom: 4 }}>
                              <strong>{key}:</strong>{" "}
                              <span
                                style={
                                  key === "finance" || key === "indicators"
                                    ? { color }
                                    : {}
                                }
                              >
                                {value.split("\n").map((line, idx) => (
                                  <React.Fragment key={idx}>
                                    {line.replace(
                                      /\s*\(good\)|\s*\(neutral\)|\s*\(bad\)/,
                                      ""
                                    )}
                                    <br />
                                  </React.Fragment>
                                ))}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </Col>

                  {/* 🔹 Action buttons */}
                  <Col xs={4} sm={2} className="d-flex justify-content-end gap-2">
                    <Button
                      variant="info"
                      size="sm"
                      disabled={loadingTicker === ticker}
                      onClick={async () => {
                        try {
                          setLoadingTicker(ticker);
                          const res = await analyzeSingleTicker(ticker);
                          setSuccessMessage(res.message || `Analyzed ${ticker}`);
                          setError("");
                        } catch (err: any) {
                          setError(err.message || `Failed to analyze ${ticker}`);
                          setSuccessMessage("");
                        } finally {
                          setLoadingTicker(null);
                        }
                      }}
                    >
                      {loadingTicker === ticker ? (
                        <Spinner
                          as="span"
                          animation="border"
                          size="sm"
                          role="status"
                          aria-hidden="true"
                        />
                      ) : (
                        "Analyze"
                      )}
                    </Button>

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

        <Modal.Footer className="border-0">
          <Button variant="secondary" onClick={() => setShow(false)}>
            Close
          </Button>
        </Modal.Footer>
      </Modal>
    </>
  );
}
