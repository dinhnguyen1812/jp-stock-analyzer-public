import React from "react";
import { Modal, Row, Col, Badge } from "react-bootstrap";

interface IntradayAnalysisModalProps {
  show: boolean;
  onHide: () => void;
  analysis: any; // You can replace `any` with a type if desired
  ticker: string;
}

const recommendationVariant = (rec?: string) => {
  switch (rec) {
    case "Buy":
      return "success";
    case "Sell":
      return "danger";
    default:
      return "secondary";
  }
};

const IntradayAnalysisModal: React.FC<IntradayAnalysisModalProps> = ({
  show,
  onHide,
  analysis,
  ticker,
}) => {
  if (!analysis) return null;

  return (
    <Modal size="lg" show={show} onHide={onHide} scrollable>
      <Modal.Header closeButton>
        <Modal.Title>Intraday Analysis for {ticker}</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <Row>
          <Col md={6}>
            <h5>Volume Info</h5>
            <ul>
              <li>Name: {analysis.volume_info.name}</li>
              <li>Current Price: {analysis.volume_info.current_price.toFixed(2)}</li>
              <li>Price Change: {analysis.volume_info.price_change.toFixed(2)}</li>
              <li>Volume Rate: {analysis.volume_info.volume_rate.toFixed(2)}</li>
              <li>Money Flow Rate: {analysis.volume_info.money_flow_rate.toFixed(2)}</li>
              <li>Current Volume: {analysis.volume_info.current_volume.toLocaleString()}</li>
              <li>Avg Volume (5d): {analysis.volume_info.avg_volume_5d.toLocaleString()}</li>
              <li>Detected At: {new Date(analysis.volume_info.detected_at).toLocaleString()}</li>
            </ul>
          </Col>

          <Col md={6}>
            <h5>Technical Signals</h5>
            <ul>
              <li>Candle: {analysis.analysis_signal?.candle_pattern ?? "None"}</li>
              <li>Breakout: {analysis.analysis_signal?.breakout_detected ? "Yes" : "No"}</li>
              <li>RSI: {analysis.analysis_signal?.rsi}</li>
              <li>MACD: Line={analysis.analysis_signal?.macd_line}, Signal={analysis.analysis_signal?.macd_signal}, Hist={analysis.analysis_signal?.macd_hist}</li>
              <li>SMA50: {analysis.analysis_signal?.sma_50}, EMA20: {analysis.analysis_signal?.ema_20}</li>
              <li>W-Shape: {analysis.analysis_signal?.w_shape ? "Yes" : "No"}</li>
            </ul>
          </Col>
        </Row>

        <h5>Summary</h5>
        <p><strong>Recommendation: </strong>
          <Badge bg={recommendationVariant(analysis.volume_info.recommendation)}>
            {analysis.volume_info.recommendation}
          </Badge>
        </p>
        <p><strong>Promising Score: </strong>{analysis.volume_info.promising_score}</p>

        <h6>GPT Reasoning</h6>
        <p style={{ whiteSpace: "pre-wrap" }}>{analysis.volume_info.reasoning}</p>

        <h6>Top News</h6>
        <ul>
          {analysis.top_news?.map((newsItem: any, i: number) => (
            <li key={i}>
              <a href={newsItem.url} target="_blank" rel="noopener noreferrer">{newsItem.headline}</a>
              <br />
              <small className="text-muted">
                [{newsItem.category}] {new Date(newsItem.published_at).toLocaleString()}
              </small>
            </li>
          ))}
        </ul>
      </Modal.Body>
    </Modal>
  );
};

export default IntradayAnalysisModal;
