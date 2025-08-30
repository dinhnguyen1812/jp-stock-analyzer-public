// components/premarket/types.ts
import type { VolumeSurgeStock, AnalysisSignal } from "../../types";

export interface DailyPrice {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface SpikeInfo {
  spike_date: string;
  first_day_close_near_high: boolean;
  first_spike_pct: number;
  days_since_spike: number;
  number_of_respikes: number;
  drop_from_high_pct: number;
  last_day_close_near_low: boolean;
  score: number;
}

export interface AnalyzedVolumeInfo extends VolumeSurgeStock {
  recent_prices?: DailyPrice[];
  spike_info?: SpikeInfo[];
  reasoning?: string;
  recommendation?: "Buy" | "Hold" | "Sell" | null;
  promising_score?: number;
  news_score?: number;
  top_news?: {
    published_at: string;
    category: string;
    headline: string;
    url: string;
    score: number;
    impact_verdict: string;
    impact_reason: string;
    keyword: string;
    rank: string;
  }[];
  highest_impact_keyword?: string;
  highest_impact_rank?: string;
  drop_from_high_pct?: number;
  rebound_from_low_pct?: number;
  highest_price?: number;
  lowest_price?: number;
  kabutan_chart_url?: string;
}

export interface SavedAnalysis {
  volume_info: AnalyzedVolumeInfo;
  analysis_signal: AnalysisSignal;
}
