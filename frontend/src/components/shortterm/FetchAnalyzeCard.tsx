import React from "react";
import { Card, Form, Row, Col, Button, InputGroup, Spinner } from "react-bootstrap";

interface FetchAnalyzeCardProps {
  surgeThreshold: number;
  priceThreshold: number;
  promisingScoreThreshold: number;
  tickerInput: string;
  loadingFetch: boolean;
  loadingAnalyze: boolean;
  onSurgeThresholdChange: (value: number) => void;
  onPriceThresholdChange: (value: number) => void;
  onPromisingScoreChange: (value: number) => void;
  onTickerInputChange: (value: string) => void;
  onFetch: () => void;
  onAnalyze: (ticker: string) => void;
}

const FetchAnalyzeCard: React.FC<FetchAnalyzeCardProps> = ({
  surgeThreshold,
  priceThreshold,
  promisingScoreThreshold,
  tickerInput,
  loadingFetch,
  loadingAnalyze,
  onSurgeThresholdChange,
  onPriceThresholdChange,
  onPromisingScoreChange,
  onTickerInputChange,
  onFetch,
  onAnalyze,
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

            <Col style={{ flexGrow: 1, minWidth: 110 }}>
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

            <Col style={{ flexGrow: 2, minWidth: 200 }}>
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
