import React, { useState } from "react";
import { Button, Modal, Spinner } from "react-bootstrap";
import type { VolumeSurgeStock, KabutanNewsAnalysis } from "../../types";
import { fetchKabutanNewsAnalysis } from "../../api";

interface StockRowProps {
  stock: VolumeSurgeStock;
}

const StockRow: React.FC<StockRowProps> = ({ stock }) => {
  const [showModal, setShowModal] = useState(false);
  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState<KabutanNewsAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleAnalyzeClick = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchKabutanNewsAnalysis(stock.ticker);
      setAnalysis(data);
      setShowModal(true);
    } catch (err: any) {
      setError(err.message || "Failed to load analysis");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <tr>
        <td>{stock.ticker}</td>
        <td>{stock.name}</td>
        <td>{stock.current_price.toFixed(2)}</td>
        <td>{stock.price_change.toFixed(2)}</td>
        <td>{stock.volume_rate.toFixed(2)}</td>
        <td>{stock.money_flow_rate.toFixed(2)}</td>
        <td>{stock.current_volume.toLocaleString()}</td>
        <td>{stock.avg_volume_5d.toLocaleString()}</td>
        <td>{new Date(stock.detected_at).toLocaleString()}</td>
        <td>
          <Button variant="outline-primary" size="sm" onClick={handleAnalyzeClick} disabled={loading}>
            {loading ? <Spinner animation="border" size="sm" /> : "Analyze"}
          </Button>
        </td>
      </tr>

      <Modal size="lg" show={showModal} onHide={() => setShowModal(false)}>
        <Modal.Header closeButton>
          <Modal.Title>Analysis for {stock.ticker}</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {error && <p className="text-danger">{error}</p>}

          {!error && !analysis && <p>Loading analysis...</p>}

          {analysis && (
            <>
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

              <h5>Top News</h5>
              <ul>
                {analysis.top_news.map((newsItem, idx) => (
                  <li key={idx}>
                    <a href={newsItem.url} target="_blank" rel="noopener noreferrer">
                      {newsItem.headline}
                    </a>{" "}
                    ({new Date(newsItem.published_at).toLocaleDateString()})
                  </li>
                ))}
              </ul>

              <h5>GPT Summary</h5>
              <p style={{ whiteSpace: "pre-wrap" }}>{analysis.gpt_summary}</p>
            </>
          )}
        </Modal.Body>
      </Modal>
    </>
  );
};

export default StockRow;
