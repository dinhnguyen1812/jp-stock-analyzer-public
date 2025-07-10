import React, { useState, useEffect } from "react";
import { Container } from "react-bootstrap";
import ScanForm from "../components/shortterm/ScanForm";
import FetchAnalyzeCard from "../components/shortterm/FetchAnalyzeCard";
import StockTable from "../components/shortterm/StockTable";
import IntradayAnalysisModal from "../components/shortterm/TickerAnalysisResult";
import NewsImpactModal from "../components/shortterm/NewsImpactModal";
import HoldingsCard from "../components/shortterm/HoldingsCard";
import ScanSpikeCard from "../components/shortterm/ScanSpikeCard";
import SpikeScanCard from "../components/shortterm/FetchSpikeCard";
import type { VolumeSurgeStock } from "../types";
import {
  triggerVolumeScan,
  fetchRecentVolumeSurges,
  fetchIntradayAnalysis,
  analyzeAllStarredStocks,
  fetchNewsSignalsWithImpacts,
  triggerVolumeSurgeFullScan,
} from "../api";

const ShortTermPage: React.FC = () => {
  useEffect(() => {
    document.title = "Volume Surge Scanner";
  }, []);

  const [surgeThreshold, setSurgeThreshold] = useState(1.5);
  const [priceThreshold, setPriceThreshold] = useState(300.0);
  const [promisingScoreThreshold, setPromisingScoreThreshold] = useState(30);
  const [starredOnly, setStarredOnly] = useState(false);

  const [fromPage, setFromPage] = useState(1);
  const [toPage, setToPage] = useState(5);

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

  const [loadingSpikeScan, setLoadingSpikeScan] = useState(false);
  const [spikeScanReport, setSpikeScanReport] = useState("");

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
      setShowNewsModal(true);
    } catch (error) {
      console.error("Failed to fetch news signals", error);
    } finally {
      setLoadingNewsSignals(false);
    }
  };

  const handleScanSpike = async () => {
    setLoadingSpikeScan(true);
    try {
      const result = await triggerVolumeSurgeFullScan(
        surgeThreshold,
        fromPage,
        toPage
      );
      setSpikeScanReport(result.report);
    } catch (err) {
      alert("Spike scan failed.");
    } finally {
      setLoadingSpikeScan(false);
    }
  };

  return (
    <Container className="py-4">
      {/* SCAN FORM + HOLDINGS */}
      <div className="d-flex align-items-center mb-3 gap-3">
        <div style={{ flex: 1, minWidth: 0 }}>
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
            onFetchNewsSignals={handleFetchNewsSignals}
            loadingNewsSignals={loadingNewsSignals}
            onScanSpike={handleScanSpike}
            loadingSpikeScan={loadingSpikeScan}
          />
        </div>
        <div style={{ width: "280px", minWidth: "280px" }}>
          <HoldingsCard />
        </div>
      </div>

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

      {/* SPIKE SCAN CARD (Below FetchAnalyzeCard) */}
      <SpikeScanCard />

      {/* MODALS */}
      <IntradayAnalysisModal
        show={showIntradayModal}
        onHide={() => setShowIntradayModal(false)}
        analysis={intradayAnalysis}
        ticker={targetTicker}
      />

      <NewsImpactModal
        show={showNewsModal}
        onHide={() => setShowNewsModal(false)}
        rawResponse={newsImpactResult?.raw_response || "(No data available)"}
      />

      {/* TABLE */}
      {stocks.length > 0 && (
        <StockTable stocks={stocks} onStarToggle={handleStarToggle} />
      )}

      {/* SPIKE SCAN RESULT (TEXT REPORT) */}
      {spikeScanReport && <ScanSpikeCard report={spikeScanReport} />}
    </Container>
  );
};

export default ShortTermPage;
