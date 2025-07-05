import type { KabutanNewsAnalysis } from "./types";

const BASE_URL = "http://localhost:8002";

export async function fetchStockAnalysis(ticker: string) {
  const res = await fetch(`${BASE_URL}/longterm/${ticker}/analysis`);
  if (!res.ok) throw new Error("Failed to fetch stock analysis");
  return await res.json();
}

export async function triggerVolumeScan(
  surge_threshold = 2.0,
  price_threshold = 300.0,
  from_page = 1,
  to_page = 1
) {
  const res = await fetch(`${BASE_URL}/shortterm/volume_scan`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      surge_threshold,
      price_threshold,
      from_page,
      to_page,
    }),
  });

  if (!res.ok) throw new Error("Volume scan failed");
  return await res.json();
}

export async function fetchRecentVolumeSurges(
  surgeThreshold: number = 2.0,
  priceThreshold: number = 150.0,
  promisingScoreThreshold: number = 0.0,
  starredOnly: boolean = false
) {
  const res = await fetch(
    `${BASE_URL}/shortterm/volume_surges?surge_threshold=${surgeThreshold}&price_threshold=${priceThreshold}&promising_score_threshold=${promisingScoreThreshold}&starred_only=${starredOnly}`
  );
  if (!res.ok) throw new Error("Failed to fetch volume surge results");
  return await res.json();
}


export async function fetchKabutanNewsAnalysis(ticker: string, limit = 30, top_n = 10, user_prompt?: string) {
  const params = new URLSearchParams({
    limit: limit.toString(),
    top_n: top_n.toString(),
  });
  if (user_prompt) {
    params.append("user_prompt", user_prompt);
  }

  const res = await fetch(`${BASE_URL}/shortterm/${ticker}/kabutan_news_analysis?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to fetch analysis for ${ticker}`);
  return (await res.json()) as KabutanNewsAnalysis;
}

export async function fetchSavedAnalysis(ticker: string) {
  const res = await fetch(`${BASE_URL}/shortterm/${ticker}/volume_surge/analysis`);
  if (!res.ok) throw new Error("Failed to fetch saved analysis");
  return await res.json();
}

export async function starStock(ticker: string) {
  const res = await fetch(`${BASE_URL}/shortterm/${ticker}/star`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Failed to star stock");
  return await res.json();
}

export async function unstarStock(ticker: string) {
  const res = await fetch(`${BASE_URL}/shortterm/${ticker}/star`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Failed to unstar stock");
  return await res.json();
}

export async function fetchIntradayAnalysis(ticker: string) {
  const response = await fetch(`${BASE_URL}/shortterm/analyze_ticker/${ticker}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch intraday analysis for ${ticker}`);
  }
  return await response.json();
}

export async function analyzeAllStarredStocks() {
  const res = await fetch(`${BASE_URL}/shortterm/analyze_starred`);
  if (!res.ok) throw new Error("Failed to analyze starred stocks");
  return await res.json();
}

export async function fetchNewsSignalsWithImpacts() {
  const res = await fetch(`${BASE_URL}/shortterm/news_signals`);
  if (!res.ok) throw new Error("Failed to fetch news signals");
  return await res.json();
}