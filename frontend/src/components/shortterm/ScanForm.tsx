import React from "react";
import { Form, Button, Spinner, Row, Col, InputGroup, Card } from "react-bootstrap";

interface ScanFormProps {
  surgeThreshold: number;
  priceThreshold: number;
  pages: number;
  loading: boolean;
  onSurgeThresholdChange: (value: number) => void;
  onPriceThresholdChange: (value: number) => void;
  onPagesChange: (value: number) => void;
  onScan: () => void;
}

const ScanForm: React.FC<ScanFormProps> = ({
  surgeThreshold,
  priceThreshold,
  pages,
  loading,
  onSurgeThresholdChange,
  onPriceThresholdChange,
  onPagesChange,
  onScan,
}) => {
  return (
    <Card className="mb-4 shadow-sm">
      <Card.Body>
        <Form>
          <Row className="g-3 align-items-end">
            <Col md={4}>
              <Form.Label>Surge Threshold</Form.Label>
              <InputGroup>
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

            <Col md={4}>
              <Form.Label>Price Threshold</Form.Label>
              <InputGroup>
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

            <Col md={2}>
              <Form.Label>Pages</Form.Label>
              <Form.Control
                type="number"
                min="1"
                value={pages}
                onChange={(e) => onPagesChange(Number(e.target.value) || 1)}
                disabled={loading}
              />
            </Col>

            <Col md={2}>
              <Button
                variant="primary"
                className="w-100"
                onClick={onScan}
                disabled={loading}
              >
                {loading ? <Spinner animation="border" size="sm" /> : "Scan"}
              </Button>
            </Col>
          </Row>
        </Form>
      </Card.Body>
    </Card>
  );
};

export default ScanForm;
