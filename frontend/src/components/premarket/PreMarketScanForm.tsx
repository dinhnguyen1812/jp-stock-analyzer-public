import React from "react";
import { Form, Button, Spinner, Row, Col, InputGroup, Card } from "react-bootstrap";

interface PreMarketScanFormProps {
  surgeThreshold: number;
  priceThreshold: number;
  fromPage: number;
  toPage: number;
  loading: boolean;
  loadingNewsSignals: boolean;
  loadingSpikeScan: boolean;
  autoScanEnabled: boolean;
  onSurgeThresholdChange: (value: number) => void;
  onPriceThresholdChange: (value: number) => void;
  onFromPageChange: (value: number) => void;
  onToPageChange: (value: number) => void;
  onScan: () => void;
  onFetchNewsSignals: () => void;
  onScanSpike: () => void;
}

const PreMarketScanForm: React.FC<PreMarketScanFormProps> = ({
  surgeThreshold,
  priceThreshold,
  fromPage,
  toPage,
  loading,
  loadingNewsSignals,
  loadingSpikeScan,
  autoScanEnabled,
  onSurgeThresholdChange,
  onPriceThresholdChange,
  onFromPageChange,
  onToPageChange,
  onScan,
  onFetchNewsSignals,
  onScanSpike,
}) => {
  return (
    <Card className="mb-3 py-2 px-2 shadow-sm">
      <Card.Body className="py-2 px-1">
        <Form>
          <Row
            className="align-items-center g-2 flex-nowrap"
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
                {loading ? <Spinner animation="border" /> : "Scan VS"}
              </Button>
            </Col>
          </Row>
        </Form>
      </Card.Body>
    </Card>
  );
};

export default PreMarketScanForm;
