export interface VolumeSurgeStock {
  promising_score?: number;
  recommendation?: any;
  ticker: string;
  name: string;
  current_price: number;
  price_change: number;
  volume_rate: number;
  money_flow_rate: number;
  current_volume: number;
  avg_volume_5d: number;
  detected_at: string;
  starred?: boolean;
  note?: string;

  top_news?: {
    published_at: string;
    category: string;
    headline: string;
    url: string;
    score: number;
    impact_verdict?: string; // ✅ Add this
    impact_reason?: string;  // ✅ And this
  }[];
}

export interface AnalysisSignal {
  candle_pattern?: string | null;
  breakout_detected?: boolean;
  resistance_level?: number | null;
  close_today?: number | null;
  rsi?: number | null;
  macd_line?: number | null;
  macd_signal?: number | null;
  macd_hist?: number | null;
  bb_upper?: number | null;
  bb_middle?: number | null;
  bb_lower?: number | null;
  bb_current_price?: number | null;
  sma_50?: number | null;
  sma_200?: number | null;
  ema_20?: number | null;
  sma_crossover?: string | null;
  w_shape?: boolean;
  flags_pennants?: boolean;
  triangle?: boolean;
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

export interface ScanFormProps {
  surgeThreshold: number;
  priceThreshold: number;
  fromPage: number;
  toPage: number;
  loading: boolean;
  onSurgeThresholdChange: (value: number) => void;
  onPriceThresholdChange: (value: number) => void;
  onFromPageChange: (value: number) => void;
  onToPageChange: (value: number) => void;
  onScan: () => void;
}

export interface NewsImpactItem {
  headline: string;
  url: string;
  category: string;
  published_at: string;
  verdict: "S+" | "S" | "A+" | "A" | "A-"| "B";
  reason: string;
}

export interface PreMarketScanResult {
  ticker: string;
  news: NewsImpactItem[];
}