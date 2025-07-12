import React, { useState } from "react";
import PreMarketScanForm from "../components/premarket/PreMarketScanForm";
import PreMarketStockTable from "../components/premarket/PreMarketStockTable";
import type { VolumeSurgeStock } from "../types";
import { scanPreMarketVolumeSurges, fetchAllAnalyses } from "../api";

const PreMarketPage: React.FC = () => {
  const [surgeThreshold, setSurgeThreshold] = useState<number>(2.0);
  const [priceThreshold, setPriceThreshold] = useState<number>(300);
  const [fromPage, setFromPage] = useState<number>(1);
  const [toPage, setToPage] = useState<number>(1);
  const [loading, setLoading] = useState<boolean>(false);
  const [loadingFetchAnalyzed, setLoadingFetchAnalyzed] = useState<boolean>(false);
  const [stocks, setStocks] = useState<VolumeSurgeStock[]>([]);
  const [analyzedResults, setAnalyzedResults] = useState<any[]>([]); // loosely typed for now

  const handleScan = async () => {
    setLoading(true);
    setAnalyzedResults([]); // clear previous analyzed results on new scan
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
      const result = await fetchAllAnalyses(); // call your /volume_surge/all_analyses API
      setAnalyzedResults(result);
      setStocks([]); // optionally clear the scan results to focus on analyzed results
    } catch (err) {
      console.error("Failed to fetch analyzed volume surges", err);
    } finally {
      setLoadingFetchAnalyzed(false);
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

  return (
    <div className="container mt-3">
      <h4 className="mb-3">📈 Pre-Market Volume Surge Scanner</h4>

      <PreMarketScanForm
        surgeThreshold={surgeThreshold}
        priceThreshold={priceThreshold}
        fromPage={fromPage}
        toPage={toPage}
        loading={loading}
        loadingNewsSignals={false}
        loadingSpikeScan={false}
        autoScanEnabled={false}
        onSurgeThresholdChange={setSurgeThreshold}
        onPriceThresholdChange={setPriceThreshold}
        onFromPageChange={setFromPage}
        onToPageChange={setToPage}
        onScan={handleScan}
        onFetchNewsSignals={() => {}}
        onScanSpike={() => {}}
        onFetchAnalyzed={handleFetchAnalyzed}
      />

      {/* Display scan results */}
      {loading && <p>Loading scan results...</p>}
      {stocks.length > 0 && (
        <>
          <h5 className="mt-4">Scan Results ({stocks.length})</h5>
          <PreMarketStockTable stocks={stocks} onStarToggle={handleStarToggle} />
        </>
      )}

      {/* Display analyzed results */}
      {loadingFetchAnalyzed && <p>Loading analyzed results...</p>}
      {analyzedResults.length > 0 && (
        <>
          <h5 className="mt-4">Analyzed Volume Surge Stocks ({analyzedResults.length})</h5>
          <PreMarketStockTable
            stocks={analyzedResults.map((item) => ({
              ...item.volume_info,
              // Map any needed fields from analysis result for PreMarketStockRow
            }))}
            onStarToggle={handleStarToggle}
          />
        </>
      )}
    </div>
  );
};

export default PreMarketPage;
