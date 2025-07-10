import React, { useState } from "react";
import { Card, Button, Spinner, Table, Badge } from "react-bootstrap";
import { fetchSpikeScans } from "../../api";
import { formatDistanceToNow } from "date-fns";

interface SpikeEntry {
  ticker: string;
  volume_rate: number;
  money_flow_rate: number;
  detected_at: string;
  downtrend_info?: any;
  top_news?: any;
  updated_at: string;
}

const SpikeScanCard: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [spikeData, setSpikeData] = useState<SpikeEntry[]>([]);

  const handleFetchSpikes = async () => {
    setLoading(true);
    try {
      const data = await fetchSpikeScans();
      setSpikeData(data);
    } catch (err) {
      alert("Failed to fetch spike scan data.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="mb-3 shadow-sm">
      <Card.Body>
        <div className="d-flex justify-content-between align-items-center mb-2">
          <h5 className="mb-0">📊 Spike Scan Result</h5>
          <Button variant="warning" size="sm" onClick={handleFetchSpikes} disabled={loading}>
            {loading ? <Spinner animation="border" size="sm" /> : "📈 Fetch Spikes"}
          </Button>
        </div>

        {spikeData.length === 0 ? (
          <p className="text-muted">No spike data loaded.</p>
        ) : (
          <div style={{ maxHeight: "400px", overflowY: "auto" }}>
            <Table striped bordered hover responsive size="sm">
              <thead>
                <tr>
                  <th>Ticker</th>
                  <th>Vol Rate</th>
                  <th>Flow Rate</th>
                  <th>Detected</th>
                  <th>Downtrend</th>
                  <th>Top News</th>
                </tr>
              </thead>
              <tbody>
                {spikeData.map((entry) => {
                  const jstDate = new Date(new Date(entry.detected_at).getTime() + 9 * 60 * 60 * 1000);
                  return (
                    <tr key={entry.ticker}>
                      <td>
                        <strong>{entry.ticker}</strong>
                      </td>
                      <td>{entry.volume_rate.toFixed(2)}</td>
                      <td>{entry.money_flow_rate?.toFixed(2) ?? "-"}</td>
                      <td title={jstDate.toLocaleString()}>
                        {formatDistanceToNow(jstDate, { addSuffix: true })}
                      </td>
                      <td>
                        {entry.downtrend_info?.had_downtrend ? (
                          <Badge bg="danger">Yes</Badge>
                        ) : (
                          <Badge bg="secondary">No</Badge>
                        )}
                      </td>
                      <td>
                        {entry.top_news && Array.isArray(entry.top_news) ? (
                          <ul className="mb-0" style={{ paddingLeft: "1rem" }}>
                            {entry.top_news.map((n, i) => (
                              <li key={i}>
                                <a href={n.url} target="_blank" rel="noreferrer">
                                  {n.headline}
                                </a>
                                {n.verdict && (
                                  <Badge
                                    bg={
                                      n.verdict === "Decisive"
                                        ? "danger"
                                        : n.verdict === "Great"
                                        ? "success"
                                        : n.verdict === "Good"
                                        ? "primary"
                                        : n.verdict === "Neutral"
                                        ? "warning"
                                        : "secondary"
                                    }
                                    className="ms-2"
                                  >
                                    {n.verdict}
                                  </Badge>
                                )}
                              </li>
                            ))}
                          </ul>
                        ) : (
                          "-"
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </Table>
          </div>
        )}
      </Card.Body>
    </Card>
  );
};

export default SpikeScanCard;
