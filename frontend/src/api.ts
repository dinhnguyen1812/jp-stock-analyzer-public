const BASE_URL = "http://localhost:8002";

export async function fetchStockAnalysis(ticker: string) {
  const res = await fetch(`${BASE_URL}/longterm/${ticker}/analysis`);
  if (!res.ok) throw new Error("Failed to fetch stock analysis");
  return await res.json();
}
