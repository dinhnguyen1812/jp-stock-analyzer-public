import React from "react";
import { Form, Button, Spinner } from "react-bootstrap";

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
    <Form className="mb-4">
      <Form.Group controlId="surgeThreshold" className="mb-2">
        <Form.Label>Surge Threshold (x)</Form.Label>
        <Form.Control
          type="number"
          step="0.1"
          value={surgeThreshold}
          onChange={(e) => onSurgeThresholdChange(parseFloat(e.target.value))}
          disabled={loading}
        />
      </Form.Group>
      <Form.Group controlId="priceThreshold" className="mb-2">
        <Form.Label>Price Threshold (¥)</Form.Label>
        <Form.Control
          type="number"
          value={priceThreshold}
          onChange={(e) => onPriceThresholdChange(parseFloat(e.target.value))}
          disabled={loading}
        />
      </Form.Group>
      <Form.Group controlId="pages" className="mb-2">
        <Form.Label>Pages to Scan</Form.Label>
        <Form.Control
          type="number"
          value={pages}
          onChange={(e) => onPagesChange(Number(e.target.value) || 1)}
          disabled={loading}
          min={1}
        />
      </Form.Group>
      <Button onClick={onScan} disabled={loading}>
        {loading ? <Spinner animation="border" size="sm" /> : "Scan"}
      </Button>
    </Form>
  );
};

export default ScanForm;
