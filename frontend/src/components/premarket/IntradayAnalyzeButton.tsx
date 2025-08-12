import React, { useState } from "react";
import {
  Button,
  Modal,
  Form,
  Spinner,
  Tabs,
  Tab,
  Alert,
} from "react-bootstrap";
import ReactMarkdown from "react-markdown";
import { analyzeLiveStock } from "../../api";
import "../../index.css";

type IntradayAnalyzeButtonProps = {
  ticker: string;
};

export default function IntradayAnalyzeButton({
  ticker,
}: IntradayAnalyzeButtonProps) {
  const [show, setShow] = useState(false);
  const [rawYahooJson, setRawYahooJson] = useState("{}");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<"input" | "result">("input");

  const url1 = `https://query1.finance.yahoo.com/v8/finance/chart/${ticker}.T?interval=1m&range=1d`;
  const url5 = `https://query1.finance.yahoo.com/v8/finance/chart/${ticker}.T?interval=5m&range=1d`;

  const handleAnalyze = async () => {
    setError(null);
    setResult(null);

    let parsedJson;
    try {
      parsedJson = JSON.parse(rawYahooJson);
    } catch {
      setError("Invalid JSON input");
      return;
    }

    setLoading(true);
    try {
      const res = await analyzeLiveStock(ticker, parsedJson);
      setResult(res);
      setActiveTab("result");
    } catch (e: any) {
      setError(e.message || "Failed to analyze intraday");
    } finally {
      setLoading(false);
    }
  };

  const formatJson = () => {
    try {
      const parsed = JSON.parse(rawYahooJson);
      setRawYahooJson(JSON.stringify(parsed, null, 2));
      setError(null);
    } catch {
      setError("Invalid JSON input - cannot format");
    }
  };

  return (
    <>
      <Button variant="outline-secondary" size="sm" onClick={() => setShow(true)}>
        Intraday Analyze
      </Button>

      <Modal
        show={show}
        onHide={() => setShow(false)}
        size="xl"
        centered
        dialogClassName="custom-modal-height"
      >
        <Modal.Header closeButton>
          <Modal.Title>Intraday Analyze for {ticker}</Modal.Title>
        </Modal.Header>
        <Modal.Body
          style={{ maxHeight: "80vh", overflowY: "auto", paddingBottom: 0 }}
        >
          <p>
            Links:{" "}
            <a href={url1} target="_blank" rel="noopener noreferrer">
              1m interval (1 day)
            </a>{" "}
            |{" "}
            <a href={url5} target="_blank" rel="noopener noreferrer">
              5m interval (1 day)
            </a>
          </p>

          {error && (
            <Alert
              variant="danger"
              onClose={() => setError(null)}
              dismissible
              className="mt-2"
            >
              {error}
            </Alert>
          )}

          <Tabs
            activeKey={activeTab}
            onSelect={(k) => setActiveTab(k as "input" | "result")}
            className="mb-3"
          >
            <Tab eventKey="input" title="Raw Yahoo JSON Input">
              <Form.Group controlId="rawYahooJsonTextarea" className="mb-3">
                <Form.Label>Input raw_yahoo_json</Form.Label>
                <Form.Control
                  as="textarea"
                  rows={12}
                  value={rawYahooJson}
                  onChange={(e) => setRawYahooJson(e.target.value)}
                  spellCheck={false}
                  style={{
                    fontFamily: "monospace",
                    fontSize: 14,
                    padding: 12,
                    lineHeight: 1.5,
                    resize: "vertical",
                  }}
                  disabled={loading}
                />
              </Form.Group>
              <Button
                variant="secondary"
                size="sm"
                onClick={formatJson}
                disabled={loading}
              >
                Format JSON
              </Button>
            </Tab>

            <Tab eventKey="result" title="Analysis Result" disabled={!result}>
              {loading && (
                <div className="text-center my-3">
                  <Spinner animation="border" /> Loading analysis...
                </div>
              )}

              {result?.analysis_raw && !loading && (
                <div
                  style={{
                    maxHeight: "60vh",
                    overflowY: "auto",
                    backgroundColor: "#f0f2f5",
                    padding: 16,
                    borderRadius: 6,
                    fontSize: 14,
                    whiteSpace: "pre-wrap",
                    lineHeight: 1.5,
                    userSelect: "text",
                  }}
                >
                  <ReactMarkdown>{result.analysis_raw}</ReactMarkdown>
                </div>
              )}

              {!result?.analysis_raw && result && !loading && (
                <pre
                  style={{
                    maxHeight: "60vh",
                    overflowY: "auto",
                    backgroundColor: "#f0f2f5",
                    padding: 16,
                    borderRadius: 6,
                    fontSize: 14,
                    userSelect: "text",
                  }}
                >
                  {JSON.stringify(result, null, 2)}
                </pre>
              )}
            </Tab>
          </Tabs>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShow(false)} disabled={loading}>
            Close
          </Button>
          <Button variant="primary" onClick={handleAnalyze} disabled={loading}>
            {loading ? (
              <>
                <Spinner animation="border" size="sm" /> Analyzing...
              </>
            ) : (
              "Intraday Analyze"
            )}
          </Button>
        </Modal.Footer>
      </Modal>
    </>
  );
}
