// components/premarket/PreMarketStockModal.tsx
import React from "react";
import { Modal, Button, Tabs, Tab, Row, Col } from "react-bootstrap";
import MiniCandleChart from "./MiniPriceChart";
import IntradayAnalyzeTab from "./IntradayAnalyzeTab";
import type { SavedAnalysis } from "./types";
import { highlightKeywords, highlightRank } from "./highlightUtils";
import { formatDistance } from "date-fns";

interface Props {
  stockTicker: string;
  show: boolean;
  onClose: () => void;
  analysis: SavedAnalysis | null;
  error: string | null;
  latestThresholdDate: Date | null;
  onNoteChange: (ticker: string, newNote: string) => void;
  noteValue: string;
  isSaving: boolean;
  setNoteValue: (val: string) => void;
}

const PreMarketStockModal: React.FC<Props> = ({
  stockTicker,
  show,
  onClose,
  analysis,
  error,
  latestThresholdDate,
  onNoteChange,
  noteValue,
  isSaving,
  setNoteValue
}) => {
  return (
    <Modal size="xl" show={show} onHide={onClose} scrollable>
      <Modal.Header closeButton>
        <Modal.Title>Analysis for {stockTicker}</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <Tabs defaultActiveKey="volume" id="analysis-tabs" className="mb-3">
          <Tab eventKey="volume" title="Pre-market">
            {error && <p className="text-danger">{error}</p>}
            {!error && !analysis && <p>Loading analysis...</p>}
            {analysis && (
              <>
                <Row>
                  <Col md={4}>
                    <h5>Volume Info</h5>
                    <ul>
                      <li>Name: {analysis.volume_info.name}</li>
                      <li>Current Price: {analysis.volume_info.current_price.toFixed(2)}</li>
                      <li>Price Change: {analysis.volume_info.price_change.toFixed(2)}</li>
                      <li>Volume Rate: {analysis.volume_info.volume_rate.toFixed(2)}</li>
                      <li>Money Flow Rate: {analysis.volume_info.money_flow_rate.toFixed(2)}</li>
                      <li>Current Volume: {analysis.volume_info.current_volume.toLocaleString()}</li>
                      <li>Avg Volume (5d): {analysis.volume_info.avg_volume_5d.toLocaleString()}</li>
                      <li>
                        Detected At:{" "}
                        {formatDistance(new Date(analysis.volume_info.detected_at + "Z"), new Date(), {
                          addSuffix: true,
                        })}
                      </li>
                      <li>
                        1st Spike Date: {analysis.volume_info.spike_info?.[0]?.spike_date ?? "N/A"}
                      </li>
                      <li>
                        1st Close↑High: {highlightKeywords(analysis.volume_info.spike_info?.[0]?.first_day_close_near_high ? "Yes" : "No")}
                      </li>
                      <li>
                        Respikes: {analysis.volume_info.spike_info?.[0]?.number_of_respikes ?? "N/A"}
                      </li>
                      <li>
                        Drop↓High (%): {analysis.volume_info.spike_info?.[0]?.drop_from_high_pct?.toFixed(2) ?? "N/A"}
                      </li>
                      <li>
                        Close↓Low: {highlightKeywords(analysis.volume_info.spike_info?.[0]?.last_day_close_near_low ? "Yes" : "No")}
                      </li>
                    </ul>
                  </Col>

                  <Col md={4}>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
                      <div style={{ flex: "1 1 300px", minWidth: 300 }}>
                        <h5 className="mb-3">📉 15-Day Chart</h5>
                        {analysis.volume_info.recent_prices && analysis.volume_info.recent_prices.length > 0 ? (
                          <MiniCandleChart
                            data={analysis.volume_info.recent_prices.map(p => ({
                              date: p.date,
                              open: p.open,
                              high: p.high,
                              low: p.low,
                              close: p.close,
                            }))}
                          />
                        ) : (
                          <p className="text-muted">No price data</p>
                        )}
                      </div>

                      <div style={{ flexShrink: 0, marginTop: "1.5rem" }}>
                        <h5 style={{ marginBottom: "0.25rem" }}>
                          📈{" "}
                          <a
                            href={analysis.volume_info.kabutan_chart_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{ whiteSpace: "nowrap" }}
                          >
                            View Kabutan Chart
                          </a>
                        </h5>
                      </div>
                    </div>
                  </Col>
                </Row>

                <h5 className="mt-4">Summary</h5>
                <div className="mb-4">
                  {analysis.volume_info.recommendation && (
                    <div className="mb-1">
                      Recommendation: {highlightKeywords(analysis.volume_info.recommendation)}
                    </div>
                  )}
                  <div className="mb-1">Promising Score: {analysis.volume_info.promising_score ?? "?"}</div>
                </div>

                <h5 className="mt-4">GPT Reasoning</h5>
                <p style={{ whiteSpace: "pre-wrap" }}>
                  {analysis.volume_info.reasoning || "(No reasoning provided)"}
                </p>

                {Array.isArray(analysis.volume_info.top_news) && analysis.volume_info.top_news.length > 0 && (
                  <>
                    <h5 className="mt-4">Top News</h5>
                    <ul className="list-unstyled">
                      {analysis.volume_info.top_news.map((item, idx) => (
                        <li key={idx} className="mb-3">
                          <a href={item.url} target="_blank" rel="noopener noreferrer">
                            {item.headline}
                          </a>
                          <br />
                          <small className="text-muted">
                            [{item.category}] {new Date(item.published_at).toLocaleString()}
                          </small>
                          <br />
                          <strong>Keyword:</strong> {highlightKeywords(item.keyword)}: {highlightRank(item.rank)}
                          <br />
                          <em style={{ display: "block", marginTop: "0.25rem" }}>
                            {item.impact_reason}
                          </em>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </>
            )}

            {/* Sticky bottom-right note box */}
            <div
              style={{
                position: "sticky",
                bottom: 0,
                display: "flex",
                justifyContent: "flex-end",
                background: "transparent",
                zIndex: 2,
              }}
            >
              <div
                style={{
                  width: "35%",
                  background: "white",
                  padding: "8px",
                  borderTop: "1px solid #ddd",
                  boxShadow: "0 -2px 6px rgba(0,0,0,0.1)",
                }}
              >
                <label htmlFor="stock-note" className="form-label fw-bold">
                  📝 Note
                </label>
                <textarea
                  id="stock-note"
                  className="form-control"
                  rows={3}
                  value={noteValue}
                  onChange={(e) => setNoteValue(e.target.value)}
                  disabled={isSaving}
                />
                <button
                  className="btn btn-primary btn-sm mt-2"
                  onClick={() => onNoteChange(stockTicker, noteValue)}
                  disabled={isSaving}
                >
                  {isSaving ? "Saving..." : "Save Note"}
                </button>
              </div>
            </div>
          </Tab>
          <Tab eventKey="intraday" title="Intraday Analyze">
            <IntradayAnalyzeTab ticker={stockTicker} />
          </Tab>
        </Tabs>
      </Modal.Body>
      <Modal.Footer>
        <Button variant="secondary" onClick={onClose}>Close</Button>
      </Modal.Footer>
    </Modal>
  );
};

export default PreMarketStockModal;