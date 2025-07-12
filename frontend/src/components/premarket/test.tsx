import React, { useState, useCallback, type JSX } from "react";
import { Button, Modal, Spinner, Badge, Row, Col } from "react-bootstrap";
import type { VolumeSurgeStock, AnalysisSignal } from "../../types";
import { fetchAllAnalyses, starStock, unstarStock } from "../../api";
import { formatDistance } from "date-fns";

interface PreMarketStockRowProps {
  stock: VolumeSurgeStock & {
    watchlist_recommendation?: string;
    promising_score?: number;
    recommendation?: string | null;
    starred?: boolean;
    detected_at: string;
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
}

export interface SavedAnalysis {
  volume_info: AnalyzedVolumeInfo;
  analysis_signal: AnalysisSignal;
}

// Keyword highlighting logic
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

  const handleAnalyzeClick = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const allData: SavedAnalysis[] = await fetchAllAnalyses();
      const found = allData.find((item) => item.volume_info.ticker === stock.ticker);
      if (!found) throw new Error(`No analysis found for ticker ${stock.ticker}`);
      setAnalysis(found);
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

  const verdictRank: Record<string, number> = {
    decisive: 5,
    great: 4,
    good: 3,
    neutral: 2,
    bad: 1,
  };

  const ONE_HOUR_MS = 1000 * 60 * 60;
  const isOld =
    new Date(stock.detected_at).getTime() <
    new Date(latestDetectedAt).getTime() - ONE_HOUR_MS;

  return (
    <>
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
              <Badge bg="light" text="dark" className="border">
                Score: {stock.promising_score}
              </Badge>
            )}

            {Array.isArray(stock.top_news) && stock.top_news.length > 0 && (() => {
              const bestNews = stock.top_news
                .filter((n) => n.impact_verdict)
                .sort((a, b) =>
                  (verdictRank[b.impact_verdict.toLowerCase()] ?? 0) -
                  (verdictRank[a.impact_verdict.toLowerCase()] ?? 0)
                )[0];

              if (!bestNews) return null;

              const verdict = bestNews.impact_verdict.toLowerCase();
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
              onClick={handleAnalyzeClick}
              disabled={loading}
              aria-label={`View analysis for ${stock.ticker}`}
            >
              {loading ? <Spinner animation="border" size="sm" /> : "Analysis"}
            </Button>
          </div>
        </td>
      </tr>

      {/* Modal is unchanged — you can keep it as-is */}
    </>
  );
};

export default PreMarketStockRow;
