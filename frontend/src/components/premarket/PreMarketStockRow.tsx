import React, { useState, useCallback, type JSX } from "react";
import { Button, Modal, Spinner, Badge, Row, Col } from "react-bootstrap";
import type { VolumeSurgeStock, AnalysisSignal } from "../../types";
import { fetchSavedPremarketAnalysis, starStock, unstarStock } from "../../api";
import { formatDistance } from "date-fns";

interface PreMarketStockRowProps {
  stock: VolumeSurgeStock & {
    watchlist_recommendation?: string;
    promising_score?: number;
    recommendation?: string | null;
    starred?: boolean;
    detected_at: string;
    momentum_score?: number;  // Make sure momentum_score is included here
  };
  latestDetectedAt: string;
  onStarToggle: (ticker: string, starred: boolean) => void;
}

export interface AnalyzedVolumeInfo extends VolumeSurgeStock {
  reasoning?: string;
  recommendation?: "Buy" | "Hold" | "Sell" | null;
  promising_score?: number;
  top_news?: {
    published_at: string;
    category: string;
    headline: string;
    url: string;
    score: number;
    impact_verdict: string;
    impact_reason: string;
  }[];
  watchlist_recommendation?: string;
  drop_from_high_pct?: number;
  rebound_from_low_pct?: number;
  highest_price?: number;
  lowest_price?: number;
  downtrend?: {
    ticker: string;
    had_downtrend: boolean;
    drop_pct: number;
    from_date: string;
    to_date: string;
  };
  uptrend?: {
    ticker: string;
    had_uptrend: boolean;
    rise_pct: number;
    from_date: string;
    to_date: string;
  };
  momentum_score?: number;
  momentum_confidence?: string;
}

export interface SavedAnalysis {
  volume_info: AnalyzedVolumeInfo;
  analysis_signal: AnalysisSignal;
}

const keywordMap = [
  { word: "bullish", variant: "success" },
  { word: "bearish", variant: "danger" },
  { word: "neutral", variant: "secondary" },
  { word: "Buy", variant: "success" },
  { word: "Sell", variant: "danger" },
  { word: "Hold", variant: "warning" },
  { word: "short-term", variant: "warning" },
  { word: "Yes", variant: "success" },
  { word: "3_bullish", variant: "success" },
  { word: "3_bearish", variant: "danger" },
  { word: "decisive", variant: "danger" },
  { word: "great", variant: "success" },
  { word: "good", variant: "warning" },
  { word: "bad", variant: "secondary" },
];

const highlightKeywords = (text: string): JSX.Element => {
  if (!text) return <span>(No text)</span>;
  const cleanText = text.replace(/\*\*/g, "");
  const keywordRegex = new RegExp(`(${keywordMap.map((k) => k.word).join("|")})`, "gi");
  const parts = cleanText.split(keywordRegex);

  return (
    <>
      {parts.map((part, idx) => {
        const match = keywordMap.find((k) => k.word.toLowerCase() === part.toLowerCase());
        return match ? (
          <Badge key={idx} bg={match.variant} className="mx-1">
            {part}
          </Badge>
        ) : (
          <span key={idx}>{part}</span>
        );
      })}
    </>
  );
};

const PreMarketStockRow: React.FC<PreMarketStockRowProps> = ({
  stock,
  latestDetectedAt,
  onStarToggle,
}) => {
  const [showModal, setShowModal] = useState(false);
  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState<SavedAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starLoading, setStarLoading] = useState(false);
  const [, setForceUpdate] = useState(0);

  const handleAnalysisClick = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result: SavedAnalysis = await fetchSavedPremarketAnalysis(stock.ticker);
      setAnalysis(result);
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
      if (newStarredStatus) await starStock(stock.ticker);
      else await unstarStock(stock.ticker);
      onStarToggle(stock.ticker, newStarredStatus);
      setForceUpdate((prev) => prev + 1);
    } catch {
      alert("Failed to update star status.");
    } finally {
      setStarLoading(false);
    }
  }, [stock, onStarToggle]);

  const recommendationVariant = (rec?: string | null) => {
    switch (rec) {
      case "Buy":
        return "success";
      case "Sell":
        return "danger";
      case "Short":
        return "warning";
      default:
        return "secondary";
    }
  };

  const ONE_HOUR_MS = 1000 * 60 * 60;
  const isOld =
    new Date(stock.detected_at).getTime() <
    new Date(latestDetectedAt).getTime() - ONE_HOUR_MS;

  const verdictRank: Record<string, number> = {
    decisive: 5,
    great: 4,
    good: 3,
    neutral: 2,
    bad: 1,
  };

  const highlightSignal = (
    label: string,
    value: React.ReactNode,
    condition: boolean,
    points: number
  ) => {
    return (
      <li>
        {label}:{" "}
        <span style={condition ? { fontWeight: "bold", color: "#0d6efd" } : {}}>
          {value} {condition && <Badge bg="primary">+{points}</Badge>}
        </span>
      </li>
    );
  };

  return (
    <>
      {/* ROW */}
      <tr>
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

        <td className="align-middle text-center">{stock.ticker}</td>
        <td className="align-middle">{stock.name}</td>
        <td className="align-middle text-center">{stock.current_price.toFixed(2)}</td>
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
            {formatDistance(new Date(stock.detected_at + "Z"), new Date(), {
              addSuffix: true,
            })}
          </span>
        </td>

        <td className="align-middle text-center">
          <div className="d-flex align-items-center justify-content-center flex-wrap gap-2">
            {stock.recommendation && (
              <Badge pill bg={recommendationVariant(stock.recommendation)}>
                {stock.recommendation}
              </Badge>
            )}

            {stock.promising_score !== undefined && (
              <Badge
                bg={
                  stock.promising_score >= 80
                    ? "success"
                    : stock.promising_score >= 60
                    ? "info"
                    : stock.promising_score >= 40
                    ? "warning"
                    : "danger"
                }
                className="border"
                style={{ fontSize: "0.75rem" }}
              >
                Score: {stock.promising_score}
              </Badge>
            )}

            {stock.momentum_score !== undefined && (
              <Badge
                bg={
                  stock.momentum_score >= 8
                    ? "success"
                    : stock.momentum_score >= 6
                    ? "info"
                    : stock.momentum_score >= 4
                    ? "warning"
                    : "danger"
                }
                className="border"
                style={{ fontSize: "0.75rem" }}
              >
                Signal: {stock.momentum_score}
              </Badge>
            )}


            {Array.isArray(stock.top_news) && stock.top_news.length > 0 && (() => {
              const newsWithVerdict = stock.top_news.filter(
                (n) => typeof n.impact_verdict === "string"
              );
              if (newsWithVerdict.length === 0) return null;
              const bestNews = newsWithVerdict.sort((a, b) => {
                const aRank = verdictRank[a.impact_verdict?.toLowerCase() ?? ""] ?? 0;
                const bRank = verdictRank[b.impact_verdict?.toLowerCase() ?? ""] ?? 0;
                return bRank - aRank;
              })[0];
              const verdict = bestNews.impact_verdict?.toLowerCase() ?? "";
              const badgeColor =
                verdict === "decisive"
                  ? "danger"
                  : verdict === "great"
                  ? "success"
                  : verdict === "good"
                  ? "warning"
                  : verdict === "neutral"
                  ? "secondary"
                  : "light";
              const textColor = verdict === "bad" ? "dark" : "light";
              return (
                <Badge
                  bg={badgeColor}
                  text={textColor}
                  className="border"
                  style={{ fontSize: "0.75rem" }}
                >
                  📰 {bestNews.impact_verdict}
                </Badge>
              );
            })()}

            {stock.watchlist_recommendation && (
              <Badge
                bg="light"
                text={
                  stock.watchlist_recommendation.replace(/\*/g, "").trim().toLowerCase() === "yes"
                    ? "success"
                    : "danger"
                }
                className="border"
                style={{ fontSize: "0.75rem" }}
              >
                <span style={{ fontSize: "0.75rem", color: "gray" }}> Watch: </span>
                {stock.watchlist_recommendation.replace(/\*/g, "").trim()}
              </Badge>
            )}

            <Button
              style={{
                backgroundColor: "rgb(102, 178, 255)",
                color: "black",
                border: "none",
                minWidth: 100,
                padding: "0.25rem 0.5rem",
                fontSize: "0.8rem",
              }}
              size="sm"
              onClick={handleAnalysisClick}
              disabled={loading}
              aria-label={`View analysis for ${stock.ticker}`}
            >
              {loading ? <Spinner animation="border" size="sm" /> : "Analysis"}
            </Button>
          </div>
        </td>
      </tr>

      {/* Modal for detailed analysis */}
      <Modal size="lg" show={showModal} onHide={() => setShowModal(false)} scrollable>
        <Modal.Header closeButton>
          <Modal.Title>Analysis for {stock.ticker}</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {error && <p className="text-danger">{error}</p>}
          {!error && !analysis && <p>Loading analysis...</p>}
          {analysis && (
            <>
              <Row>
                <Col md={4}>
                  <h5>Volume Info</h5>
                  <ul>
                    <li>Name: {analysis.volume_info.name}</li>
                    <li>Current Price: {analysis.volume_info.current_price.toFixed(2)}</li>
                    <li>Price Change: {analysis.volume_info.price_change.toFixed(2)}</li>

                    {highlightSignal(
                      "Volume Rate",
                      analysis.volume_info.volume_rate.toFixed(2),
                      analysis.volume_info.volume_rate > 3,
                      3
                    )}

                    {highlightSignal(
                      "Money Flow Rate",
                      analysis.volume_info.money_flow_rate.toFixed(2),
                      analysis.volume_info.money_flow_rate > 3,
                      1
                    )}

                    <li>Current Volume: {analysis.volume_info.current_volume.toLocaleString()}</li>
                    <li>Avg Volume (5d): {analysis.volume_info.avg_volume_5d.toLocaleString()}</li>
                    <li>
                      Detected At:{" "}
                      {formatDistance(new Date(analysis.volume_info.detected_at + "Z"), new Date(), {
                        addSuffix: true,
                      })}
                    </li>
                    <li>
                      Drop From High (%): {analysis.volume_info.drop_from_high_pct?.toFixed(2) ?? "N/A"}
                    </li>
                    <li>
                      Rebound From Low (%): {analysis.volume_info.rebound_from_low_pct?.toFixed(2) ?? "N/A"}
                    </li>
                    <li>Highest Price: {analysis.volume_info.highest_price ?? "N/A"}</li>
                    <li>Lowest Price: {analysis.volume_info.lowest_price ?? "N/A"}</li>
                  </ul>
                </Col>

                <Col md={4}>
                  <h5>Analysis Signals</h5>
                  {analysis.analysis_signal ? (
                    <ul>
                      <li>
                        Candle Pattern: {highlightKeywords(analysis.analysis_signal.candle_pattern ?? "None")}
                      </li>
                      <li>
                        Breakout:{" "}
                        {highlightKeywords(analysis.analysis_signal.breakout_detected ? "Yes" : "No")},{" "}
                        Resistance: {analysis.analysis_signal.resistance_level ?? "N/A"},{" "}
                        Close: {analysis.analysis_signal.close_today ?? "N/A"}
                      </li>

                      {highlightSignal(
                        "RSI",
                        analysis.analysis_signal.rsi ?? "N/A",
                        (analysis.analysis_signal.rsi ?? 0) > 70,
                        1
                      )}

                      <li>
                        MACD: Line={analysis.analysis_signal.macd_line ?? "N/A"}, Signal=
                        {analysis.analysis_signal.macd_signal ?? "N/A"}, Hist=
                        <span
                          style={
                            (analysis.analysis_signal.macd_hist ?? 0) > 0
                              ? { fontWeight: "bold", color: "#0d6efd" }
                              : {}
                          }
                        >
                          {analysis.analysis_signal.macd_hist ?? "N/A"}{" "}
                          {(analysis.analysis_signal.macd_hist ?? 0) > 0 && <Badge bg="primary">+1</Badge>}
                        </span>
                      </li>

                      <li>
                        BBands: Upper={
                          (analysis.analysis_signal.bb_current_price ?? 0) > (analysis.analysis_signal.bb_upper ?? Infinity) ? (
                            <span style={{ fontWeight: "bold", color: "#0d6efd" }}>
                              {analysis.analysis_signal.bb_upper?.toFixed(2) ?? "N/A"}
                            </span>
                          ) : (
                            analysis.analysis_signal.bb_upper?.toFixed(2) ?? "N/A"
                          )
                        }, Middle={analysis.analysis_signal.bb_middle?.toFixed(2) ?? "N/A"}, Lower={analysis.analysis_signal.bb_lower?.toFixed(2) ?? "N/A"}, Price={analysis.analysis_signal.bb_current_price?.toFixed(2) ?? "N/A"}{" "}
                        {(analysis.analysis_signal.bb_current_price ?? 0) > (analysis.analysis_signal.bb_upper ?? Infinity) && (
                          <Badge bg="primary">+1</Badge>
                        )}
                      </li>

                      {highlightSignal(
                        "SMA50",
                        analysis.analysis_signal.sma_50 ?? "N/A",
                        analysis.volume_info.current_price > (analysis.analysis_signal.sma_50 ?? 0),
                        2
                      )}

                      <li>
                        SMA200={analysis.analysis_signal.sma_200 ?? "N/A"}, EMA20=
                        {analysis.analysis_signal.ema_20 ?? "N/A"}, Crossover=
                        {analysis.analysis_signal.sma_crossover ?? "N/A"}
                      </li>
                      <li>
                        Patterns: W-Shape={highlightKeywords(analysis.analysis_signal.w_shape ? "Yes" : "No")},
                        Flags/Pennants={highlightKeywords(analysis.analysis_signal.flags_pennants ? "Yes" : "No")},
                        Triangle={highlightKeywords(analysis.analysis_signal.triangle ? "Yes" : "No")}
                      </li>
                    </ul>
                  ) : (
                    <p className="text-muted">(No analysis signal available)</p>
                  )}
                </Col>

                <Col md={4}>
                  <h5>Recent Downtrend</h5>
                  {analysis.volume_info.downtrend ? (
                    <ul>
                      <li>
                        Had Downtrend:{" "}
                        <span
                          style={
                            analysis.volume_info.downtrend.had_downtrend === false
                              ? { fontWeight: "bold", color: "#0d6efd" }
                              : {}
                          }
                        >
                          {highlightKeywords(
                            analysis.volume_info.downtrend.had_downtrend ? "Yes" : "No"
                          )}{" "}
                          {!analysis.volume_info.downtrend.had_downtrend && (
                            <Badge bg="primary">+1</Badge>
                          )}
                        </span>
                      </li>
                      <li>
                        Drop %:{" "}
                        {analysis.volume_info.downtrend.drop_pct !== undefined
                          ? analysis.volume_info.downtrend.drop_pct.toFixed(2)
                          : "N/A"}
                      </li>
                      <li>
                        From: {analysis.volume_info.downtrend.from_date ?? "N/A"} &nbsp;
                        To: {analysis.volume_info.downtrend.to_date ?? "N/A"}
                      </li>
                    </ul>
                  ) : (
                    <p className="text-muted">(No downtrend data)</p>
                  )}

                  <h5 className="mt-4">Recent Uptrend</h5>
                  {analysis.volume_info.uptrend ? (
                    <ul>
                      <li>
                        Had Uptrend:{" "}
                        <span
                          style={
                            analysis.volume_info.uptrend.had_uptrend === false
                              ? { fontWeight: "bold", color: "#0d6efd" }
                              : {}
                          }
                        >
                          {highlightKeywords(analysis.volume_info.uptrend.had_uptrend ? "Yes" : "No")}{" "}
                          {!analysis.volume_info.uptrend.had_uptrend && (
                            <Badge bg="primary">+1</Badge>
                          )}
                        </span>
                      </li>
                      <li>
                        Rise %:{" "}
                        {analysis.volume_info.uptrend.rise_pct !== undefined
                          ? analysis.volume_info.uptrend.rise_pct.toFixed(2)
                          : "N/A"}
                      </li>
                      <li>
                        From: {analysis.volume_info.uptrend.from_date ?? "N/A"} &nbsp;
                        To: {analysis.volume_info.uptrend.to_date ?? "N/A"}
                      </li>
                    </ul>
                  ) : (
                    <p className="text-muted">(No uptrend data)</p>
                  )}

                  <h5 className="mt-4">Momentum Score</h5>
                  <p>
                    {analysis.volume_info.momentum_score ?? "N/A"}{" "}
                    <small>
                      (
                      {analysis.volume_info.momentum_confidence
                        ? analysis.volume_info.momentum_confidence
                        : "No confidence info"}
                      )
                    </small>
                  </p>
                </Col>
              </Row>

              <h5 className="mt-4">Summary</h5>
              <div className="mb-4">
                {analysis.volume_info.recommendation && (
                  <div className="mb-1">
                    Recommendation: {highlightKeywords(analysis.volume_info.recommendation)}
                  </div>
                )}
                <div className="mb-1">
                  Promising Score: {analysis.volume_info.promising_score ?? "?"}
                </div>
                <div className="mb-1">
                  Watchlist Recommendation:{" "}
                  {highlightKeywords(analysis.volume_info.watchlist_recommendation || "")}
                </div>
              </div>

              <h5 className="mt-4">GPT Reasoning</h5>
              <p style={{ whiteSpace: "pre-wrap" }}>
                {highlightKeywords(analysis.volume_info.reasoning || "(No reasoning provided)")}
              </p>

              {Array.isArray(analysis.volume_info.top_news) &&
                analysis.volume_info.top_news.length > 0 && (
                  <>
                    <h5 className="mt-4">Top News</h5>
                    <ul className="list-unstyled">
                      {analysis.volume_info.top_news.map((item, idx) => (
                        <li key={idx} className="mb-3">
                          <a href={item.url} target="_blank" rel="noopener noreferrer">
                            {item.headline}
                          </a>
                          <br />
                          <small className="text-muted">
                            [{item.category}] {new Date(item.published_at).toLocaleString()}
                          </small>
                          <br />
                          <strong>Impact Verdict:</strong>{" "}
                          {highlightKeywords(item.impact_verdict)}
                          <br />
                          <em style={{ display: "block", marginTop: "0.25rem" }}>
                            {highlightKeywords(item.impact_reason)}
                          </em>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
            </>
          )}
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowModal(false)}>
            Close
          </Button>
        </Modal.Footer>
      </Modal>
    </>
  );
};

export default PreMarketStockRow;
