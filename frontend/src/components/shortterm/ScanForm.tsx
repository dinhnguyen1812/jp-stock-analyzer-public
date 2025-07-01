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
          <Row className="align-items-center g-3">
            <Col md={3}>
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

            <Col md={3}>
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

            <Col md={2}>
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

            <Col md={2}>
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
