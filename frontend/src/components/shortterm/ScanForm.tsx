import React from "react";
import { Form, Button, Spinner, Row, Col, InputGroup, Card } from "react-bootstrap";
import type { ScanFormProps } from "../../types";

const ScanForm: React.FC<ScanFormProps> = ({
  surgeThreshold,
  priceThreshold,
  fromPage,
  toPage,
  loading,
  onSurgeThresholdChange,
  onPriceThresholdChange,
  onFromPageChange,
  onToPageChange,
  onScan,
}) => {
  return (
    <Card className="mb-4 shadow-sm">
      <Card.Body>
        <Form>
          <Row className="g-3 align-items-end">
            <Col md={3}>
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

            <Col md={3}>
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
              <Form.Label>From Page</Form.Label>
              <Form.Control
                type="number"
                min="1"
                value={fromPage}
                onChange={(e) => onFromPageChange(Number(e.target.value) || 1)}
                disabled={loading}
              />
            </Col>

            <Col md={2}>
              <Form.Label>To Page</Form.Label>
              <Form.Control
                type="number"
                min={fromPage}
                value={toPage}
                onChange={(e) => onToPageChange(Number(e.target.value) || fromPage)}
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
