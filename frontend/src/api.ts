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
  pages = 1
) {
  const res = await fetch(`${BASE_URL}/shortterm/volume_scan`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ surge_threshold, price_threshold, pages }),
  });
  if (!res.ok) throw new Error("Volume scan failed");
  return await res.json();
}

export async function fetchRecentVolumeSurges(hours: number = 24) {
  const res = await fetch(`${BASE_URL}/shortterm/volume_surges?hours=${hours}`);
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