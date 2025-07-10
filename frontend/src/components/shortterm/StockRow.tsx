import React, { useState, useCallback, type JSX } from "react";
import { Button, Modal, Spinner, Badge, Row, Col } from "react-bootstrap";
import type { VolumeSurgeStock, AnalysisSignal } from "../../types";
import {
  fetchSavedAnalysis,
  starStock,
  unstarStock,
} from "../../api";
import { formatDistance } from "date-fns";

interface StockRowProps {
  stock: VolumeSurgeStock;
  latestDetectedAt: string;
  onStarToggle: (ticker: string, starred: boolean) => void;
}

export interface SavedAnalysis {
  volume_info: VolumeSurgeStock;
  analysis_signal: AnalysisSignal;
}

const sentimentKeywords = [
  { word: "bullish", variant: "success" },
  { word: "bearish", variant: "danger" },
  { word: "neutral", variant: "secondary" },
];

const highlightSentiment = (text: string): JSX.Element => {
  const parts = text.split(/(\b(?:bullish|bearish|neutral)\b)/gi);

  return (
    <>
      {parts.map((part, i) => {
        const match = sentimentKeywords.find(
          (k) => k.word.toLowerCase() === part.toLowerCase()
        );
        return match ? (
          <Badge key={i} bg={match.variant} className="mx-1">
            {part}
          </Badge>
        ) : (
          <span key={i}>{part}</span>
        );
      })}
    </>
  );
};

const StockRow: React.FC<StockRowProps> = ({
  stock,
  latestDetectedAt,
  onStarToggle,
}) => {
  const [showModal, setShowModal] = useState(false);
  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starLoading, setStarLoading] = useState(false);
  const [, setForceUpdate] = useState(0); // to force re-render on star toggle

  const handleAnalyzeClick = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchSavedAnalysis(stock.ticker);
      setAnalysis(data);
      setShowModal(true);
    } catch (err: any) {
      setError(err.message || "Failed to load analysis");
    } finally {
      setLoading(false);
    }
  }, [stock.ticker]);

  const handleToggleStar = useCallback(async () => {
    setStarLoading(true);
    try {
      const newStarredStatus = !stock.starred;
      if (newStarredStatus) {
        await starStock(stock.ticker);
      } else {
        await unstarStock(stock.ticker);
      }
      onStarToggle(stock.ticker, newStarredStatus);
      setForceUpdate((prev) => prev + 1);
    } catch {
      alert("Failed to update star status.");
    } finally {
      setStarLoading(false);
    }
  }, [stock, onStarToggle]);

  const recommendationVariant = (rec?: string) => {
    switch (rec) {
      case "Buy":
        return "success";
      case "Sell":
        return "danger";
      default:
        return "secondary";
    }
  };

  const ONE_HOUR_MS = 1000 * 60 * 60;
  const isOld =
    new Date(stock.detected_at).getTime() < new Date(latestDetectedAt).getTime() - ONE_HOUR_MS;

  return (
    <>
      <tr>
        {/* Star Button Column */}
        <td className="text-center align-middle" style={{ width: 40 }}>
          <Button
            variant="outline-secondary"
            size="sm"
            title={stock.starred ? "Unstar stock" : "Star stock"}
            aria-pressed={stock.starred}
            onClick={handleToggleStar}
            disabled={starLoading}
            className="p-0 d-flex justify-content-center align-items-center"
            style={{ width: 32, height: 32 }}
          >
            {starLoading ? (
              <Spinner animation="border" size="sm" />
            ) : (
              <span
                style={{
                  fontSize: "1.25rem",
                  lineHeight: 1,
                  userSelect: "none",
                  color: stock.starred ? "#ffc107" : "#6c757d",
                  pointerEvents: "none",
                  textShadow: stock.starred
                    ? "0 0 6px #ffc107, 0 0 10px #ffc107, 0 0 14px #ffd54f"
                    : "none",
                }}
                aria-hidden="true"
              >
                ★
              </span>
            )}
          </Button>
        </td>

        {/* Remaining Stock Data Columns */}
        <td className="align-middle">{stock.ticker}</td>
        <td className="align-middle">{stock.name}</td>
        <td className="align-middle text-center">{stock.current_price.toFixed(2)}</td>
        <td className="align-middle text-center">{stock.price_change.toFixed(2)}</td>
        <td className="align-middle text-center">{stock.volume_rate.toFixed(2)}</td>
        <td className="align-middle text-center">{stock.money_flow_rate.toFixed(2)}</td>
        <td className="align-middle text-center">{stock.current_volume.toLocaleString()}</td>
        <td className="align-middle text-center">{stock.avg_volume_5d.toLocaleString()}</td>
        <td className="align-middle text-center">
          <span
            style={{
              color: isOld ? "#999" : undefined,
              fontStyle: isOld ? "italic" : undefined,
            }}
            title={new Date(stock.detected_at + "Z").toLocaleString()}
          >
            {formatDistance(
              new Date(stock.detected_at + "Z"),
              new Date(new Date().toISOString()),
              { addSuffix: true }
            )}
          </span>
        </td>

        {/* Analysis Button */}
        <td className="align-middle">
          <div className="d-flex flex-column align-items-center justify-content-center gap-2">
            {stock.recommendation && (
              <div>
                <Badge pill bg={recommendationVariant(stock.recommendation)} className="me-2">
                  {stock.recommendation}
                </Badge>
                <Badge bg="light" text="dark" className="border">
                  {stock.promising_score ?? "?"}
                </Badge>
              </div>
            )}
            <Button
              style={{
                backgroundColor: "rgb(102, 178, 255)",
                color: "black",
                border: "none",
                minWidth: 100,
              }}
              size="sm"
              onClick={handleAnalyzeClick}
              disabled={loading}
              aria-label={`View analysis for ${stock.ticker}`}
            >
              {loading ? <Spinner animation="border" size="sm" /> : "Analysis"}
            </Button>
          </div>
        </td>
      </tr>

      <Modal
        size="lg"
        show={showModal}
        onHide={() => setShowModal(false)}
        scrollable
        aria-labelledby="stock-analysis-modal"
      >
        <Modal.Header closeButton>
          <Modal.Title id="stock-analysis-modal">Analysis for {stock.ticker}</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {error && <p className="text-danger">{error}</p>}
          {!error && !analysis && <p>Loading analysis...</p>}
          {analysis && (
            <>
              <Row>
                <Col md={6}>
                  <h5>Volume Info</h5>
                  <ul>
                    <li>Name: {analysis.volume_info.name}</li>
                    <li>Current Price: {analysis.volume_info.current_price.toFixed(2)}</li>
                    <li>Price Change: {analysis.volume_info.price_change.toFixed(2)}</li>
                    <li>Volume Rate: {analysis.volume_info.volume_rate.toFixed(2)}</li>
                    <li>Money Flow Rate: {analysis.volume_info.money_flow_rate.toFixed(2)}</li>
                    <li>Current Volume: {analysis.volume_info.current_volume.toLocaleString()}</li>
                    <li>Avg Volume (5d): {analysis.volume_info.avg_volume_5d.toLocaleString()}</li>
                    <li>
                      Detected At:{" "}
                      {formatDistance(new Date(analysis.volume_info.detected_at), new Date(), {
                        addSuffix: true,
                      })}
                    </li>
                  </ul>
                </Col>

                <Col md={6}>
                  <h5>Analysis Signals</h5>
                  {analysis.analysis_signal ? (
                    <ul>
                      <li>Candle Pattern: {analysis.analysis_signal.candle_pattern ?? "None"}</li>
                      <li>
                        Breakout: {analysis.analysis_signal.breakout_detected ? "Yes" : "No"}, Resistance: {analysis.analysis_signal.resistance_level ?? "N/A"}, Close: {analysis.analysis_signal.close_today ?? "N/A"}
                      </li>
                      <li>RSI: {analysis.analysis_signal.rsi ?? "N/A"}</li>
                      <li>
                        MACD: Line={analysis.analysis_signal.macd_line ?? "N/A"}, Signal={analysis.analysis_signal.macd_signal ?? "N/A"}, Hist={analysis.analysis_signal.macd_hist ?? "N/A"}
                      </li>
                      <li>
                        BBands: Upper={analysis.analysis_signal.bb_upper ?? "N/A"}, Middle={analysis.analysis_signal.bb_middle ?? "N/A"}, Lower={analysis.analysis_signal.bb_lower ?? "N/A"}, Price={analysis.analysis_signal.bb_current_price ?? "N/A"}
                      </li>
                      <li>
                        MA: SMA50={analysis.analysis_signal.sma_50 ?? "N/A"}, SMA200={analysis.analysis_signal.sma_200 ?? "N/A"}, EMA20={analysis.analysis_signal.ema_20 ?? "N/A"}, Crossover={analysis.analysis_signal.sma_crossover ?? "N/A"}
                      </li>
                      <li>
                        Patterns: W-Shape={analysis.analysis_signal.w_shape ? "Yes" : "No"}, Flags/Pennants={analysis.analysis_signal.flags_pennants ? "Yes" : "No"}, Triangle={analysis.analysis_signal.triangle ? "Yes" : "No"}
                      </li>
                    </ul>
                  ) : (
                    <p className="text-muted">(No analysis signal available)</p>
                  )}
                </Col>
              </Row>

              <h5>Analysis Summary</h5>
              <ul className="list-unstyled">
                <li>
                  <strong>Recommendation:</strong>{" "}
                  <Badge pill bg={recommendationVariant(analysis.volume_info.recommendation)}>
                    {analysis.volume_info.recommendation ?? "N/A"}
                  </Badge>
                </li>
                <li className="mt-2">
                  <strong>Promising Score:</strong>{" "}
                  <Badge bg="light" text="dark" className="border">
                    {analysis.volume_info.promising_score ?? "N/A"}
                  </Badge>
                </li>
              </ul>

              <h6>GPT Reasoning</h6>
              <p style={{ whiteSpace: "pre-wrap" }}>
                {highlightSentiment(analysis.volume_info.reasoning || "(No reasoning provided)")}
              </p>

              {Array.isArray(analysis.volume_info.top_news) &&
                analysis.volume_info.top_news.length > 0 && (
                  <>
                    <h5>Top News</h5>
                    <ul className="list-unstyled">
                      {analysis.volume_info.top_news.map((newsItem: any, index: number) => (
                        <li key={index} style={{ marginBottom: "0.75rem" }}>
                          <a href={newsItem.url} target="_blank" rel="noopener noreferrer">
                            {newsItem.headline}
                          </a>
                          <br />
                          <small className="text-muted">
                            [{newsItem.category}] {new Date(newsItem.published_at).toLocaleString()}
                          </small>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
            </>
          )}
        </Modal.Body>
      </Modal>
    </>
  );
};

export default StockRow;