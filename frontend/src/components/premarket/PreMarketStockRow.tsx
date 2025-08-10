import React, { useState, useCallback, type JSX, useEffect } from "react";
import { Button, Modal, Spinner, Badge, Row, Col } from "react-bootstrap";
import { formatDistance } from "date-fns";
import { fetchSavedPremarketAnalysis, fetchSetNote, starStock, unstarStock, watchStock, unwatchStock } from "../../api";
import type { VolumeSurgeStock, AnalysisSignal } from "../../types";
import MiniCandleChart from "./MiniPriceChart";

export interface DailyPrice {
  date: string;   // ISO date string, e.g. "2025-08-09"
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface AnalyzedVolumeInfo extends VolumeSurgeStock {
  recent_prices?: DailyPrice[];
  reasoning?: string;
  recommendation?: "Buy" | "Hold" | "Sell" | null;
  promising_score?: number;
  spiked?: string;
  spike_next?: number;
  top_news?: {
    published_at: string;
    category: string;
    headline: string;
    url: string;
    score: number;
    impact_verdict: string;
    impact_reason: string;
    keyword: string;
    rank: string;
  }[];
  highest_impact_keyword?: string;
  highest_impact_rank?: string;
  drop_from_high_pct?: number;
  rebound_from_low_pct?: number;
  highest_price?: number;
  lowest_price?: number;
  // downtrend?: {
  //   ticker: string;
  //   had_downtrend: boolean;
  //   drop_pct: number;
  //   from_date: string;
  //   to_date: string;
  // };
  // uptrend?: {
  //   ticker: string;
  //   had_uptrend: boolean;
  //   rise_pct: number;
  //   from_date: string;
  //   to_date: string;
  // };
  kabutan_chart_url?: string;
  momentum_score?: number;
  momentum_confidence?: string;
  momentum_signals?: {
    score: number;
    passed: boolean;
    label: string;
    points: number;
    condition: boolean;
    meaning: string;
  }[];
}

export interface SavedAnalysis {
  // longterm_info: any;
  volume_info: AnalyzedVolumeInfo;
  analysis_signal: AnalysisSignal;
}

interface PreMarketStockRowProps {
  stock: VolumeSurgeStock & {
    recent_prices?: DailyPrice[];
    highest_impact_keyword?: string;
    highest_impact_rank?: string;
    promising_score?: number;
    spiked?: string;
    spike_next?: number;
    recommendation?: string | null;
    starred?: boolean;
    watched?: boolean;
    detected_at: string;
    momentum_score?: number;
    momentum_signals?: {
      score: number;
      passed: boolean;
      label: string;
      points: number;
      condition: boolean;
      meaning: string;
    }[];
  };
  latestDetectedAt: string;
  latestThresholdDate: Date | null;
  onStarToggle: (ticker: string, starred: boolean) => void;
  onWatchToggle: (ticker: string, watched: boolean) => void;
  onNoteChange: (ticker: string, newNote: string) => void;
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
  { word: "3_bearish", variant: "danger" }
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

const rankMap = [
  // Rank values
  { word: "S+", variant: "danger" },
  { word: "S", variant: "success" },
  { word: "A+", variant: "primary" },
  { word: "A", variant: "warning" },
  { word: "A-", variant: "info" },
  { word: "B", variant: "secondary" },
  { word: "C", variant: "dark" },
  { word: "D", variant: "dark" }
];

const highlightRank = (text: string): JSX.Element => {
  if (!text) return <span>(No text)</span>;
  const cleanText = text.replace(/\*\*/g, "");
  const keywordRegex = new RegExp(`(${rankMap.map((k) => k.word).join("|")})`, "gi");
  const parts = cleanText.split(keywordRegex);

  return (
    <>
      {parts.map((part, idx) => {
        const match = rankMap.find((k) => k.word.toLowerCase() === part.toLowerCase());
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
  latestThresholdDate,
  onStarToggle,
  onWatchToggle,
  onNoteChange,
}) => {
  const [showModal, setShowModal] = useState(false);
  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState<SavedAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starLoading, setStarLoading] = useState(false);
  const [watchLoading, setWatchLoading] = useState(false);
  const [, setForceUpdate] = useState(0);

  const [noteValue, setNoteValue] = useState(stock.note || "");
  useEffect(() => {
    setNoteValue(stock.note || "");
  }, [stock.note]);

  const handleBlur = () => {
    if (noteValue !== stock.note) {
      onNoteChange(stock.ticker, noteValue);
    }
  };

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

  const handleToggleWatch = useCallback(async () => {
    setWatchLoading(true);
    try {
      const newWatchedStatus = !stock.watched;
      if (newWatchedStatus) await watchStock(stock.ticker);
      else await unwatchStock(stock.ticker);
      onWatchToggle(stock.ticker, newWatchedStatus);
      setForceUpdate((prev) => prev + 1);
    } catch {
      alert("Failed to update watch status.");
    } finally {
      setWatchLoading(false);
    }
  }, [stock, onWatchToggle]);

  const ONE_HOUR_MS = 1000 * 60 * 60;
  const isOld =
    new Date(stock.detected_at).getTime() <
    new Date(latestDetectedAt).getTime() - ONE_HOUR_MS;

  const verdictRank: Record<string, number> = {
    "S+": 7,
    "S": 6,
    "A+": 5,
    "A": 4,
    "A-": 3,
    "B": 2,
    "C": 1,
    "D": 0
  };

  const renderKeySignals = () => {
    const signals = stock.momentum_signals || [];
    return (
      <div className="d-flex flex-wrap gap-2">
        {signals.map((s, i) => (
          <span
            key={i}
            style={{
              fontSize: "0.75rem",
              color: s.passed ? "green" : "gray",
              fontWeight: "bold",
              whiteSpace: "nowrap",
            }}
          >
            {shortenLabel(s.label)}: {s.passed ? "✅" : "⛔"}
            {s.score > 0 ? `+${s.score}` : s.score}
          </span>
        ))}
      </div>
    );
  };

  // Helper to shorten the signal label
  const shortenLabel = (label: string): string => {
    const map: Record<string, string> = {
      "Volume Rate > 3 / 5 / 10": "VR>3",
      "Price vs SMA50": "SMA50",
      "MACD Bullish Crossover": "MACD",
      "RSI Rising into 70+": "RSI↑70",
      "Price Broke Upper BB + Big Candle": "BBBreak",
      "No lower lows in last 5 days": "NoLL",
      "Price above band with reversal wick": "ReversalWick",
      "RSI > 70 but falling": "RSI>70↓",
      "MACD > 0 and rising": "MACD>0↑",
    };
    return map[label] || label.slice(0, 10);
  };

  const [localNote, setLocalNote] = useState<string>(stock.note ?? "");
  const [isSaving, setIsSaving] = useState(false);

  const handleNoteSave = async () => {
    setIsSaving(true);
    try {
      await fetchSetNote(stock.ticker, localNote);
      console.log(`✅ Note updated for ${stock.ticker}`);
    } catch (err) {
      console.error(`❌ Failed to update note:`, err);
      alert("Note update failed");
    }
    setIsSaving(false);
  };

  // const compareIndicator = (
  //   stockValue: string | number | null | undefined,
  //   industryValue: string | number | null | undefined,
  //   type: "higher" | "lower" = "higher"
  // ): string => {
  //   if (stockValue == null || industryValue == null) return "➖";

  //   const s = typeof stockValue === "number" ? stockValue : parseFloat(stockValue);
  //   const i = typeof industryValue === "number" ? industryValue : parseFloat(industryValue);

  //   if (isNaN(s) || isNaN(i)) return "➖";

  //   if (type === "higher") return s >= i ? "✅" : "❌";
  //   if (type === "lower") return s <= i ? "✅" : "❌";

  //   return "➖";
  // };

  return (
    <>
      <tr>
        <td className="align-middle small" style={{ maxWidth: "160px", whiteSpace: "pre-wrap" }}>
          <textarea
            value={noteValue}
            onChange={(e) => setNoteValue(e.target.value)}
            onBlur={handleBlur}
            rows={2}
            style={{ width: "100%", fontSize: "0.75rem" }}
          />
        </td>
        <td className="text-center align-middle" style={{ width: 40 }}>
          <div>
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
                    textShadow: stock.starred
                      ? "0 0 2px #ffc107, 0 0 4px #ffc107"
                      : "none",
                  }}
                  aria-hidden="true"
                >
                  ★
                </span>
              )}
            </Button>
          </div>
          <div>
            <Button
              variant="outline-secondary"
              size="sm"
              title={stock.watched ? "Unwatch stock" : "Watch stock"}
              aria-pressed={stock.watched}
              onClick={handleToggleWatch}
              disabled={watchLoading}
              className="p-0 d-flex justify-content-center align-items-center"
              style={{ width: 32, height: 32 }}
            >
              {watchLoading ? (
                <Spinner animation="border" size="sm" />
              ) : (
                <span
                  style={{
                    fontSize: "1.25rem",
                    lineHeight: 1,
                    userSelect: "none",
                    color: stock.watched ? "#ffc107" : "#6c757d",
                    textShadow: stock.watched
                      ? "0 0 2px #ffc107, 0 0 4px #ffc107"
                      : "none",
                  }}
                  aria-hidden="true"
                >
                  ♥
                </span>
              )}
            </Button>
          </div>
        </td>

        <td className="align-middle text-center">
          <div>{stock.ticker}</div>
          <div>{stock.name}</div>
        </td>
        <td className="align-middle text-center">
          <div>{stock.current_price.toFixed(2)}</div>
          <div>{stock.price_change.toFixed(2)}</div>
        </td>
        <td className="align-middle text-center">
          <div>{stock.volume_rate.toFixed(2)}</div>
          <div>{stock.money_flow_rate.toFixed(2)}</div>
        </td>
        <td className="align-middle text-center">
          <div>{stock.current_volume.toLocaleString()}</div>
          <div>{stock.avg_volume_5d.toLocaleString()}</div>
        </td>

        {/* 🔑 Key Signals column */}
        <td className="align-middle text-start">
          {renderKeySignals()}
        </td>
        {/* 🔑 MiniChart */}
        <td
          className="align-middle text-start"
          style={{ minWidth: 120, maxWidth: 160 }}
        >
          {stock.recent_prices && stock.recent_prices.length > 0 ? (
            <MiniCandleChart
              data={stock.recent_prices.map(p => ({
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
        </td>

        {/* Most impact column */}
        <td className="align-middle text-start">
          {stock.highest_impact_rank && (
            <Badge
              bg="light" // fallback
              className="border border-secondary me-2"
              style={{
                fontSize: "1rem",
                backgroundColor: "white",
                color: {
                  "S+": "#dc3545",         // Red - strong impact
                  "S": "#e5533d",          // Between red and orange
                  "A+": "#fd7e14",         // Orange - high impact
                  "A": "#0d6efd",          // Bootstrap primary blue
                  "A-": "#f0ad4e",         // Lighter orange
                  "B": "#0dcaf0",          // Bootstrap info (cyan)
                  "C": "#6c757d",          // Bootstrap secondary (gray)
                  "D": "#212529"           // Bootstrap dark
                }[stock.highest_impact_rank] ?? "#000000",
              }}
            >
              <span style={{ fontSize: "0.75rem", color: "gray", marginRight: 4 }}>
                {stock.highest_impact_keyword}:
              </span>
              {stock.highest_impact_rank.replace(/\*/g, "").trim()}
            </Badge>
          )}
          <div style={{ height: 8 }} /> {/* Space between rows */}
          {stock.spiked !== undefined && (
            <Badge
              bg={stock.spiked.toLowerCase() === "yes" ? "success" : "danger"}
              className="border me-2"
              style={{ fontSize: "0.75rem" }}
            >
              Spike: {stock.spiked}
            </Badge>
          )}
          {stock.spike_next !== undefined && (
            <Badge
              bg={
                stock.spike_next >= 80
                  ? "success"
                  : stock.spike_next >= 60
                  ? "info"
                  : stock.spike_next >= 40
                  ? "warning"
                  : "danger"
              }
              className="border"
              style={{ fontSize: "0.75rem" }}
            >
              Spike next: {stock.spike_next}
            </Badge>
          )}
        </td>

        {/* Action/GPT column */}
        <td className="align-middle text-center">
          <div className="d-flex flex-column align-items-center justify-content-center gap-1">
            <div className="d-flex flex-wrap justify-content-center align-items-center gap-2">
              {stock.recommendation && (
                <Badge pill bg={
                  stock.recommendation === "Buy"
                    ? "success"
                    : stock.recommendation === "Sell"
                    ? "danger"
                    : "warning"
                }>
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

              {Array.isArray(stock.top_news) && stock.top_news.length > 0 && latestThresholdDate && (() => {
                const newsWithVerdict = stock.top_news.filter(
                  (n) => typeof n.impact_verdict === "string"
                );
                if (newsWithVerdict.length === 0) return null;

                const bestNews = newsWithVerdict.sort((a, b) => {
                  const aRank = verdictRank[a.impact_verdict?.toUpperCase() ?? ""] ?? 0;
                  const bRank = verdictRank[b.impact_verdict?.toUpperCase() ?? ""] ?? 0;
                  return bRank - aRank;
                })[0];

                const verdict = bestNews.impact_verdict?.toUpperCase() ?? "";

                const badgeColor =
                  verdict === "S+" ? "danger" :
                  verdict === "S" ? "success" :
                  verdict === "A+" ? "primary" :
                  verdict === "A" ? "warning" :
                  verdict === "A-" ? "info" :
                  verdict === "B" ? "secondary" :
                  verdict === "C" || verdict === "D" ? "dark" :
                  "light";

                const textColor = verdict === "C" || verdict === "D" ? "dark" : "light";

                const publishedAt = new Date(bestNews.published_at);
                const thresholdDate = new Date(
                  Date.UTC(
                    latestThresholdDate.getUTCFullYear(),
                    latestThresholdDate.getUTCMonth(),
                    latestThresholdDate.getUTCDate(),
                    6, 29, 0 // 06:29 UTC = 15:29 JST
                  )
                );

                const isVeryRecent = publishedAt >= thresholdDate;
                const verdictLabel = `${verdict}${isVeryRecent ? " ⭐️" : ""}`;

                return (
                  <Badge
                    bg={badgeColor}
                    text={textColor}
                    className="border"
                    style={{ fontSize: "0.75rem" }}
                  >
                    {verdictLabel}
                  </Badge>
                );
              })()}
              <Button
                variant="outline-secondary"
                size="sm"
                onClick={handleAnalysisClick}
                disabled={loading}
                style={{
                  minWidth: 90,
                  fontSize: "0.75rem",
                  padding: "0.25rem 0.5rem",
                }}
              >
                {loading ? <Spinner animation="border" size="sm" /> : "Analysis"}
              </Button>
            </div>
          </div>
        </td>
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
      </tr>

      <Modal size="xl" show={showModal} onHide={() => setShowModal(false)} scrollable>
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
                    <li>Volume Rate: {analysis.volume_info.volume_rate.toFixed(2)}</li>
                    <li>Money Flow Rate: {analysis.volume_info.money_flow_rate.toFixed(2)}</li>
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
                      <li>Candle Pattern: {highlightKeywords(analysis.analysis_signal.candle_pattern ?? "None")}</li>
                      <li>
                        Breakout: {highlightKeywords(analysis.analysis_signal.breakout_detected ? "Yes" : "No")},{" "}
                        Resistance: {analysis.analysis_signal.resistance_level ?? "N/A"},{" "}
                        Close: {analysis.analysis_signal.close_today ?? "N/A"}
                      </li>
                      <li>RSI: {analysis.analysis_signal.rsi ?? "N/A"}</li>
                      <li>
                        MACD: Line={analysis.analysis_signal.macd_line ?? "N/A"}, Signal={analysis.analysis_signal.macd_signal ?? "N/A"}, Hist={analysis.analysis_signal.macd_hist ?? "N/A"}
                      </li>
                      <li>
                        BBands: Upper={analysis.analysis_signal.bb_upper?.toFixed(2) ?? "N/A"}, Middle={analysis.analysis_signal.bb_middle?.toFixed(2) ?? "N/A"}, Lower={analysis.analysis_signal.bb_lower?.toFixed(2) ?? "N/A"}, Price={analysis.analysis_signal.bb_current_price?.toFixed(2) ?? "N/A"}
                      </li>
                      <li>SMA50: {analysis.analysis_signal.sma_50 ?? "N/A"}</li>
                      <li>SMA200: {analysis.analysis_signal.sma_200 ?? "N/A"}, EMA20: {analysis.analysis_signal.ema_20 ?? "N/A"}, Crossover: {analysis.analysis_signal.sma_crossover ?? "N/A"}</li>
                      <li>
                        Patterns: W-Shape={highlightKeywords(analysis.analysis_signal.w_shape ? "Yes" : "No")}, Flags/Pennants={highlightKeywords(analysis.analysis_signal.flags_pennants ? "Yes" : "No")}, Triangle={highlightKeywords(analysis.analysis_signal.triangle ? "Yes" : "No")}
                      </li>
                    </ul>
                  ) : (
                    <p className="text-muted">(No analysis signal available)</p>
                  )}
                </Col>

                {/* Long-Term Indicator Column */}
                {/* <Col md={3}>
                  <h5>📊 Long-Term Indicators</h5>
                  <ul>
                    <li>
                      PER: {analysis.longterm_info.stock_per} vs Industry Avg: {analysis.longterm_info.industry_per}{" "}
                      {compareIndicator(analysis.longterm_info.stock_per, analysis.longterm_info.industry_per, "lower")}
                    </li>
                    <li>
                      PBR: {analysis.longterm_info.stock_pbr} vs Industry Avg: {analysis.longterm_info.industry_pbr}{" "}
                      {compareIndicator(analysis.longterm_info.stock_pbr, analysis.longterm_info.industry_pbr, "lower")}
                    </li>
                    <li>
                      ROE: {analysis.longterm_info.stock_roe}% vs Industry Avg: {analysis.longterm_info.industry_roe}%{" "}
                      {compareIndicator(analysis.longterm_info.stock_roe, analysis.longterm_info.industry_roe, "higher")}
                    </li>
                    <li>
                      EPS: {analysis.longterm_info.eps} / BPS: {analysis.longterm_info.bps}
                    </li>
                    <li>
                      Dividend Yield: {analysis.longterm_info.dividend_yield}%{" "}
                      {compareIndicator(analysis.longterm_info.dividend_yield, 1, "higher")}
                    </li>
                    <li>
                      Debt Ratio: {analysis.longterm_info.debt_ratio}%{" "}
                      {compareIndicator(analysis.longterm_info.debt_ratio, 100, "lower")}
                    </li>
                    <li>Market Cap: ¥{analysis.longterm_info.market_cap}</li>
                    <li>
                      Industry: {analysis.longterm_info.industry_name || "N/A"}
                    </li>
                  </ul>
                </Col> */}

                <Col md={4}>
                  {/* <h5>Recent Uptrend</h5>
                  {analysis.volume_info.uptrend ? (
                    <ul>
                      <li>Had Uptrend: {highlightKeywords(analysis.volume_info.uptrend.had_uptrend ? "Yes" : "No")}</li>
                      <li>Rise %: {analysis.volume_info.uptrend.rise_pct !== undefined ? analysis.volume_info.uptrend.rise_pct.toFixed(2) : "N/A"}</li>
                      <li>From: {analysis.volume_info.uptrend.from_date ?? "N/A"} To: {analysis.volume_info.uptrend.to_date ?? "N/A"}</li>
                    </ul>
                  ) : (
                    <p className="text-muted">(No uptrend data)</p>
                  )}

                  <h5>Recent Downtrend</h5>
                  {analysis.volume_info.downtrend ? (
                    <ul>
                      <li>Had Downtrend: {highlightKeywords(analysis.volume_info.downtrend.had_downtrend ? "Yes" : "No")}</li>
                      <li>Drop %: {analysis.volume_info.downtrend.drop_pct !== undefined ? analysis.volume_info.downtrend.drop_pct.toFixed(2) : "N/A"}</li>
                      <li>From: {analysis.volume_info.downtrend.from_date ?? "N/A"} To: {analysis.volume_info.downtrend.to_date ?? "N/A"}</li>
                    </ul>
                  ) : (
                    <p className="text-muted">(No downtrend data)</p>
                  )} */}
                  <h5 className="mb-3">📉 15-Day Chart</h5>
                  {analysis.volume_info.recent_prices &&
                  analysis.volume_info.recent_prices.length > 0 ? (
                    <MiniCandleChart
                      data={analysis.volume_info.recent_prices.map(p => ({
                        date: p.date,
                        open: p.open,
                        high: p.high,
                        low: p.low,
                        close: p.close,
                      }))}
                    />
                  ) : (
                    <p className="text-muted">No price data</p>
                  )}

                  <h5 className="mt-4">📈{" "}
                    <a
                      href={analysis.volume_info.kabutan_chart_url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      View Kabutan Chart
                    </a>
                  </h5>
                </Col>
              </Row>

              {/* NEW MOMENTUM SIGNALS SECTION */}
              <Row className="mt-4">
                <Col>
                  <h5>Momentum Score: {analysis.volume_info.momentum_score ?? "N/A"}</h5>
                  <p>Confidence: {analysis.volume_info.momentum_confidence ?? "N/A"}</p>
                  <h5>Momentum Signals (🔑 must be satisfied)</h5>
                  {analysis.volume_info.momentum_signals && analysis.volume_info.momentum_signals.length > 0 ? (
                    <ul>
                      {analysis.volume_info.momentum_signals.map((signal, idx) => {
                        const isCritical =
                          signal.label === "Volume Rate > 3 / 5 / 10" ||
                          signal.label === "Price vs SMA50" ||
                          signal.label === "MACD Bullish Crossover";

                        const scoreColor =
                          signal.score < 0
                            ? { color: "red", fontWeight: "bold" }
                            : signal.passed
                            ? { color: "#0d6efd", fontWeight: "bold" }
                            : {};

                        return (
                          <li key={idx}>
                            <strong style={isCritical ? { color: "#8f2825" } : {}}>
                              {isCritical ? "🔑 " : ""}
                              {signal.label}
                            </strong>
                            :{" "}
                            <span style={scoreColor}>
                              {signal.passed ? "✅" : "❌"} {signal.score > 0 ? `+${signal.score}` : signal.score} — {signal.meaning}
                            </span>
                          </li>
                        );
                      })}
                    </ul>
                  ) : (
                    <p className="text-muted">(No momentum signals available)</p>
                  )}
                </Col>
              </Row>

              <h5 className="mt-4">Summary</h5>
              <div className="mb-4">
                {analysis.volume_info.recommendation && (
                  <div className="mb-1">
                    Recommendation: {highlightKeywords(analysis.volume_info.recommendation)}
                  </div>
                )}
                <div className="mb-1">Promising Score: {analysis.volume_info.promising_score ?? "?"}</div>
              </div>

              <h5 className="mt-4">GPT Reasoning</h5>
              <p style={{ whiteSpace: "pre-wrap" }}>
                {highlightKeywords(analysis.volume_info.reasoning || "(No reasoning provided)")}
              </p>

              {Array.isArray(analysis.volume_info.top_news) && analysis.volume_info.top_news.length > 0 && (
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
                        <strong>Keyword:</strong> {item.keyword}: {highlightRank(item.rank)}
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
          <div className="mt-3">
            <label htmlFor="stock-note" className="form-label fw-bold">📝 Note</label>
            <textarea
              id="stock-note"
              className="form-control"
              rows={3}
              value={localNote}
              onChange={(e) => setLocalNote(e.target.value)}
              disabled={isSaving}
            />
            <button
              className="btn btn-primary btn-sm mt-2"
              onClick={handleNoteSave}
              disabled={isSaving}
            >
              {isSaving ? "Saving..." : "Save Note"}
            </button>
          </div>

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
