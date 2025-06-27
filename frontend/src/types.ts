export interface VolumeSurgeStock {
  ticker: string;
  name: string;
  current_price: number;
  price_change: number;
  volume_rate: number;
  money_flow_rate: number;
  current_volume: number;
  avg_volume_5d: number;
  detected_at: string;
  starred?: boolean; // optional, from DB
  reasoning?: string | null;
  recommendation?: "Buy" | "Hold" | "Sell" | null;
  promising_score?: number | null;
  top_news: Array<{
    published_at: string;
    category: string;
    headline: string;
    url: string;
    score: number;
  }>;
}

export interface KabutanNewsAnalysis {
  ticker: string;
  volume_info: {
    reasoning: string;
    promising_score: string;
    recommendation: string;
    ticker: string;
    name: string;
    current_price: number;
    price_change: number;
    volume_rate: number;
    money_flow_rate: number;
    current_volume: number;
    avg_volume_5d: number;
    detected_at: string;
  };
  top_news: Array<{
    published_at: string;
    category: string;
    headline: string;
    url: string;
    score: number;
  }>;
  gpt_summary: string;
}
