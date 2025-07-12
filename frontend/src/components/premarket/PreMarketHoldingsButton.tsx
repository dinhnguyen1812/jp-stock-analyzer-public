import React, { useState } from "react";
import {
  Button,
  Modal,
  Table,
  Spinner,
  Form,
  Row,
  Col,
  Card,
} from "react-bootstrap";
import {
  fetchCurrentEntries,
  addEntryAndAnalyze,
  markEntryAsSold,
  getGptAdviceForHoldings,
} from "../../api";

const PreMarketHoldingButton: React.FC = () => {
  const [showModal, setShowModal] = useState(false);
  const [holdings, setHoldings] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState(false);
  const [ticker, setTicker] = useState("");
  const [amount, setAmount] = useState<number>(0);
  const [entryPrice, setEntryPrice] = useState<number | null>(null);
  const [gptResults, setGptResults] = useState<any[]>([]);
  const [loadingAdvice, setLoadingAdvice] = useState(false);

  const handleShow = async () => {
    setShowModal(true);
    await loadHoldings();
  };

  const loadHoldings = async () => {
    setLoading(true);
    try {
      const data = await fetchCurrentEntries();
      setHoldings(data);
    } catch (error) {
      alert("Failed to fetch holdings");
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = async () => {
    if (!ticker || amount <= 0 || entryPrice === null || entryPrice <= 0) {
      alert("Please enter valid ticker, amount, and entry price.");
      return;
    }
    setAdding(true);
    try {
      await addEntryAndAnalyze(ticker, amount, entryPrice);
      await loadHoldings();
      setTicker("");
      setAmount(0);
      setEntryPrice(null);
    } catch (error: any) {
      alert(error.message || "Failed to add entry");
    } finally {
      setAdding(false);
    }
  };

  const handleGptAdvice = async () => {
    setLoadingAdvice(true);
    try {
      const res = await getGptAdviceForHoldings();
      setGptResults(res.results || []);
    } catch (err: any) {
      alert(err.message || "Failed to fetch GPT advice");
    } finally {
      setLoadingAdvice(false);
    }
  };

  const formatToJST = (utcString: string) => {
    const date = new Date(utcString + "Z");
    return date.toLocaleString("ja-JP", {
      timeZone: "Asia/Tokyo",
      hour12: false,
    });
  };

  return (
    <>
      <Button variant="dark" size="sm" onClick={handleShow} className="mb-3">
        💼 Holdings
      </Button>

      <Modal show={showModal} onHide={() => setShowModal(false)} size="lg" scrollable>
        <Modal.Header closeButton>
          <Modal.Title>Current Holdings</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {/* ➕ Entry Form */}
          <Form className="mb-3">
            <Row className="align-items-end">
              <Col sm={4}>
                <Form.Label>Ticker</Form.Label>
                <Form.Control
                  type="text"
                  value={ticker}
                  onChange={(e) => setTicker(e.target.value.toUpperCase())}
                  placeholder="e.g. 7203"
                />
              </Col>
              <Col sm={2}>
                <Form.Label>Amount</Form.Label>
                <Form.Control
                  type="number"
                  value={amount}
                  onChange={(e) => setAmount(parseInt(e.target.value))}
                  placeholder="e.g. 100"
                  min={1}
                />
              </Col>
              <Col sm={3}>
                <Form.Label>Entry Price (¥)</Form.Label>
                <Form.Control
                  type="number"
                  value={entryPrice ?? ""}
                  onChange={(e) =>
                    setEntryPrice(parseFloat(e.target.value) || 0)
                  }
                  placeholder="e.g. 1450"
                  min={0}
                  step={0.01}
                />
              </Col>
              <Col sm={3}>
                <Button
                  variant="success"
                  className="w-100"
                  onClick={handleAdd}
                  disabled={adding}
                >
                  {adding ? (
                    <Spinner size="sm" animation="border" />
                  ) : (
                    "➕ Add Entry"
                  )}
                </Button>
              </Col>
            </Row>
          </Form>

          {/* 📊 Holdings Table */}
          {loading ? (
            <div className="text-center">
              <Spinner animation="border" />
            </div>
          ) : holdings ? (
            <>
              <Table striped bordered hover size="sm">
                <thead className="table-light">
                  <tr>
                    <th>Ticker</th>
                    <th>Entry Price</th>
                    <th>Current Price</th>
                    <th>Amount</th>
                    <th>Entry Time</th>
                    <th>P/L (¥)</th>
                    <th>P/L (%)</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {holdings.entries.map((entry: any, idx: number) => (
                    <tr key={idx}>
                      <td>{entry.ticker}</td>
                      <td>{entry.entry_price}</td>
                      <td>{entry.current_price}</td>
                      <td>{entry.amount}</td>
                      <td style={{ fontSize: "0.75rem" }}>
                        {formatToJST(entry.entry_time)}
                      </td>
                      <td style={{ color: entry.profit_amount >= 0 ? "green" : "red" }}>
                        {entry.profit_amount}
                      </td>
                      <td style={{ color: entry.profit_percent >= 0 ? "green" : "red" }}>
                        {entry.profit_percent}%
                      </td>
                      <td>
                        <Button
                          variant="outline-danger"
                          size="sm"
                          onClick={async () => {
                            if (window.confirm(`Mark ${entry.ticker} as sold?`)) {
                              try {
                                await markEntryAsSold(entry.id);
                                await loadHoldings();
                              } catch (err: any) {
                                alert(err.message);
                              }
                            }
                          }}
                        >
                          Sold
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>

              {/* 💰 Summary */}
              <div className="mt-3">
                <p>
                  <strong>Total Capital:</strong>{" "}
                  ¥{holdings.summary.total_invested.toLocaleString()}
                </p>
                <p>
                  <strong>Total Current Value:</strong>{" "}
                  ¥{holdings.summary.total_current_value.toLocaleString()}
                </p>
                <p>
                  <strong>Total Profit:</strong>{" "}
                  <span
                    style={{
                      color:
                        holdings.summary.total_profit >= 0 ? "green" : "red",
                    }}
                  >
                    ¥{holdings.summary.total_profit} (
                    {holdings.summary.total_profit_percent}%)
                  </span>
                </p>
              </div>

              {/* 🧠 GPT Advice Button */}
              <div className="d-flex justify-content-end mb-2">
                <Button
                  variant="info"
                  onClick={handleGptAdvice}
                  disabled={loadingAdvice}
                >
                  {loadingAdvice ? (
                    <>
                      <Spinner size="sm" animation="border" /> Asking GPT...
                    </>
                  ) : (
                    "🧠 GPT Advice"
                  )}
                </Button>
              </div>

              {/* 📋 GPT Advice Results */}
              {gptResults.length > 0 && (
                <div className="mt-3">
                  <h5>🧠 GPT Advice for Holdings</h5>
                  {gptResults.map((res, idx) => (
                    <Card key={idx} className="mb-3 shadow-sm">
                      <Card.Body>
                        <Card.Title>
                          {res.ticker} — <strong>{res.recommendation}</strong>{" "}
                          {res.confidence !== null && (
                            <span className="ms-2 text-muted">
                              Confidence: {res.confidence}
                            </span>
                          )}
                        </Card.Title>
                        {(() => {
                          const lines = res.gpt_advice
                            .split("\n")
                            .map((l: string) => l.trim());
                          const summaryStart = lines.findIndex((l: string) =>
                            l.toLowerCase().includes("summary of key")
                          );
                          const adviceStart = lines.findIndex((l: string) =>
                            l.toLowerCase().startsWith("advice:")
                          );
                          const bulletStart = lines.findIndex(
                            (l: string, i: number) =>
                              i > adviceStart && /^[\-\*●•]/.test(l)
                          );
                          const confidenceStart = lines.findIndex((l: string) =>
                            l.toLowerCase().includes("confidence score")
                          );

                          const summaryLines = lines.slice(
                            summaryStart + 1,
                            adviceStart > 0 ? adviceStart : lines.length
                          );
                          const bullets = lines.slice(bulletStart, confidenceStart);
                          const confidenceLine = lines[confidenceStart] || "";

                          return (
                            <>
                              {summaryLines.length > 0 && (
                                <>
                                  <strong>📌 Summary of Key Changes</strong>
                                  <ul>
                                    {summaryLines
                                      .filter((l: string) => l && !l.startsWith("###"))
                                      .map((l: string, i: any) => (
                                        <li key={`s-${i}`}>{l}</li>
                                      ))}
                                  </ul>
                                </>
                              )}

                              <p>
                                <strong>{lines[adviceStart] || "Advice: -"}</strong>
                              </p>

                              {bullets.length > 0 && (
                                <>
                                  <strong>🔍 Justification</strong>
                                  <ul>
                                    {bullets.map((l: string, i: any) => (
                                      <li key={`b-${i}`}>
                                        {l.replace(/^[-*●•] ?/, "")}
                                      </li>
                                    ))}
                                  </ul>
                                </>
                              )}

                              {confidenceLine && (
                                <p>
                                  <strong>🎯 {confidenceLine}</strong>
                                </p>
                              )}
                            </>
                          );
                        })()}
                      </Card.Body>
                    </Card>
                  ))}
                </div>
              )}
            </>
          ) : (
            <p>(No holdings yet)</p>
          )}
        </Modal.Body>
      </Modal>
    </>
  );
};

export default PreMarketHoldingButton;
