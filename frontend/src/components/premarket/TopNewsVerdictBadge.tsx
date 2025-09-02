// components/premarket/TopNewsVerdictBadge.tsx
import React from "react";
import { Badge } from "react-bootstrap";

interface TopNewsItem {
  impact_verdict?: string;
  published_at?: string;
}

interface Props {
  topNews?: TopNewsItem[];
  latestThresholdDate?: Date | null;
}

const verdictRank: Record<string, number> = {
  "S+": 7, "S": 6, "A+": 5, "A": 4, "A-": 3, "B": 2, "C": 1, "D": 0
};

const verdictColors: Record<string, string> = {
  "S+": "danger", "S": "success", "A+": "primary", "A": "warning",
  "A-": "info", "B": "secondary", "C": "dark", "D": "danger"
};

const TopNewsVerdictBadge: React.FC<Props> = ({ topNews, latestThresholdDate }) => {
  if (!topNews || topNews.length === 0 || !latestThresholdDate) return null;

  const thresholdDate = new Date(Date.UTC(
    latestThresholdDate.getUTCFullYear(),
    latestThresholdDate.getUTCMonth(),
    latestThresholdDate.getUTCDate(),
    6, 29, 0
  ));

  // Filter news that have verdict and are “new”
  const newNews = topNews.filter(n => n.impact_verdict && n.published_at && new Date(n.published_at) >= thresholdDate);

  if (newNews.length === 0) return null;

  // Get the best verdict among new news
  const bestNewNews = newNews.sort((a, b) => {
    const aRank = verdictRank[a.impact_verdict!.toUpperCase()] ?? 0;
    const bRank = verdictRank[b.impact_verdict!.toUpperCase()] ?? 0;
    return bRank - aRank;
  })[0];

  const verdict = bestNewNews.impact_verdict?.toUpperCase() ?? "";
  const badgeColor = verdictColors[verdict] ?? "light";

  return (
    <div className="d-flex justify-content-center">
      <Badge
        bg={badgeColor}
        text="light"
        className="border"
        style={{ fontSize: "0.75rem" }}
      >
        {verdict} ❤️
      </Badge>
    </div>
  );
};

export default TopNewsVerdictBadge;
