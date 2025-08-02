import React, { useState } from "react";
import {
  Card,
  Row,
  Col,
  Form,
  Button,
  Spinner,
  InputGroup,
  Table,
  Badge,
} from "react-bootstrap";
import { scanNewsBulk, getPositiveNewsTickers, starStock, unstarStock } from "../../api";

interface PositiveNewsItem {
  ticker: string;
  headline: string;
  verdict: string;
  reason: string;
  created_at: string;
  published_at?: string | null;
  url?: string | null;
  starred?: boolean;
}

const getVerdictColor = (verdict: string) => {
  const lower = verdict?.toLowerCase();
  if (lower === "decisive") return "danger";
  if (lower === "great") return "success";
  if (lower === "good") return "warning";
  if (lower === "neutral") return "secondary";
  // if (lower === "unsure") return "secondary";
  return "light";
};

const verdictPriority: Record<string, number> = {
  decisive: 4,
  great: 3,
  good: 2,
  neutral: 1,
  // unsure: 0,
};

const PreMarketScanNewsCard: React.FC = () => {
  const [fromPage, setFromPage] = useState(1);
  const [toPage, setToPage] = useState(40);
  const [priceThreshold, setPriceThreshold] = useState(1000);
  const [daysThreshold, setDaysThreshold] = useState(1);
  const [loadingScan, setLoadingScan] = useState(false);
  const [loadingPositive, setLoadingPositive] = useState(false);
  const [alertTickers, setAlertTickers] = useState<PositiveNewsItem[]>([]);
  const [sortKey, setSortKey] = useState<"published_at" | "verdict" | null>(null);
  const [sortAsc, setSortAsc] = useState(false);

  const [starred, setStarred] = useState<Record<string, boolean>>({});
  const [starLoading, setStarLoading] = useState<Record<string, boolean>>({});

  const updateStarredFromItems = (items: PositiveNewsItem[]) => {
    const newStarred: Record<string, boolean> = {};
    items.forEach((item) => {
      newStarred[item.ticker] = item.starred ?? false;
    });
    setStarred(newStarred);
  };

  const handleScanNews = async () => {
    setLoadingScan(true);
    setAlertTickers([]);
    try {
      const result = await scanNewsBulk(fromPage, toPage, priceThreshold, daysThreshold);
      if (Array.isArray(result?.alert_tickers)) {
        setAlertTickers(result.alert_tickers);
        updateStarredFromItems(result.alert_tickers);
      } else {
        setAlertTickers([]);
        setStarred({});
      }
    } catch (err) {
      alert("Scan failed: " + err);
    } finally {
      setLoadingScan(false);
    }
  };

  const handleFetchPositiveNews = async () => {
    setLoadingPositive(true);
    try {
      const result = await getPositiveNewsTickers();
      setAlertTickers(result || []);
      updateStarredFromItems(result || []);
    } catch (err) {
      alert("Failed to fetch positive news tickers: " + err);
    } finally {
      setLoadingPositive(false);
    }
  };

  const handleSort = (key: "published_at" | "verdict") => {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(false);
    }
  };

  const handleToggleStar = async (ticker: string) => {
    setStarLoading((prev) => ({ ...prev, [ticker]: true }));
    try {
      const isStarred = starred[ticker];
      if (isStarred) {
        await unstarStock(ticker);
      } else {
        await starStock(ticker);
      }
      setStarred((prev) => ({ ...prev, [ticker]: !isStarred }));
    } catch {
      alert("Failed to update star status.");
    } finally {
      setStarLoading((prev) => ({ ...prev, [ticker]: false }));
    }
  };

  const sortedTickers = [...alertTickers].sort((a, b) => {
    if (sortKey === "published_at") {
      const dateA = new Date(a.published_at || a.created_at).getTime();
      const dateB = new Date(b.published_at || b.created_at).getTime();
      return sortAsc ? dateA - dateB : dateB - dateA;
    }
    if (sortKey === "verdict") {
      const scoreA = verdictPriority[a.verdict?.toLowerCase()] || 0;
      const scoreB = verdictPriority[b.verdict?.toLowerCase()] || 0;
      return sortAsc ? scoreA - scoreB : scoreB - scoreA;
    }
    return 0;
  });

  return (
    <Card className="mb-4 px-3 py-2 shadow-sm">
      <Card.Title>📰 Kabutan News Scanner</Card.Title>

      <Row className="g-3 align-items-center mb-3">
        <Col xs={5} md={2}>
          <InputGroup>
            <InputGroup.Text>From</InputGroup.Text>
            <Form.Control
              type="number"
              value={fromPage}
              min={1}
              onChange={(e) => setFromPage(Number(e.target.value))}
              disabled={loadingScan || loadingPositive}
            />
          </InputGroup>
        </Col>
        <Col xs={12} md={2}>
          <InputGroup>
            <InputGroup.Text>To</InputGroup.Text>
            <Form.Control
              type="number"
              value={toPage}
              min={fromPage}
              onChange={(e) => setToPage(Number(e.target.value))}
              disabled={loadingScan || loadingPositive}
            />
          </InputGroup>
        </Col>
        <Col xs={12} md={2}>
          <InputGroup>
            <InputGroup.Text>Price ≤</InputGroup.Text>
            <Form.Control
              type="number"
              value={priceThreshold}
              onChange={(e) => setPriceThreshold(Number(e.target.value))}
              disabled={loadingScan || loadingPositive}
            />
            <InputGroup.Text>¥</InputGroup.Text>
          </InputGroup>
        </Col>
        <Col xs={12} md={2}>
          <InputGroup>
            <Form.Control
              type="number"
              value={daysThreshold}
              onChange={(e) => setDaysThreshold(Number(e.target.value))}
              disabled={loadingScan || loadingPositive}
            />
            <InputGroup.Text>days before</InputGroup.Text>
          </InputGroup>
        </Col>
        <Col xs={12} md={3}>
          <Row className="g-2">
            <Col>
              <Button
                className="w-100"
                variant="danger"
                onClick={handleScanNews}
                disabled={loadingScan || loadingPositive}
              >
                {loadingScan ? <Spinner animation="border" size="sm" /> : "Scan News"}
              </Button>
            </Col>
            <Col>
              <Button
                className="w-100"
                variant="success"
                onClick={handleFetchPositiveNews}
                disabled={loadingScan || loadingPositive}
              >
                {loadingPositive ? <Spinner animation="border" size="sm" /> : "Fetch Positive"}
              </Button>
            </Col>
          </Row>
        </Col>
      </Row>

      {alertTickers.length > 0 && (
        <div className="mt-3">
          <h6>✅ Positive News Detected:</h6>
          <div className="table-responsive small" style={{ maxHeight: "400px", overflowY: "auto" }}>
            <Table striped bordered hover responsive size="sm">
              <thead className="table-light">
                <tr>
                  <th className="text-center" style={{ width: 40 }}>★</th>
                  <th className="text-center">Ticker</th>
                  <th>Headline</th>
                  <th
                    className="text-center clickable"
                    style={{ cursor: "pointer" }}
                    onClick={() => handleSort("published_at")}
                  >
                    Published At {sortKey === "published_at" && (sortAsc ? "▲" : "▼")}
                  </th>
                  <th
                    className="text-center clickable"
                    style={{ cursor: "pointer" }}
                    onClick={() => handleSort("verdict")}
                  >
                    Verdict {sortKey === "verdict" && (sortAsc ? "▲" : "▼")}
                  </th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {sortedTickers.map((item, idx) => (
                  <tr key={`${item.ticker}-${item.published_at || item.created_at}-${idx}`}>
                    <td className="text-center align-middle">
                      <Button
                        variant="outline-secondary"
                        size="sm"
                        onClick={() => handleToggleStar(item.ticker)}
                        disabled={starLoading[item.ticker]}
                        className="p-0 d-flex justify-content-center align-items-center"
                        style={{ width: 28, height: 28 }}
                      >
                        {starLoading[item.ticker] ? (
                          <Spinner animation="border" size="sm" />
                        ) : (
                          <span
                            style={{
                              fontSize: "1.2rem",
                              color: starred[item.ticker] ? "#ffc107" : "#6c757d",
                              textShadow: starred[item.ticker]
                                ? "0 0 6px #ffc107, 0 0 10px #ffc107"
                                : "none",
                              pointerEvents: "none",
                              userSelect: "none",
                            }}
                          >
                            ★
                          </span>
                        )}
                      </Button>
                    </td>
                    <td className="text-center">{item.ticker}</td>
                    <td>
                      <a
                        href={item.url || `https://kabutan.jp/stock/news?code=${item.ticker}`}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {item.headline || item.ticker}
                      </a>
                    </td>
                    <td className="text-center">
                      {item.published_at
                        ? new Date(item.published_at).toLocaleString()
                        : item.created_at
                        ? new Date(item.created_at).toLocaleString()
                        : "N/A"}
                    </td>

                    <td className="text-center">
                      {item.verdict && (
                        <Badge bg={getVerdictColor(item.verdict)}>{item.verdict}</Badge>
                      )}
                    </td>
                    <td>{item.reason || ""}</td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
        </div>
      )}
    </Card>
  );
};

export default PreMarketScanNewsCard;
