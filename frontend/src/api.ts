const BASE_URL = "http://localhost:8002";

export interface StockData {
  ticker: string;
  name: string;
  market: string;
  price: number;
  per: number;
  pbr: number;
  roe: number;
  eps: number;
  market_cap: number;
}

export interface NewsItem {
  headline: string;
  url: string;
  published_at: string;
}

export async function fetchStock(ticker: string): Promise<StockData> {
  const res = await fetch(`${BASE_URL}/stocks/${ticker}`);
  if (!res.ok) throw new Error("Stock not found.");
  return res.json();
}

export async function fetchNews(ticker: string): Promise<NewsItem[]> {
  const res = await fetch(`${BASE_URL}/stocks/${ticker}/news`);
  if (!res.ok) throw new Error("Failed to fetch news.");
  return res.json();
}

