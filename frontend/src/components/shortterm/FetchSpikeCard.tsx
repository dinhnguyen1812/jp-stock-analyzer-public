import React, { useState } from "react";
import { Card, Button, Spinner, Table, Badge } from "react-bootstrap";
import { fetchSpikeScans } from "../../api";
import { formatDistanceToNow } from "date-fns";

interface SpikeEntry {
  ticker: string;
  volume_rate: number;
  money_flow_rate: number;
  current_price: number;
  drop_from_high_pct?: number;
  rebound_from_low_pct?: number;
  detected_at: string;
  downtrend?: {
    had_downtrend: boolean;
    drop_pct: number;
    from_date: string;
    to_date: string;
  };
  top_news?: {
    headline: string;
    url: string;
    verdict: string;
    reason?: string;
  }[];
  updated_at: string;
}

type SortKey =
  | "volume_rate"
  | "money_flow_rate"
  | "detected_at"
  | "drop_from_high_pct"
  | "rebound_from_low_pct";

const FetchSpikeCard: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [spikeData, setSpikeData] = useState<SpikeEntry[]>([]);
  const [sortKey, setSortKey] = useState<SortKey>("volume_rate");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");

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

  const handleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortOrder("desc");
    }
  };

  const sortedData = [...spikeData].sort((a, b) => {
    const aVal = a[sortKey];
    const bVal = b[sortKey];

    if (sortKey === "detected_at") {
      const aDate = aVal ? new Date(aVal as string).getTime() : 0;
      const bDate = bVal ? new Date(bVal as string).getTime() : 0;
      return sortOrder === "asc" ? aDate - bDate : bDate - aDate;
    }

    const aNum = typeof aVal === "number" ? aVal : -Infinity;
    const bNum = typeof bVal === "number" ? bVal : -Infinity;
    return sortOrder === "asc" ? aNum - bNum : bNum - aNum;
  });

  const renderSortIndicator = (key: SortKey) =>
    sortKey === key ? (sortOrder === "asc" ? " ▲" : " ▼") : "";

  return (
    <Card className="mb-3 shadow-sm">
      <Card.Body>
        <div className="d-flex justify-content-between align-items-center mb-2">
          <h5 className="mb-0">📊 Spike Scan Result</h5>
          <Button
            variant="warning"
            size="sm"
            onClick={handleFetchSpikes}
            disabled={loading}
          >
            {loading ? <Spinner animation="border" size="sm" /> : "📈 Fetch Spikes"}
          </Button>
        </div>

        {spikeData.length === 0 ? (
          <p className="text-muted">No spike data loaded.</p>
        ) : (
          <div style={{ maxHeight: "450px", overflowY: "auto" }}>
            <Table striped bordered hover responsive size="sm">
              <thead style={{ position: "sticky", top: 0, backgroundColor: "#fff", zIndex: 10 }}>
                <tr>
                  <th>Ticker</th>
                  <th className="clickable" onClick={() => handleSort("volume_rate")}>
                    Vol Rate {renderSortIndicator("volume_rate")}
                  </th>
                  <th className="clickable" onClick={() => handleSort("money_flow_rate")}>
                    Flow Rate {renderSortIndicator("money_flow_rate")}
                  </th>
                  <th className="clickable" onClick={() => handleSort("detected_at")}>
                    Detected {renderSortIndicator("detected_at")}
                  </th>
                  <th>Current</th>
                  <th
                    className="clickable"
                    onClick={() => handleSort("drop_from_high_pct")}
                  >
                    ↓ from High {renderSortIndicator("drop_from_high_pct")}
                  </th>
                  <th
                    className="clickable"
                    onClick={() => handleSort("rebound_from_low_pct")}
                  >
                    ↑ from Low {renderSortIndicator("rebound_from_low_pct")}
                  </th>
                  <th>Downtrend</th>
                  <th>Top News</th>
                </tr>
              </thead>
              <tbody>
                {sortedData.map((entry) => {
                  const jstDate = new Date(
                    new Date(entry.detected_at).getTime() + 9 * 60 * 60 * 1000
                  );
                  const dt = entry.downtrend;

                  return (
                    <tr key={entry.ticker}>
                      <td><strong>{entry.ticker}</strong></td>
                      <td>{entry.volume_rate.toFixed(2)}</td>
                      <td>{entry.money_flow_rate?.toFixed(2) ?? "-"}</td>
                      <td title={jstDate.toLocaleString()}>
                        {formatDistanceToNow(jstDate, { addSuffix: true })}
                      </td>
                      <td>{entry.current_price.toLocaleString()}</td>
                      <td>
                        {entry.drop_from_high_pct !== undefined
                          ? `${entry.drop_from_high_pct.toFixed(1)}%`
                          : "-"}
                      </td>
                      <td>
                        {entry.rebound_from_low_pct !== undefined
                          ? `${entry.rebound_from_low_pct.toFixed(1)}%`
                          : "-"}
                      </td>
                      <td>
                        {dt ? (
                          <>
                            <Badge bg={dt.had_downtrend ? "danger" : "secondary"}>
                              {dt.had_downtrend ? "Yes" : "No"}
                            </Badge>
                            <div style={{ fontSize: "0.75rem" }}>
                              {dt.drop_pct}%<br />
                              {dt.from_date} → {dt.to_date}
                            </div>
                          </>
                        ) : (
                          "-"
                        )}
                      </td>
                      <td>
                        {Array.isArray(entry.top_news) && entry.top_news.length > 0 ? (
                          <ul className="mb-0" style={{ paddingLeft: "1rem" }}>
                            {entry.top_news.map((n, i) => (
                              <li key={i}>
                                <a href={n.url} target="_blank" rel="noreferrer">
                                  {n.headline}
                                </a>{" "}
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

export default FetchSpikeCard;
