import React from "react";
import { Card, Form, Row, Col, Button, InputGroup, Spinner } from "react-bootstrap";

interface FetchAnalyzeCardProps {
  surgeThreshold: number;
  priceThreshold: number;
  promisingScoreThreshold: number;
  tickerInput: string;
  loadingFetch: boolean;
  loadingAnalyze: boolean;
  starredOnly: boolean; // ⭐ New
  loadingAnalyzeStarred: boolean; // ⭐ loading state for that action
  onSurgeThresholdChange: (value: number) => void;
  onPriceThresholdChange: (value: number) => void;
  onPromisingScoreChange: (value: number) => void;
  onTickerInputChange: (value: string) => void;
  onFetch: () => void;
  onAnalyze: (ticker: string) => void;
  onStarredOnlyChange: (value: boolean) => void; // ⭐ New
  onAnalyzeStarred: () => void;  // ⭐ new prop for analyzing all starred
}

const FetchAnalyzeCard: React.FC<FetchAnalyzeCardProps> = ({
  surgeThreshold,
  priceThreshold,
  promisingScoreThreshold,
  tickerInput,
  loadingFetch,
  loadingAnalyze,
  starredOnly,
  loadingAnalyzeStarred,
  onSurgeThresholdChange,
  onPriceThresholdChange,
  onPromisingScoreChange,
  onTickerInputChange,
  onFetch,
  onAnalyze,
  onStarredOnlyChange,
  onAnalyzeStarred,
}) => {
  return (
    <Card className="mb-4 shadow-sm">
      <Card.Body>
        <Form>
          <Row className="align-items-center g-2" style={{ flexWrap: "nowrap" }}>
            <Col style={{ flexGrow: 1.2, minWidth: 90 }}>
              <InputGroup>
                <InputGroup.Text style={{ minWidth: 60, justifyContent: "center" }}>Surge ≥</InputGroup.Text>
                <Form.Control
                  type="number"
                  value={surgeThreshold}
                  onChange={(e) => onSurgeThresholdChange(Number(e.target.value))}
                  step={0.1}
                  disabled={loadingFetch}
                />
                <InputGroup.Text style={{ minWidth: 20 }}>x</InputGroup.Text>
              </InputGroup>
            </Col>

            <Col style={{ flexGrow: 1.0, minWidth: 90 }}>
              <InputGroup>
                <InputGroup.Text style={{ minWidth: 60, justifyContent: "center" }}>Price ≤</InputGroup.Text>
                <Form.Control
                  type="number"
                  value={priceThreshold}
                  onChange={(e) => onPriceThresholdChange(Number(e.target.value))}
                  step={10}
                  disabled={loadingFetch}
                />
                <InputGroup.Text style={{ minWidth: 20 }}>¥</InputGroup.Text>
              </InputGroup>
            </Col>

            <Col style={{ flexGrow: 1.2, minWidth: 180 }}>
              <InputGroup>
                <InputGroup.Text style={{ minWidth: 90, justifyContent: "center" }}>Promising ≥</InputGroup.Text>
                <Form.Control
                  type="number"
                  value={promisingScoreThreshold}
                  onChange={(e) => onPromisingScoreChange(Number(e.target.value))}
                  step={1}
                  min={0}
                  max={100}
                  disabled={loadingFetch}
                />
                <InputGroup.Text style={{ minWidth: 30 }}>pts</InputGroup.Text>
              </InputGroup>
            </Col>

            {/* ⭐ Starred Only Checkbox */}
            <Col style={{ flexGrow: 0.1, minWidth: 50 }}>
              <Form.Check
                type="checkbox"
                label="⭐"
                checked={starredOnly}
                onChange={(e) => onStarredOnlyChange(e.target.checked)}
                disabled={loadingFetch}
              />
            </Col>

            <Col style={{ flexGrow: 0.6, minWidth: 80 }}>
              <Button
                variant="primary"
                onClick={onFetch}
                disabled={loadingFetch}
                className="w-100"
                style={{ whiteSpace: "nowrap" }}
              >
                {loadingFetch ? (
                  <Spinner animation="border" size="sm" />
                ) : (
                  "Fetch"
                )}
              </Button>
            </Col>
            <Col xs="auto">
              <Button
                variant="warning"
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

            <Col style={{ flexGrow: 1, minWidth: 200 }}>
              <InputGroup>
                <Form.Control
                  placeholder="Ticker"
                  value={tickerInput}
                  onChange={(e) => onTickerInputChange(e.target.value.toUpperCase())}
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
                  disabled={loadingAnalyze}
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
        </Form>
      </Card.Body>
    </Card>
  );
};

export default FetchAnalyzeCard;
