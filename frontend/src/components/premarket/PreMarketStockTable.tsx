import React, { useEffect, useState } from "react";
import { Table } from "react-bootstrap";
import PreMarketStockRow from "./PreMarketStockRow";
import type { VolumeSurgeStock } from "../../types";
import { fetchSetNote } from "../../api";

const handleNoteChange = async (ticker: string, newNote: string) => {
  try {
    await fetchSetNote(ticker, newNote);
    console.log(`✅ Note updated for ${ticker}`);
  } catch (err) {
    console.error(`❌ Failed to update note for ${ticker}:`, err);
  }
};

type EnrichedStock = VolumeSurgeStock & {
  promising_score?: number;
  momentum_score?: number;
  recommendation?: string | null;
  highest_impact_keyword?: string;
  highest_impact_rank?: string;
  starred?: boolean;
  momentum_signals?: {
    score: number;
    passed: boolean;
    label: string;
    points: number;
    condition: boolean;
    meaning: string;
  }[];
};

interface PreMarketStockTableProps {
  stocks: EnrichedStock[];
  onStarToggle: (ticker: string, starred: boolean) => void;
}

type SortKey = keyof Pick<
  EnrichedStock,
  | "current_price"
  | "price_change"
  | "volume_rate"
  | "money_flow_rate"
  | "current_volume"
  | "avg_volume_5d"
  | "detected_at"
  | "promising_score"
>;

const PreMarketStockTable: React.FC<PreMarketStockTableProps> = ({ stocks, onStarToggle }) => {
  const [sortKey, setSortKey] = useState<SortKey>("volume_rate");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [actionSortKey, setActionSortKey] = useState<"promising_score" | "momentum_score">("promising_score");

  const normalizeStock = (stock: EnrichedStock): EnrichedStock => ({
    ...stock,
    promising_score: (stock as any).promising_score,
    momentum_score: (stock as any).momentum_score,
    recommendation: (stock as any).recommendation,
    highest_impact_keyword: (stock as any).highest_impact_keyword,
    highest_impact_rank: (stock as any).highest_impact_rank,
    momentum_signals: (stock as any).momentum_signals ?? [],
    starred: (stock as any).starred ?? false,
    detected_at: stock.detected_at || new Date().toISOString(),
  });

  const handleSort = (key: SortKey | "action_column") => {
    if (key === "action_column") {
      setSortKey("promising_score");
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      if (key === sortKey) {
        setSortOrder(sortOrder === "asc" ? "desc" : "asc");
      } else {
        setSortKey(key);
        setSortOrder("desc");
      }
    }
  };

  const sortedStocks = [...stocks].sort((a, b) => {
    const aVal =
      sortKey === "promising_score" && actionSortKey === "momentum_score"
        ? (a as any).momentum_score ?? 0
        : a[sortKey] ?? 0;

    const bVal =
      sortKey === "promising_score" && actionSortKey === "momentum_score"
        ? (b as any).momentum_score ?? 0
        : b[sortKey] ?? 0;

    if (sortKey === "detected_at") {
      return sortOrder === "asc"
        ? new Date(aVal as string).getTime() - new Date(bVal as string).getTime()
        : new Date(bVal as string).getTime() - new Date(aVal as string).getTime();
    }

    return sortOrder === "asc"
      ? (aVal as number) - (bVal as number)
      : (bVal as number) - (aVal as number);
  });

  const latestDetectedAt = sortedStocks.length
    ? new Date(
        Math.max(...sortedStocks.map((s) => new Date(s.detected_at).getTime()))
      ).toISOString()
    : new Date(0).toISOString();

  const renderSortIndicator = (key: SortKey) =>
    sortKey === key ? (sortOrder === "asc" ? " ▲" : " ▼") : "";

  return (
    <div className="small">
      <Table striped bordered hover responsive className="table-sm align-top">
        <thead className="table-light sticky-top">
          <tr>
            <th style={{ minWidth: "150px" }} className="align-top text-center">Note</th>
            <th style={{ width: "40px" }}> </th>
            <th style={{ width: "80px" }} className="align-top text-center">Ticker</th>
            <th style={{ minWidth: "120px" }} className="align-top text-center">Name</th>
            <th
              style={{ width: "120px" }}
              className="align-top text-center clickable"
              onClick={() => handleSort("current_price")}
            >
              Current Price (円){renderSortIndicator("current_price")}
            </th>
            <th
              style={{ width: "100px" }}
              className="align-top text-center clickable"
              onClick={() => handleSort("price_change")}
            >
              Price Change (%) {renderSortIndicator("price_change")}
            </th>
            <th
              style={{ width: "80px" }}
              className="align-top text-center clickable"
              onClick={() => handleSort("volume_rate")}
            >
              Volume Rate {renderSortIndicator("volume_rate")}
            </th>
            <th
              style={{ width: "100px" }}
              className="align-top text-center clickable"
              onClick={() => handleSort("money_flow_rate")}
            >
              Money Flow Rate {renderSortIndicator("money_flow_rate")}
            </th>
            <th
              style={{ minWidth: "75px" }}
              className="align-top text-center clickable"
              onClick={() => handleSort("current_volume")}
            >
              Current Volume (株) {renderSortIndicator("current_volume")}
            </th>
            <th
              style={{ minWidth: "75px" }}
              className="align-top text-center clickable"
              onClick={() => handleSort("avg_volume_5d")}
            >
              Avg Volume (5d) {renderSortIndicator("avg_volume_5d")}
            </th>
            <th
              style={{ minWidth: "90px" }}
              className="align-top text-center clickable"
              onClick={() => handleSort("detected_at")}
            >
              Detected At {renderSortIndicator("detected_at")}
            </th>
            <th style={{ minWidth: "250px" }} className="align-top text-center">
              🔑 Key Signals
            </th>
            <th
              style={{ minWidth: "350px" }}
              className="align-top text-center clickable"
              onClick={() => handleSort("action_column")}
            >
              Action / GPT {renderSortIndicator("promising_score")}
              <div style={{ fontSize: "0.75rem", marginTop: "4px" }}>
                <span
                  className={`me-2 ${actionSortKey === "promising_score" ? "fw-bold text-primary" : "text-muted"}`}
                  style={{ cursor: "pointer" }}
                  onClick={(e) => {
                    e.stopPropagation();
                    setActionSortKey("promising_score");
                    if (sortKey === "promising_score") setSortOrder("desc");
                  }}
                >
                  Score
                </span>
                |
                <span
                  className={`ms-2 ${actionSortKey === "momentum_score" ? "fw-bold text-primary" : "text-muted"}`}
                  style={{ cursor: "pointer" }}
                  onClick={(e) => {
                    e.stopPropagation();
                    setActionSortKey("momentum_score");
                    if (sortKey === "promising_score") setSortOrder("desc");
                  }}
                >
                  Signal
                </span>
              </div>
            </th>
          </tr>
        </thead>
        <tbody>
          {sortedStocks.map((stock) => {
            const normalized = normalizeStock(stock);
            const keySignals = normalized.momentum_signals?.filter((s) =>
              ["Volume Rate > 3 / 5 / 10", "Price vs SMA50", "MACD Bullish Crossover"].includes(s.label)
            ) ?? [];

            return (
              <PreMarketStockRow
                key={stock.ticker}
                stock={{ ...normalized, momentum_signals: keySignals }}
                latestDetectedAt={latestDetectedAt}
                onStarToggle={onStarToggle}
                onNoteChange={handleNoteChange}
              />
            );
          })}
        </tbody>
      </Table>
    </div>
  );
};

export default PreMarketStockTable;
