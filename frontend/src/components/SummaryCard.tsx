import { Card, Badge } from "react-bootstrap";

interface SummaryCardProps {
  summary: string;
  sentiment: string;
  epsOutlook: string;
  reasoning?: string;
}

export const SummaryCard: React.FC<SummaryCardProps> = ({
  summary,
  sentiment,
  epsOutlook,
  reasoning,
}) => {
  const color =
    sentiment === "Bullish"
      ? "success"
      : sentiment === "Bearish"
      ? "danger"
      : "secondary";

  return (
    <Card
      className="mb-3"
      style={{
        maxHeight: "710px",
        overflowY: "auto",
        border: "1px solid #ced4da",
        borderRadius: "8px",
        padding: "1rem",
        backgroundColor: "#fff",
      }}
    >
      <Card.Header>📈 GPT Stock Summary</Card.Header>
      <Card.Body>
        <p style={{ whiteSpace: "pre-line" }}>{summary}</p>

        {reasoning && (
          <>
            <hr />
            <p>
              <strong>📌 GPT Reasoning:</strong>
              <br />
              {reasoning}
            </p>
          </>
        )}

        <hr />

        <p>
          <strong>Sentiment:</strong>{" "}
          <Badge bg={color}>{sentiment}</Badge>
        </p>
        <p>
          <strong>EPS Outlook:</strong>
          <br />
          <span style={{ whiteSpace: "pre-line" }}>{epsOutlook}</span>
        </p>
      </Card.Body>
    </Card>
  );
};
