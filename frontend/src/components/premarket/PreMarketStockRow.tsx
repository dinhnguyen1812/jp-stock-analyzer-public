// components/premarket/PreMarketStockRow.tsx
import React, { useState, useCallback, useEffect } from "react";
import { Badge, Button, Spinner } from "react-bootstrap";
import { formatDistance } from "date-fns";
import MiniCandleChart from "./MiniPriceChart";
import PreMarketStockModal from "./PreMarketStockModal";
import SpikeScoreBreakdown from "./SpikeScoreBreakdown";
import type { SavedAnalysis } from "./types";
import type { VolumeSurgeStock } from "../../types";
import { fetchSavedPremarketAnalysis, starStock, unstarStock, watchStock, unwatchStock, analyzeSingleTicker } from "../../api";
import PromisingScoreBadge from "./PromisingScoreBadge";
import TopNewsVerdictBadge from "./TopNewsVerdictBadge";
import HighestImpactBadge from "./HighestImpactBadge";

interface Props {
  stock: VolumeSurgeStock & {
    recent_prices?: any[];
    spike_info?: any[];
    highest_impact_keyword?: string;
    highest_impact_rank?: string;
    model?: string;
    promising_score?: number;
    news_score?: number;
    recommendation?: string | null;
    starred?: boolean;
    watched?: boolean;
    detected_at: string;
    note?: string;
  };
  latestDetectedAt: string;
  latestThresholdDate: Date | null;
  onStarToggle: (ticker: string, starred: boolean) => void;
  onWatchToggle: (ticker: string, watched: boolean) => void;
  onNoteChange: (ticker: string, newNote: string) => void;
}

const PreMarketStockRow: React.FC<Props> = ({
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
  const [isSaving, setIsSaving] = useState(false);

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
      const newStarred = !stock.starred;
      if (newStarred) await starStock(stock.ticker);
      else await unstarStock(stock.ticker);
      onStarToggle(stock.ticker, newStarred);
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
      const newWatched = !stock.watched;
      if (newWatched) await watchStock(stock.ticker);
      else await unwatchStock(stock.ticker);
      onWatchToggle(stock.ticker, newWatched);
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
  
  const bgColor = !!stock.starred ? "#fff8dc" : undefined;

  const [loadingTickers, setLoadingTickers] = useState<Record<string, boolean>>({});

  return (
    <>
      <tr>
        <td className="align-middle small" style={{ maxWidth: "160px", whiteSpace: "pre-wrap", backgroundColor: bgColor }}>
          <textarea
            value={noteValue}
            onChange={(e) => setNoteValue(e.target.value)}
            onBlur={handleBlur}
            rows={7}
            style={{ width: "100%", fontSize: "0.75rem" }}
          />
        </td>

        <td className="text-center align-middle" style={{ width: 40, backgroundColor: bgColor }}>
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
                    textShadow: stock.starred ? "0 0 2px #ffc107, 0 0 4px #ffc107" : "none",
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
                    textShadow: stock.watched ? "0 0 2px #ffc107, 0 0 4px #ffc107" : "none",
                  }}
                  aria-hidden="true"
                >
                  ♥
                </span>
              )}
            </Button>
          </div>
        </td>

        <td className="align-middle text-center" style={{ backgroundColor: bgColor }}>
          <div>
            <a
              href={`https://kabutan.jp/stock/chart?code=${stock.ticker}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              {stock.ticker}
            </a>
          </div>
          <div>{stock.name}</div>
          <hr style={{ margin: "2px 0", borderTop: "1px solid #0d6efd" }} />
          <div>{stock.current_price.toFixed(2)}</div>
          <div>(
            {stock.price_change >= 0 ? `+${stock.price_change.toFixed(2)}` : stock.price_change.toFixed(2)}
          )</div>
        </td>

        <td className="align-middle text-start" style={{ minWidth: 120, maxWidth: 160 }}>
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

        <td className="align-middle text-center">
          {/* Spike Breakdown */}
          <SpikeScoreBreakdown spikeInfo={stock.spike_info?.[0]} />
        </td>

        <td className="align-middle text-center">
          {stock.highest_impact_rank && (
            <div className="d-flex justify-content-center mb-2">
              <HighestImpactBadge
                keyword={stock.highest_impact_keyword}
                rank={stock.highest_impact_rank}
                newsScore={stock.news_score}
              />
            </div>
          )}
          {stock.model && (
            <span
              className={`badge ${
                stock.model === "gpt-4o" ? "bg-primary" : "bg-success"
              }`}
              style={{ fontSize: "0.7rem" }}
            >
              {stock.model}
            </span>
          )}
        </td>

        <td className="align-middle text-center">
          <div className="d-flex flex-column align-items-center justify-content-center gap-2">
            <PromisingScoreBadge score={stock.promising_score} />
            <TopNewsVerdictBadge topNews={stock.top_news} latestThresholdDate={latestThresholdDate} />
            <div className="d-flex justify-content-center">
              <Button
                variant="outline-secondary"
                size="sm"
                onClick={handleAnalysisClick}
                disabled={loading}
                style={{ minWidth: 90, fontSize: "0.75rem", padding: "0.25rem 0.5rem" }}
              >
                {loading ? <Spinner animation="border" size="sm" /> : "Analysis"}
              </Button>
            </div>
            {/* Extra Analyze button */}
            <div className="mt-1 d-flex justify-content-center">
              <Button
                variant="info"
                size="sm"
                disabled={loadingTickers[stock.ticker]}
                onClick={async () => {
                  try {
                    setLoadingTickers(prev => ({ ...prev, [stock.ticker]: true }));
                    const res = await analyzeSingleTicker(stock.ticker);
                    console.log(res.message || `Analyzed ${stock.ticker}`);
                  } catch (err: any) {
                    console.error(err.message || `Failed to analyze ${stock.ticker}`);
                  } finally {
                    setLoadingTickers(prev => ({ ...prev, [stock.ticker]: false }));
                  }
                }}
                style={{ fontSize: "0.7rem", padding: "0.2rem 0.4rem", minWidth: "60px" }}
              >
                {loadingTickers[stock.ticker] ? (
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
            </div>

          </div>
        </td>

        <td className="align-middle text-center">
          <div>{stock.volume_rate.toFixed(2)}</div>
          <div>{stock.money_flow_rate.toFixed(2)}</div>
        </td>

        <td className="align-middle text-center">
          <div>{stock.current_volume.toLocaleString()}</div>
          <div>{stock.avg_volume_5d.toLocaleString()}</div>
        </td>

        <td className="align-middle text-center">
          <span
            style={{ color: isOld ? "#999" : undefined, fontStyle: isOld ? "italic" : undefined }}
            title={new Date(stock.detected_at + "Z").toLocaleString()}
          >
            {formatDistance(new Date(stock.detected_at + "Z"), new Date(), { addSuffix: true })}
          </span>
        </td>
      </tr>

      <PreMarketStockModal
        stockTicker={stock.ticker}
        show={showModal}
        onClose={() => setShowModal(false)}
        analysis={analysis}
        error={error}
        latestThresholdDate={latestThresholdDate}
        onNoteChange={onNoteChange}
        noteValue={noteValue}
        setNoteValue={setNoteValue}
        isSaving={isSaving}
      />
    </>
  );
};

export default PreMarketStockRow;
