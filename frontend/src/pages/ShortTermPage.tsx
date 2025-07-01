import React, { useState, useEffect } from "react";
import { Container } from "react-bootstrap";
import ScanForm from "../components/shortterm/ScanForm";
import FetchAnalyzeCard from "../components/shortterm/FetchAnalyzeCard";
import StockTable from "../components/shortterm/StockTable";
import IntradayAnalysisModal from "../components/shortterm/TickerAnalysisResult";
import type { VolumeSurgeStock } from "../types";
import {
  triggerVolumeScan,
  fetchRecentVolumeSurges,
  fetchIntradayAnalysis
} from "../api";

const ShortTermPage: React.FC = () => {
  useEffect(() => {
    document.title = "Volume Surge Scanner";
  }, []);

  const [surgeThreshold, setSurgeThreshold] = useState(2.0);
  const [priceThreshold, setPriceThreshold] = useState(150.0);
  const [promisingScoreThreshold, setPromisingScoreThreshold] = useState(0);  // NEW

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
      // Pass promisingScoreThreshold as well
      const data = await fetchRecentVolumeSurges(
        surgeThreshold,
        priceThreshold,
        promisingScoreThreshold
      );
      setStocks(data);
    } catch (error) {
      console.error(error);
      alert("Failed to fetch volume surge stocks.");
    } finally {
      setLoadingFetch(false);
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
      />

      {/* FETCH & ANALYZE CARD */}
      <FetchAnalyzeCard
        surgeThreshold={surgeThreshold}
        priceThreshold={priceThreshold}
        promisingScoreThreshold={promisingScoreThreshold}         // NEW
        tickerInput={tickerInput}
        loadingFetch={loadingFetch}
        loadingAnalyze={loadingAnalyze}
        onSurgeThresholdChange={setSurgeThreshold}
        onPriceThresholdChange={setPriceThreshold}
        onPromisingScoreChange={setPromisingScoreThreshold}        // NEW
        onTickerInputChange={setTickerInput}
        onFetch={handleFetchResults}
        onAnalyze={handleAnalyzeTicker}
      />

      {/* MODAL */}
      <IntradayAnalysisModal
        show={showIntradayModal}
        onHide={() => setShowIntradayModal(false)}
        analysis={intradayAnalysis}
        ticker={targetTicker}
      />

      {/* TABLE */}
      {stocks.length > 0 && <StockTable stocks={stocks} />}
    </Container>
  );
};

export default ShortTermPage;
