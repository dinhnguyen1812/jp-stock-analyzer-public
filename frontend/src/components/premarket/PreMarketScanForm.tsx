import React, { useState } from "react";
import { Form, Button, Spinner, Row, Col, InputGroup, Card } from "react-bootstrap";

interface PreMarketScanFormProps {
  surgeThreshold: number;
  priceThreshold: number;
  detectedAtMaxDay: number;
  fromPage: number;
  toPage: number;
  starredOnly: boolean;
  loading: boolean;
  loadingNewsSignals: boolean;
  loadingSpikeScan: boolean;
  autoScanEnabled: boolean;
  onSurgeThresholdChange: (value: number) => void;
  onPriceThresholdChange: (value: number) => void;
  onDetectedAtMaxDayChange: (value: number) => void;
  onFromPageChange: (value: number) => void;
  onToPageChange: (value: number) => void;
  onStarredOnlyChange: (checked: boolean) => void;
  onScan: () => void;
  onFetchNewsSignals: () => void;
  onScanSpike: () => void;
  onFetchAnalyzed: () => void;
  onAnalyzeStarred: () => void;
  loadingAnalyzeStarred: boolean;

  // New props for single ticker analyze
  onAnalyze: (ticker: string) => void;
  loadingAnalyze: boolean;
}

const PreMarketScanForm: React.FC<PreMarketScanFormProps> = ({
  surgeThreshold,
  priceThreshold,
  detectedAtMaxDay,
  fromPage,
  toPage,
  starredOnly,
  loading,
  onSurgeThresholdChange,
  onPriceThresholdChange,
  onDetectedAtMaxDayChange,
  onFromPageChange,
  onToPageChange,
  onStarredOnlyChange,
  onScan,
  onFetchAnalyzed,
  onAnalyzeStarred,
  loadingAnalyzeStarred,
  onAnalyze,
  loadingAnalyze,
}) => {
  // Local state for the ticker input
  const [tickerInput, setTickerInput] = useState("");

  const handleTickerChange = (val: string) => {
    setTickerInput(val.toUpperCase());
  };

  return (
    <Card className="mb-3 py-2 px-3 shadow-sm">
      <Card.Body className="py-2 px-1">
        <Form>
          <Row className="align-items-center mb-3">
            <Col>
              <h5 className="mb-0">📈 Pre-Market Volume Surge Scanner</h5>
            </Col>

            <Col xs="auto" className="ms-auto">
              <InputGroup>
                <Form.Control
                  placeholder="Ticker"
                  value={tickerInput}
                  onChange={(e) => handleTickerChange(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      onAnalyze(tickerInput);
                    }
                  }}
                  disabled={loadingAnalyze}
                />
                <Button
                  variant="primary"
                  onClick={() => onAnalyze(tickerInput)}
                  disabled={loadingAnalyze || tickerInput.trim() === ""}
                  style={{ whiteSpace: "nowrap" }}
                >
                  {loadingAnalyze ? (
                    <>
                      <Spinner animation="border" size="sm" role="status" aria-hidden="true" />
                      {" "}Analyze...
                    </>
                  ) : (
                    "Analyze"
                  )}
                </Button>
              </InputGroup>
            </Col>
          </Row>

          <Row
            className="align-items-center g-2"
            style={{ overflowX: "auto", fontSize: "0.85rem" }}
          >
            <Col style={{ minWidth: 190 }}>
              <InputGroup>
                <InputGroup.Text>Surge ≥</InputGroup.Text>
                <Form.Control
                  type="number"
                  step="0.1"
                  min="0"
                  value={surgeThreshold}
                  onChange={(e) => onSurgeThresholdChange(parseFloat(e.target.value))}
                  disabled={loading}
                />
                <InputGroup.Text>x</InputGroup.Text>
              </InputGroup>
            </Col>

            <Col style={{ minWidth: 195 }}>
              <InputGroup>
                <InputGroup.Text>Price ≤</InputGroup.Text>
                <Form.Control
                  type="number"
                  min="0"
                  value={priceThreshold}
                  onChange={(e) => onPriceThresholdChange(parseFloat(e.target.value))}
                  disabled={loading}
                />
                <InputGroup.Text>¥</InputGroup.Text>
              </InputGroup>
            </Col>

            <Col style={{ minWidth: 125 }}>
              <InputGroup>
                <InputGroup.Text>From</InputGroup.Text>
                <Form.Control
                  type="number"
                  min="1"
                  value={fromPage}
                  onChange={(e) => onFromPageChange(Number(e.target.value) || 1)}
                  disabled={loading}
                />
              </InputGroup>
            </Col>

            <Col style={{ minWidth: 110 }}>
              <InputGroup>
                <InputGroup.Text>To</InputGroup.Text>
                <Form.Control
                  type="number"
                  min={fromPage}
                  value={toPage}
                  onChange={(e) => onToPageChange(Number(e.target.value) || fromPage)}
                  disabled={loading}
                />
              </InputGroup>
            </Col>

            <Col style={{ minWidth: 95 }}>
              <Button
                variant="primary"
                className="w-100"
                onClick={onScan}
                disabled={loading}
              >
                {loading && <Spinner animation="border" size="sm" className="me-2" />}
                Scan VS
              </Button>
            </Col>

            <Col style={{ flexGrow: 0.1, minWidth: 60 }}>
              <Form.Check
                type="checkbox"
                label="⭐"
                checked={starredOnly}
                onChange={(e) => onStarredOnlyChange(e.target.checked)}
                disabled={loading}
              />
            </Col>

            <Col style={{ minWidth: 180 }}>
              <InputGroup>
                <Form.Control
                  type="number"
                  min="0"
                  value={detectedAtMaxDay}
                  onChange={(e) => onDetectedAtMaxDayChange(parseFloat(e.target.value))}
                  disabled={loading}
                />
                <InputGroup.Text>days before</InputGroup.Text>
              </InputGroup>
            </Col>

            <Col style={{ minWidth: 135 }}>
              <Button
                variant="success"
                className="w-100"
                onClick={onFetchAnalyzed}
                disabled={loading}
              >
                {loading && <Spinner animation="border" size="sm" className="me-2" />}
                Fetch
              </Button>
            </Col>

            <Col style={{ minWidth: 150 }}>
              <Button
                variant="warning"
                className="w-100"
                onClick={onAnalyzeStarred}
                disabled={loadingAnalyzeStarred}
                title="Analyze all starred stocks"
              >
                {loadingAnalyzeStarred ? (
                  <>
                    <Spinner animation="border" size="sm" /> Analyzing Starred...
                  </>
                ) : (
                  "Analyze Starred"
                )}
              </Button>
            </Col>
          </Row>
        </Form>
      </Card.Body>
    </Card>
  );
};

export default PreMarketScanForm;
