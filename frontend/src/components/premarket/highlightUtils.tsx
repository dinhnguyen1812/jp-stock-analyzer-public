// components/premarket/highlightUtils.tsx
import React, { type JSX } from "react";
import { Badge } from "react-bootstrap";

const keywordMap = [
  { word: "bullish", variant: "success" },
  { word: "bearish", variant: "danger" },
  { word: "neutral", variant: "secondary" },
  { word: "Buy", variant: "success" },
  { word: "Sell", variant: "danger" },
  { word: "Hold", variant: "warning" },
  { word: "short-term", variant: "warning" },
  { word: "Yes", variant: "success" },
  { word: "3_bullish", variant: "success" },
  { word: "3_bearish", variant: "danger" },
  { word: "likely re-spike", variant: "success" }
];

export const highlightKeywords = (text: string): JSX.Element => {
  if (!text) return <span>(No text)</span>;
  const cleanText = text.replace(/\*\*/g, "");
  const keywordRegex = new RegExp(`(${keywordMap.map(k => k.word).join("|")})`, "gi");
  const parts = cleanText.split(keywordRegex);

  return (
    <>
      {parts.map((part, idx) => {
        const match = keywordMap.find(k => k.word.toLowerCase() === part.toLowerCase());
        return match ? (
          <Badge key={idx} bg={match.variant} className="mx-1">{part}</Badge>
        ) : (
          <span key={idx}>{part}</span>
        );
      })}
    </>
  );
};

const rankMap = [
  { word: "S+", variant: "danger" },
  { word: "A+", variant: "primary" },
  { word: "A-", variant: "info" },
  { word: "S", variant: "success" },
  { word: "A", variant: "warning" },
  { word: "B", variant: "secondary" },
  { word: "C", variant: "dark" },
  { word: "D", variant: "danger" }
];

const escapeRegex = (str: string) => str.replace(/[.*+?^${}()|[\]\\-]/g, "\\$&");

const sortedRankMap = [...rankMap].sort((a, b) => b.word.length - a.word.length);

export const highlightRank = (text: string): JSX.Element => {
  if (!text) return <span>(No text)</span>;
  const cleanText = text.replace(/\*\*/g, "");
  const regex = new RegExp(`(${sortedRankMap.map(k => escapeRegex(k.word)).join("|")})`, "gi");
  const parts = cleanText.split(regex);

  return (
    <>
      {parts.map((part, idx) => {
        const match = sortedRankMap.find(k => k.word.toLowerCase() === part.toLowerCase());
        return match ? <Badge key={idx} bg={match.variant} className="mx-1">{part}</Badge> : <span key={idx}>{part}</span>;
      })}
    </>
  );
};
