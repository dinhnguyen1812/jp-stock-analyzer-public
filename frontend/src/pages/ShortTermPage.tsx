import React, { useState, useEffect } from "react";
import { Container, Card } from "react-bootstrap";
import ScanForm from "../components/shortterm/ScanForm";
import FetchAnalyzeCard from "../components/shortterm/FetchAnalyzeCard";
import StockTable from "../components/shortterm/StockTable";
import IntradayAnalysisModal from "../components/shortterm/TickerAnalysisResult";
import NewsImpactModal from "../components/shortterm/NewsImpactModal";
import type { VolumeSurgeStock } from "../types";
import {
  triggerVolumeScan,
  fetchRecentVolumeSurges,
  fetchIntradayAnalysis,
  analyzeAllStarredStocks,
  fetchNewsSignalsWithImpacts,
} from "../api";

const ShortTermPage: React.FC = () => {
  useEffect(() => {
    document.title = "Volume Surge Scanner";
  }, []);

  const [surgeThreshold, setSurgeThreshold] = useState(2.0);
  const [priceThreshold, setPriceThreshold] = useState(150.0);
  const [promisingScoreThreshold, setPromisingScoreThreshold] = useState(0);
  const [starredOnly, setStarredOnly] = useState(false);

  const [fromPage, setFromPage] = useState(1);
  const [toPage, setToPage] = useState(1);

  const [stocks, setStocks] = useState<VolumeSurgeStock[]>([]);
  const [loadingScan, setLoadingScan] = useState(false);
  const [loadingFetch, setLoadingFetch] = useState(false);

  const [tickerInput, setTickerInput] = useState("");
  const [showIntradayModal, setShowIntradayModal] = useState(false);
  const [intradayAnalysis, setIntradayAnalysis] = useState<any | null>(null);
  const [targetTicker, setTargetTicker] = useState<string>("");

  const [loadingAnalyze, setLoadingAnalyze] = useState(false);
  const [loadingAnalyzeStarred, setLoadingAnalyzeStarred] = useState(false);
  const [starredAnalyzeResults, setStarredAnalyzeResults] = useState<any[]>([]);

  const [loadingNewsSignals, setLoadingNewsSignals] = useState(false);
  const [newsImpactResult, setNewsImpactResult] = useState<any | null>(null);

  const [showNewsModal, setShowNewsModal] = useState(false);

  const handleAnalyzeTicker = async (ticker: string) => {
    if (!ticker.trim()) {
      alert("Please enter a ticker.");
      return;
    }
    setLoadingAnalyze(true);
    try {
      const data = await fetchIntradayAnalysis(ticker.trim());
      setTargetTicker(ticker.trim());
      setIntradayAnalysis(data);
      setShowIntradayModal(true);
    } catch {
      alert("Failed to analyze ticker.");
    } finally {
      setLoadingAnalyze(false);
    }
  };

  const handleScan = async () => {
    setLoadingScan(true);
    try {
      await triggerVolumeScan(surgeThreshold, priceThreshold, fromPage, toPage);
      await handleFetchResults();
      alert("Scan triggered successfully.");
    } catch (error) {
      console.error(error);
      alert("Failed to trigger scan.");
    } finally {
      setLoadingScan(false);
    }
  };

  const handleFetchResults = async () => {
    setLoadingFetch(true);
    try {
      const data = await fetchRecentVolumeSurges(
        surgeThreshold,
        priceThreshold,
        promisingScoreThreshold,
        starredOnly
      );
      setStocks(data);
    } catch (error) {
      console.error(error);
      alert("Failed to fetch volume surge stocks.");
    } finally {
      setLoadingFetch(false);
    }
  };

  const handleStarToggle = (ticker: string, starred: boolean) => {
    setStocks((prevStocks) =>
      prevStocks.map((stock) =>
        stock.ticker === ticker ? { ...stock, starred } : stock
      )
    );
  };

  const handleAnalyzeStarred = async () => {
    setLoadingAnalyzeStarred(true);
    try {
      const results = await analyzeAllStarredStocks();
      setStarredAnalyzeResults(results);
      alert(`Analyzed ${results.length} starred stocks.`);
      await handleFetchResults();
    } catch (error) {
      console.error(error);
      alert("Failed to analyze starred stocks.");
    } finally {
      setLoadingAnalyzeStarred(false);
    }
  };

  const handleFetchNewsSignals = async () => {
    try {
      setLoadingNewsSignals(true);
      const result = await fetchNewsSignalsWithImpacts();
      setNewsImpactResult(result);
      setShowNewsModal(true); // 👉 Show modal after fetch
    } catch (error) {
      console.error("Failed to fetch news signals", error);
    } finally {
      setLoadingNewsSignals(false);
    }
  };


  return (
    <Container className="py-4">
      {/* SCAN CONTROL */}
      <ScanForm
        surgeThreshold={surgeThreshold}
        priceThreshold={priceThreshold}
        fromPage={fromPage}
        toPage={toPage}
        loading={loadingScan}
        onSurgeThresholdChange={setSurgeThreshold}
        onPriceThresholdChange={setPriceThreshold}
        onFromPageChange={setFromPage}
        onToPageChange={setToPage}
        onScan={handleScan}
        onFetchNewsSignals={handleFetchNewsSignals} // ✅ NEW
        loadingNewsSignals={loadingNewsSignals}     // ✅ NEW
      />

      {/* FETCH & ANALYZE CARD */}
      <FetchAnalyzeCard
        surgeThreshold={surgeThreshold}
        priceThreshold={priceThreshold}
        promisingScoreThreshold={promisingScoreThreshold}
        tickerInput={tickerInput}
        loadingFetch={loadingFetch}
        loadingAnalyze={loadingAnalyze}
        starredOnly={starredOnly}
        loadingAnalyzeStarred={loadingAnalyzeStarred}
        onSurgeThresholdChange={setSurgeThreshold}
        onPriceThresholdChange={setPriceThreshold}
        onPromisingScoreChange={setPromisingScoreThreshold}
        onTickerInputChange={setTickerInput}
        onFetch={handleFetchResults}
        onAnalyze={handleAnalyzeTicker}
        onStarredOnlyChange={setStarredOnly}
        onAnalyzeStarred={handleAnalyzeStarred}
      />

      {/* MODAL */}
      <IntradayAnalysisModal
        show={showIntradayModal}
        onHide={() => setShowIntradayModal(false)}
        analysis={intradayAnalysis}
        ticker={targetTicker}
      />

      {/* TABLE */}
      {stocks.length > 0 && (
        <StockTable stocks={stocks} onStarToggle={handleStarToggle} />
      )}

      {/* NEWS IMPACT RESULT MODAL */}
      <NewsImpactModal
        show={showNewsModal}
        onHide={() => setShowNewsModal(false)}
        rawResponse={newsImpactResult?.raw_response || "(No data available)"}
      />

    </Container>
  );
};

export default ShortTermPage;
