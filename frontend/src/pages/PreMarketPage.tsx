import React, { useState } from "react";
import PreMarketScanForm from "../components/premarket/PreMarketScanForm";
import type { VolumeSurgeStock } from "../types";
import { scanPreMarketVolumeSurges } from "../api";

const PreMarketPage: React.FC = () => {
  const [surgeThreshold, setSurgeThreshold] = useState<number>(2.0);
  const [priceThreshold, setPriceThreshold] = useState<number>(300);
  const [fromPage, setFromPage] = useState<number>(1);
  const [toPage, setToPage] = useState<number>(1);
  const [loading, setLoading] = useState<boolean>(false);
  const [stocks, setStocks] = useState<VolumeSurgeStock[]>([]);

  const handleScan = async () => {
    setLoading(true);
    try {
      // Pass parameters as individual arguments (Option A)
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

  const handleStarToggle = (ticker: string, starred: boolean) => {
    setStocks((prev) =>
      prev.map((s) => (s.ticker === ticker ? { ...s, starred } : s))
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
        loadingNewsSignals={false} // placeholders, not used in premarket form
        loadingSpikeScan={false}
        autoScanEnabled={false}
        onSurgeThresholdChange={setSurgeThreshold}
        onPriceThresholdChange={setPriceThreshold}
        onFromPageChange={setFromPage}
        onToPageChange={setToPage}
        onScan={handleScan}
        onFetchNewsSignals={() => {}}
        onScanSpike={() => {}}
      />
    </div>
  );
};

export default PreMarketPage;
