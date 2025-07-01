import React, { useState } from "react";
import { Table } from "react-bootstrap";
import StockRow from "./StockRow";
import type { VolumeSurgeStock } from "../../types";

interface StockTableProps {
  stocks: VolumeSurgeStock[];
}

type SortKey = keyof Pick<
  VolumeSurgeStock,
  | "current_price"
  | "price_change"
  | "volume_rate"
  | "money_flow_rate"
  | "current_volume"
  | "avg_volume_5d"
  | "detected_at"
  | "promising_score"
>;

const StockTable: React.FC<StockTableProps> = ({ stocks }) => {
  const [sortKey, setSortKey] = useState<SortKey>("volume_rate");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");

  const handleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortOrder("desc");
    }
  };

  const sortedStocks = [...stocks].sort((a, b) => {
    const aVal = a[sortKey];
    const bVal = b[sortKey];

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

  const renderSortIndicator = (key: SortKey) => {
    return sortKey === key ? (sortOrder === "asc" ? " ▲" : " ▼") : "";
  };

  return (
    <div>
      <Table
        striped
        bordered
        hover
        responsive
        className="table-sm align-top"
      >
        <thead className="table-light sticky-top">
          <tr>
            <th style={{ width: "40px" }}> </th>
            <th style={{ width: "80px" }} className="align-top text-center">Ticker</th>
            <th style={{ minWidth: "140px" }} className="align-top text-center">Name</th>
            <th
              style={{ width: "120px" }}
              className="align-top text-center clickable"
              onClick={() => handleSort("current_price")}
            >
              Current Price (円){renderSortIndicator("current_price")}
            </th>
            <th
              style={{ width: "180px" }}
              className="align-top text-center clickable"
              onClick={() => handleSort("price_change")}
            >
              Price Change (%) {renderSortIndicator("price_change")}
            </th>
            <th
              style={{ width: "160px" }}
              className="align-top text-center clickable"
              onClick={() => handleSort("volume_rate")}
            >
              Volume Rate {renderSortIndicator("volume_rate")}
            </th>
            <th
              style={{ width: "140px" }}
              className="align-top text-center clickable"
              onClick={() => handleSort("money_flow_rate")}
            >
              Money Flow Rate {renderSortIndicator("money_flow_rate")}
            </th>
            <th
              style={{ minWidth: "160px" }}
              className="align-top text-center clickable"
              onClick={() => handleSort("current_volume")}
            >
              Current Volume (株) {renderSortIndicator("current_volume")}
            </th>
            <th
              style={{ minWidth: "160px" }}
              className="align-top text-center clickable"
              onClick={() => handleSort("avg_volume_5d")}
            >
              Avg Volume (5d) {renderSortIndicator("avg_volume_5d")}
            </th>
            <th
              style={{ minWidth: "140px" }}
              className="align-top text-center clickable"
              onClick={() => handleSort("detected_at")}
            >
              Detected At {renderSortIndicator("detected_at")}
            </th>
            <th
              style={{ minWidth: "180px" }}
              className="align-top text-center clickable"
              onClick={() => handleSort("promising_score")}
            >
              Action / GPT {renderSortIndicator("promising_score")}
            </th>
          </tr>
        </thead>
        <tbody>
          {sortedStocks.map((stock) => (
            <StockRow
              key={stock.ticker}
              stock={stock}
              latestDetectedAt={latestDetectedAt}
            />
          ))}
        </tbody>
      </Table>
    </div>
  );
};

export default StockTable;
