import React, { useState, useEffect } from "react";
import { Container } from "react-bootstrap";
import ScanForm from "../components/shortterm/ScanForm";
import StockTable from "../components/shortterm/StockTable";
import type { VolumeSurgeStock } from "../types";
import { triggerVolumeScan, fetchRecentVolumeSurges } from "../api";
import { Button, Spinner } from "react-bootstrap";

const ShortTermPage: React.FC = () => {
  useEffect(() => {
    document.title = "Volume Surge Scanner";
  }, []);

  const [surgeThreshold, setSurgeThreshold] = useState(2.0);
  const [priceThreshold, setPriceThreshold] = useState(300.0);
  const [pages, setPages] = useState(1);
  const [stocks, setStocks] = useState<VolumeSurgeStock[]>([]);
  const [loadingScan, setLoadingScan] = useState(false);
  const [loadingFetch, setLoadingFetch] = useState(false);

  // Trigger scan only
  const handleScan = async () => {
    setLoadingScan(true);
    try {
      await triggerVolumeScan(surgeThreshold, priceThreshold, pages);
      await handleFetchResults();
      alert("Scan triggered successfully.");
    } catch (error) {
      console.error(error);
      alert("Failed to trigger scan.");
    } finally {
      setLoadingScan(false);
    }
  };

  // Fetch saved volume surge results only
  const handleFetchResults = async () => {
    setLoadingFetch(true);
    try {
      const data = await fetchRecentVolumeSurges();
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
      <ScanForm
        surgeThreshold={surgeThreshold}
        priceThreshold={priceThreshold}
        pages={pages}
        loading={loadingScan}
        onSurgeThresholdChange={setSurgeThreshold}
        onPriceThresholdChange={setPriceThreshold}
        onPagesChange={setPages}
        onScan={handleScan}
      />

      <div className="mb-3">
        <Button onClick={handleFetchResults} disabled={loadingFetch}>
          {loadingFetch ? <Spinner animation="border" size="sm" /> : "Fetch Volume Surge Stocks"}
        </Button>
      </div>

      {stocks.length > 0 && <StockTable stocks={stocks} />}
    </Container>
  );
};

export default ShortTermPage;