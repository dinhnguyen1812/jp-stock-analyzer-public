import React, { useState } from "react";
import { Button, Modal, Table, Spinner } from "react-bootstrap";
import { fetchCurrentEntries } from "../../api";

const HoldingsCard: React.FC = () => {
  const [showModal, setShowModal] = useState(false);
  const [holdings, setHoldings] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);

  const handleShow = async () => {
    setShowModal(true);
    setLoading(true);
    try {
      const data = await fetchCurrentEntries();
      setHoldings(data);
    } catch (error) {
      alert("Failed to fetch holdings");
    } finally {
      setLoading(false);
    }
  };

  const formatToJST = (utcString: string) => {
    const date = new Date(utcString + "Z"); // force UTC parsing
    return date.toLocaleString("ja-JP", {
      timeZone: "Asia/Tokyo",
      hour12: false,
    });
  };

  return (
    <>
      <Button variant="dark" onClick={handleShow}>
        💼 Holdings List
      </Button>

      <Modal show={showModal} onHide={() => setShowModal(false)} size="lg" scrollable>
        <Modal.Header closeButton>
          <Modal.Title>Current Holdings</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {loading ? (
            <div className="text-center">
              <Spinner animation="border" />
            </div>
          ) : holdings ? (
            <>
              <Table striped bordered hover size="sm">
                <thead className="table-light">
                  <tr>
                    <th>Ticker</th>
                    <th>Entry Price</th>
                    <th>Current Price</th>
                    <th>Amount</th>
                    <th>Entry Time</th>
                    <th>P/L (¥)</th>
                    <th>P/L (%)</th>
                  </tr>
                </thead>
                <tbody>
                  {holdings.entries.map((entry: any, idx: number) => (
                    <tr key={idx}>
                      <td>{entry.ticker}</td>
                      <td>{entry.entry_price}</td>
                      <td>{entry.current_price}</td>
                      <td>{entry.amount}</td>
                      <td style={{ fontSize: "0.75rem" }}>
                        {formatToJST(entry.entry_time)}
                      </td>
                      <td style={{ color: entry.profit_amount >= 0 ? "green" : "red" }}>
                        {entry.profit_amount}
                      </td>
                      <td style={{ color: entry.profit_percent >= 0 ? "green" : "red" }}>
                        {entry.profit_percent}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>

              <div className="mt-3">
                <p>
                  <strong>Total Capital:</strong> ¥{holdings.summary.total_invested.toLocaleString()}
                </p>
                <p>
                  <strong>Total Current Value:</strong> ¥{holdings.summary.total_current_value.toLocaleString()}
                </p>
                <p>
                  <strong>Total Profit:</strong>{" "}
                  <span style={{ color: holdings.summary.total_profit >= 0 ? "green" : "red" }}>
                    ¥{holdings.summary.total_profit} ({holdings.summary.total_profit_percent}%)
                  </span>
                </p>
              </div>
            </>
          ) : (
            <p>(No holdings yet)</p>
          )}
        </Modal.Body>
      </Modal>
    </>
  );
};

export default HoldingsCard;
