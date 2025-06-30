import React from "react";
import { Table } from "react-bootstrap";
import StockRow from "./StockRow";
import type { VolumeSurgeStock } from "../../types";

interface StockTableProps {
  stocks: VolumeSurgeStock[];
}

const StockTable: React.FC<StockTableProps> = ({ stocks }) => {
  // Compute latest detected_at (as ISO string)
  const latestDetectedAt = stocks.length
    ? new Date(
        Math.max(...stocks.map((s) => new Date(s.detected_at).getTime()))
      ).toISOString()
    : new Date(0).toISOString(); // fallback default

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
            <th style={{ width: "40px" }}> </th> {/* Star column */}
            <th style={{ width: "80px" }} className="align-top">Ticker</th>
            <th style={{ minWidth: "140px" }} className="align-top">Name</th>
            <th style={{ width: "120px" }}>Current Price (円)</th>
            <th style={{ width: "180px" }}>Price Change (%)</th> {/* wider */}
            <th style={{ width: "120px" }}>Volume Rate</th>
            <th style={{ width: "140px" }}>Money Flow Rate</th>
            <th style={{ minWidth: "160px" }} className="text-center">Current Volume (株)</th>
            <th style={{ minWidth: "160px" }} className="align-top">Avg Volume (5d)</th>
            <th style={{ minWidth: "180px" }} className="align-top">Detected At</th>
            <th style={{ minWidth: "180px" }} className="align-top text-center">
              Action / GPT
            </th>
          </tr>
        </thead>
        <tbody>
          {stocks.map((stock) => (
            <StockRow
              key={stock.ticker}
              stock={stock}
              latestDetectedAt={latestDetectedAt} // ✅ pass to highlight older entries
            />
          ))}
        </tbody>
      </Table>
    </div>
  );
};

export default StockTable;
