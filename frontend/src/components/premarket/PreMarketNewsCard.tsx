import React, { useState } from "react";
import { Table, Card, Badge } from "react-bootstrap";

interface PositiveNewsItem {
  ticker: string;
  headline: string;
  verdict: string;
  reason: string;
  created_at: string;
  published_at?: string | null;
  url?: string | null;
}

interface Props {
  newsItems: PositiveNewsItem[];
}

const verdictColor = (verdict: string) => {
  const v = verdict.toLowerCase();
  if (v === "decisive") return "danger";
  if (v === "great") return "success";
  if (v === "good") return "warning";
  if (v === "neutral") return "secondary";
  return "light";
};

const PreMarketNewsCard: React.FC<Props> = ({ newsItems }) => {
  const [sortBy, setSortBy] = useState<"published_at" | "verdict">("published_at");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");

  const sortedNews = [...newsItems].sort((a, b) => {
    if (sortBy === "published_at") {
      const aTime = new Date(a.published_at || a.created_at).getTime();
      const bTime = new Date(b.published_at || b.created_at).getTime();
      return sortOrder === "asc" ? aTime - bTime : bTime - aTime;
    }

    if (sortBy === "verdict") {
      const order = ["decisive", "great", "good", "neutral", "bad"];
      const aRank = order.indexOf(a.verdict.toLowerCase());
      const bRank = order.indexOf(b.verdict.toLowerCase());
      return sortOrder === "asc" ? aRank - bRank : bRank - aRank;
    }

    return 0;
  });

  const toggleSort = (key: "published_at" | "verdict") => {
    if (key === sortBy) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortBy(key);
      setSortOrder("desc");
    }
  };

  const renderSortArrow = (key: string) => {
    if (sortBy === key) return sortOrder === "asc" ? " ▲" : " ▼";
    return "";
  };

  return (
    <Card className="mt-4 shadow-sm">
      <Card.Header>📰 News Table</Card.Header>
      <Card.Body className="p-0">
        <Table striped bordered hover responsive size="sm" className="mb-0">
          <thead className="table-light">
            <tr>
              <th className="text-center">Ticker</th>
              <th>Headline</th>
              <th
                className="clickable text-center"
                style={{ cursor: "pointer" }}
                onClick={() => toggleSort("published_at")}
              >
                Published At {renderSortArrow("published_at")}
              </th>
              <th
                className="clickable text-center"
                style={{ cursor: "pointer" }}
                onClick={() => toggleSort("verdict")}
              >
                Verdict {renderSortArrow("verdict")}
              </th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            {sortedNews.map((item, idx) => (
              <tr key={`${item.ticker}-${item.published_at || idx}`}>
                <td className="text-center">{item.ticker}</td>
                <td>
                  <a
                    href={item.url || `https://kabutan.jp/stock/news?code=${item.ticker}`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {item.headline}
                  </a>
                </td>
                <td className="text-center">
                  {item.published_at
                    ? new Date(item.published_at).toLocaleString()
                    : "Unknown"}
                </td>
                <td className="text-center">
                  <Badge bg={verdictColor(item.verdict)}>{item.verdict}</Badge>
                </td>
                <td>{item.reason}</td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Card.Body>
    </Card>
  );
};

export default PreMarketNewsCard;
