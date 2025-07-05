import React from "react";
import { Modal, Button } from "react-bootstrap";

interface NewsImpactModalProps {
  show: boolean;
  onHide: () => void;
  rawResponse: string;
}

const highlightKeywords = (text: string) => {
  const keywordPatterns: { pattern: RegExp; className: string }[] = [
    { pattern: /\bHigh\b/g, className: "text-danger fw-bold" },
    { pattern: /\bMedium-High\b/g, className: "text-warning fw-bold" },
    { pattern: /\bMedium\b/g, className: "text-warning" },
    { pattern: /\bMedium-Low\b/g, className: "text-secondary" },
    { pattern: /\bLow\b/g, className: "text-muted" },
    { pattern: /\bPositive\b/g, className: "text-success fw-bold" },
    { pattern: /\bNegative\b/g, className: "text-danger fw-bold" },
    { pattern: /\bNeutral\b/g, className: "text-secondary fw-bold" },
  ];

  let html = text;
  for (const { pattern, className } of keywordPatterns) {
    html = html.replace(pattern, (match) => `<span class="${className}">${match}</span>`);
  }
  return html;
};

const NewsImpactModal: React.FC<NewsImpactModalProps> = ({
  show,
  onHide,
  rawResponse,
}) => {
  return (
    <Modal show={show} onHide={onHide} size="lg" scrollable>
      <Modal.Header closeButton>
        <Modal.Title>📊 GPT News + Stock Impact</Modal.Title>
      </Modal.Header>
      <Modal.Body style={{ fontFamily: "monospace", fontSize: "0.9rem" }}>
        <div
          dangerouslySetInnerHTML={{ __html: highlightKeywords(rawResponse) }}
          style={{ whiteSpace: "pre-wrap" }}
        />
      </Modal.Body>
      <Modal.Footer>
        <Button variant="secondary" onClick={onHide}>
          Close
        </Button>
      </Modal.Footer>
    </Modal>
  );
};

export default NewsImpactModal;
