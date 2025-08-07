import React, { useState } from "react";
import PreMarketScanForm from "../components/premarket/PreMarketScanForm";
import PreMarketScanNewsCard from "../components/premarket/PreMarketScanNewsCard";
import PreMarketStockTable from "../components/premarket/PreMarketStockTable";
import PreMarketHoldingButton from "../components/premarket/PreMarketHoldingsButton";
import Rules from "../components/premarket/Rules";
import type { VolumeSurgeStock } from "../types";
import {
  scanPreMarketVolumeSurges,
  fetchAllAnalyses,
  analyzeAllStarredTickers,
  analyzeWatchList,
  analyzeSingleTicker,
} from "../api";

const PreMarketPage: React.FC = () => {
  const [surgeThreshold, setSurgeThreshold] = useState<number>(0);
  const [priceThreshold, setPriceThreshold] = useState<number>(0);
  const [detectedAtMaxDay, setDetectedAtMaxDay] = useState<number>(1);
  const [fromPage, setFromPage] = useState<number>(1);
  const [toPage, setToPage] = useState<number>(5);
  const [loading, setLoading] = useState<boolean>(false);
  const [loadingFetchAnalyzed, setLoadingFetchAnalyzed] = useState<boolean>(false);
  const [loadingAnalyzeStarred, setLoadingAnalyzeStarred] = useState<boolean>(false);
  const [loadingAnalyzeWatchList, setLoadingAnalyzeWatchList] = useState<boolean>(false);
  const [loadingAnalyze, setLoadingAnalyze] = useState<boolean>(false);
  const [starredOnly, setStarredOnly] = useState<boolean>(false);
  const [watchedOnly, setWatchedOnly] = useState<boolean>(false);
  const [stocks, setStocks] = useState<VolumeSurgeStock[]>([]);
  const [analyzedResults, setAnalyzedResults] = useState<any[]>([]);
  const [tickerInput, setTickerInput] = useState<string>("");

  const normalizeAnalyzedStock = (item: any) => {
    const vol = item?.volume_info;
    if (!vol || typeof vol !== "object" || !vol.ticker) {
      console.warn("Skipping invalid analyzed item:", item);
      return null;
    }

    return {
      ...vol,
      watchlist_recommendation: vol.watchlist_recommendation ?? undefined,
      promising_score:
        typeof vol.promising_score === "number" ? vol.promising_score : undefined,
      recommendation: vol.recommendation ?? undefined,
      starred: !!vol.starred,
      detected_at: vol.detected_at || new Date().toISOString(),
    };
  };

  const handleScan = async () => {
    setLoading(true);
    setAnalyzedResults([]);
    try {
      const result = await scanPreMarketVolumeSurges(
        surgeThreshold,
        priceThreshold,
        fromPage,
        toPage
      );
      setStocks(result);
    } catch (err) {
      console.error("Failed to scan premarket surges", err);
    } finally {
      setLoading(false);
    }
  };

  const handleFetchAnalyzed = async () => {
    setLoadingFetchAnalyzed(true);
    try {
      const result = await fetchAllAnalyses(surgeThreshold, priceThreshold, starredOnly, watchedOnly, detectedAtMaxDay);
      setAnalyzedResults(result);
      setStocks([]);
    } catch (err) {
      console.error("Failed to fetch analyzed volume surges", err);
    } finally {
      setLoadingFetchAnalyzed(false);
    }
  };

  const handleAnalyzeStarred = async () => {
    setLoadingAnalyzeStarred(true);
    try {
      const result = await analyzeAllStarredTickers();
      setAnalyzedResults(result);
      setStocks([]);
    } catch (err) {
      console.error("Failed to analyze starred tickers", err);
    } finally {
      setLoadingAnalyzeStarred(false);
    }
  };

  const handleAnalyzeWatchList = async () => {
    setLoadingAnalyzeWatchList(true);
    try {
      const result = await analyzeWatchList();
      setAnalyzedResults(result);
      setStocks([]);
    } catch (err) {
      console.error("Failed to analyze watchlist", err);
    } finally {
      setLoadingAnalyzeWatchList(false);
    }
  };

  const handleAnalyze = async (ticker: string) => {
    if (!ticker.trim()) return;
    setLoadingAnalyze(true);
    try {
      const result = await analyzeSingleTicker(ticker.trim().toUpperCase());
      setAnalyzedResults([result, ...analyzedResults]);
      setStocks([]);
      setTickerInput(""); // Clear input after analysis
    } catch (err) {
      console.error("Failed to analyze ticker", err);
    } finally {
      setLoadingAnalyze(false);
    }
  };

  const handleStarToggle = (ticker: string, starred: boolean) => {
    setStocks((prev) =>
      prev.map((s) => (s.ticker === ticker ? { ...s, starred } : s))
    );
    setAnalyzedResults((prev) =>
      prev.map((item) =>
        item.volume_info.ticker === ticker
          ? { ...item, volume_info: { ...item.volume_info, starred } }
          : item
      )
    );
  };

  const handleWatchToggle = (ticker: string, watched: boolean) => {
    setStocks((prev) =>
      prev.map((s) => (s.ticker === ticker ? { ...s, watched } : s))
    );
    setAnalyzedResults((prev) =>
      prev.map((item) =>
        item.volume_info.ticker === ticker
          ? { ...item, volume_info: { ...item.volume_info, watched } }
          : item
      )
    );
  };

  return (
    <div className="container mt-3">
      {/* Holdings Button */}
      <div className="d-flex justify-content-start align-items-center gap-2 mb-3">
        <PreMarketHoldingButton />
        <Rules />
      </div>

      {/* News Scanner Section */}
      <PreMarketScanNewsCard />

      {/* Scanner Form */}
      <PreMarketScanForm
        surgeThreshold={surgeThreshold}
        priceThreshold={priceThreshold}
        detectedAtMaxDay={detectedAtMaxDay}
        fromPage={fromPage}
        toPage={toPage}
        loading={loading}
        loadingNewsSignals={false}
        loadingSpikeScan={false}
        autoScanEnabled={false}
        starredOnly={starredOnly}
        watchedOnly={watchedOnly}
        loadingAnalyzeStarred={loadingAnalyzeStarred}
        loadingAnalyzeWatchList={loadingAnalyzeWatchList}
        loadingAnalyze={loadingAnalyze}
        onSurgeThresholdChange={setSurgeThreshold}
        onPriceThresholdChange={setPriceThreshold}
        onDetectedAtMaxDayChange={setDetectedAtMaxDay}
        onFromPageChange={setFromPage}
        onToPageChange={setToPage}
        onStarredOnlyChange={setStarredOnly}
        onWatchedOnlyChange={setWatchedOnly}
        onScan={handleScan}
        onFetchNewsSignals={() => { } }
        onScanSpike={() => { } }
        onFetchAnalyzed={handleFetchAnalyzed}
        onAnalyzeStarred={handleAnalyzeStarred}
        onAnalyzeWatchList={handleAnalyzeWatchList}
        onAnalyze={handleAnalyze}
      />

      {/* Scan Results */}
      {loading && <p>Loading scan results...</p>}
      {stocks.length > 0 && (
        <>
          <h5 className="mt-4">Scan Results ({stocks.length})</h5>
          <PreMarketStockTable stocks={stocks} onStarToggle={handleStarToggle} onWatchToggle={handleWatchToggle} />
        </>
      )}

      {/* Analyzed Results */}
      {loadingFetchAnalyzed && <p>Loading analyzed results...</p>}
      {analyzedResults.length > 0 && (
        <>
          <h5 className="mt-4">
            Analyzed Volume Surge Stocks ({analyzedResults.length})
          </h5>
          <PreMarketStockTable
            stocks={analyzedResults.map(normalizeAnalyzedStock).filter(Boolean)}
            onStarToggle={handleStarToggle}
            onWatchToggle={handleWatchToggle}
          />
        </>
      )}
    </div>
  );
};

export default PreMarketPage;
