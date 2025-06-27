import React from "react";
import { Table } from "react-bootstrap";
import StockRow from "./StockRow";
import type { VolumeSurgeStock } from "../../types";

interface StockTableProps {
  stocks: VolumeSurgeStock[];
}

const StockTable: React.FC<StockTableProps> = ({ stocks }) => {
  return (
    <Table striped bordered hover responsive>
      <thead>
        <tr>
          <th>Ticker</th>
          <th>Name</th>
          <th>Current Price (円)</th>
          <th>Price Change (%)</th>
          <th>Volume Rate</th>
          <th>Money Flow Rate</th>
          <th>Current Volume (株)</th>
          <th>Avg Volume (5d)</th>
          <th>Detected At</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
        {stocks.map((stock) => (
          <StockRow key={stock.ticker} stock={stock} />
        ))}
      </tbody>
    </Table>
  );
};

export default StockTable;
