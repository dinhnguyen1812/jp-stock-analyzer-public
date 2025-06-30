import React, { useState, useEffect } from "react";
import { Container, Button, Spinner, Form, InputGroup, Row, Col } from "react-bootstrap";
import ScanForm from "../components/shortterm/ScanForm";
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
  const [priceThreshold, setPriceThreshold] = useState(300.0);
  const [fromPage, setFromPage] = useState(1);
  const [toPage, setToPage] = useState(1);

  const [stocks, setStocks] = useState<VolumeSurgeStock[]>([]);
  const [loadingScan, setLoadingScan] = useState(false);
  const [loadingFetch, setLoadingFetch] = useState(false);

  const [tickerInput, setTickerInput] = useState("");
  const [showIntradayModal, setShowIntradayModal] = useState(false);
  const [intradayAnalysis, setIntradayAnalysis] = useState<any | null>(null);
  const [targetTicker, setTargetTicker] = useState<string>("");

  // New loading state for Analyze button
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
    } catch (err) {
      alert("Failed to analyze ticker.");
    } finally {
      setLoadingAnalyze(false);
    }
  };

  // Trigger scan only
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
        fromPage={fromPage}
        toPage={toPage}
        loading={loadingScan}
        onSurgeThresholdChange={setSurgeThreshold}
        onPriceThresholdChange={setPriceThreshold}
        onFromPageChange={setFromPage}
        onToPageChange={setToPage}
        onScan={handleScan}
      />

      <Row className="mb-3 align-items-center">
        <Col xs="auto">
          <Button onClick={handleFetchResults} disabled={loadingFetch}>
            {loadingFetch ? <Spinner animation="border" size="sm" /> : "Fetch Volume Surge Stocks"}
          </Button>
        </Col>

        <Col xs="auto">
          <InputGroup style={{ minWidth: 250 }}>
            <Form.Control
              placeholder="Enter ticker"
              value={tickerInput}
              onChange={(e) => setTickerInput(e.target.value.toUpperCase())}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  handleAnalyzeTicker(tickerInput);
                }
              }}
              aria-label="Ticker input"
              disabled={loadingAnalyze}
            />
            <Button
              variant="primary"
              onClick={() => handleAnalyzeTicker(tickerInput)}
              disabled={loadingAnalyze}
            >
              {loadingAnalyze ? (
                <>
                  <Spinner animation="border" size="sm" role="status" aria-hidden="true" />
                  {" "}Analyzing...
                </>
              ) : (
                "Analyze"
              )}
            </Button>
          </InputGroup>
        </Col>
      </Row>

      {/* Render the analysis modal */}
      <IntradayAnalysisModal
        show={showIntradayModal}
        onHide={() => setShowIntradayModal(false)}
        analysis={intradayAnalysis}
        ticker={targetTicker}
      />

      {stocks.length > 0 && <StockTable stocks={stocks} />}
    </Container>
  );
};

export default ShortTermPage;
