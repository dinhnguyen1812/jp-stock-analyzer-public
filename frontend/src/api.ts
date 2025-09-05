import type { KabutanNewsAnalysis } from "./types";

const BASE_URL = "http://localhost:8002";

export async function fetchStockAnalysis(ticker: string) {
  const res = await fetch(`${BASE_URL}/longterm/${ticker}/analysis`);
  if (!res.ok) throw new Error("Failed to fetch stock analysis");
  return await res.json();
}

export async function triggerVolumeScan(
  surge_threshold = 1.5,
  price_threshold = 300.0,
  from_page = 1,
  to_page = 3
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
  surgeThreshold: number = 1.5,
  priceThreshold: number = 300.0,
  promisingScoreThreshold: number = 0.0,
  starredOnly: boolean = false,
  watchedOnly: boolean = false
) {
  const res = await fetch(
    `${BASE_URL}/shortterm/volume_surges?surge_threshold=${surgeThreshold}&price_threshold=${priceThreshold}&promising_score_threshold=${promisingScoreThreshold}&starred_only=${starredOnly}&watched_only=${watchedOnly}`
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

export async function addEntryAndAnalyze(ticker: string, amount: number, entry_price: number) {
  const res = await fetch(`${BASE_URL}/shortterm/add_entry_and_analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker, amount, entry_price }),
  });

  if (!res.ok) {
    const errorBody = await res.text();
    throw new Error(`Failed to add entry: ${errorBody}`);
  }

  return await res.json();
}

export async function fetchCurrentEntries() {
  const res = await fetch(`${BASE_URL}/shortterm/current_entries`);
  if (!res.ok) throw new Error("Failed to fetch holdings");
  return await res.json();
}

export async function markEntryAsSold(entryId: number) {
  const res = await fetch(`${BASE_URL}/shortterm/mark_sold/${entryId}`, {
    method: "POST",
    credentials: "include",
  });

  if (!res.ok) {
    const errorBody = await res.text();
    throw new Error(`Failed to mark as sold: ${errorBody}`);
  }

  return await res.json();
}

export async function analyzeAllEntriedStocks() {
  const res = await fetch(`${BASE_URL}/shortterm/analyze_entried`);
  if (!res.ok) throw new Error("Failed to analyze entried stocks");
  return await res.json();
}

export async function getGptAdviceForHoldings() {
  const res = await fetch(`${BASE_URL}/shortterm/gpt_advice_for_holdings`);
  if (!res.ok) throw new Error("Failed to get GPT advice");
  return res.json();
}

export async function triggerVolumeSurgeFullScan(
  surgeThreshold: number,
  fromPage: number,
  toPage: number
): Promise<{
  results: any; report: string 
}> {
  const res = await fetch(`${BASE_URL}/shortterm/scan_spike`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      surge_threshold: surgeThreshold,
      from_page: fromPage,
      to_page: toPage,
    }),
  });

  if (!res.ok) throw new Error("Failed to trigger full spike scan.");
  return res.json();
}

export async function fetchSpikeScans(): Promise<any[]> {
  const res = await fetch(`${BASE_URL}/shortterm/get_spike`);
  if (!res.ok) throw new Error("Failed to fetch spike scan data.");
  return res.json();
}

export async function scanPreMarketVolumeSurges(
  surge_threshold = 2.0,
  price_threshold = 300,
  from_page = 1,
  to_page = 3
) {
  const res = await fetch(`${BASE_URL}/premarket/volume_scan`, {
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

  if (!res.ok) throw new Error("Pre-market scan failed");
  return await res.json();
}

export async function fetchAllAnalyses(
  surge_threshold: number = 2.0,
  price_threshold: number = 300,
  starred_only: boolean = false,
  watched_only: boolean = false,
  detected_at_max_age_days: number = 1.0
) {
  const queryParams = new URLSearchParams({
    surge_threshold: surge_threshold.toString(),
    price_threshold: price_threshold.toString(),
    detected_at_max_age_days: detected_at_max_age_days.toString()
  });

  if (starred_only) {
    queryParams.append("starred_only", "true");
  }

  if (watched_only) {
    queryParams.append("watched_only", "true");
  }

  const res = await fetch(`${BASE_URL}/premarket/get_saved_vs?${queryParams.toString()}`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!res.ok) throw new Error("Failed to fetch analyzed volume surges");

  const data = await res.json();
  // console.log(data); // <-- prints the JSON result
  return data;
}


export async function analyzeAllStarredTickers() {
  const res = await fetch(`${BASE_URL}/premarket/analyze_starred`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!res.ok) {
    throw new Error("Analyzing starred tickers failed");
  }

  return await res.json();
}

export async function analyzeWatchList() {
  const res = await fetch(`${BASE_URL}/premarket/analyze_watch_list`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!res.ok) {
    throw new Error("Analyzing watchlist failed");
  }

  return await res.json();
}

export async function analyzeSingleTicker(ticker: string) {
  if (!ticker) throw new Error("Ticker is required");
  const res = await fetch(`${BASE_URL}/premarket/analyze/${ticker}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Analyze failed: ${errorText}`);
  }

  return await res.json();
}

export async function analyzeMultipleTickers(tickers: string) {
  if (!tickers) throw new Error("Ticker is required");
  const res = await fetch(`${BASE_URL}/premarket/multi_analyze/${tickers}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Analyze failed: ${errorText}`);
  }

  return await res.json();
}

export async function scanNewsForTicker(ticker: string) {
  if (!ticker) throw new Error("Ticker is required");
  const res = await fetch(`${BASE_URL}/scan_news/${ticker}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Scan news failed: ${errorText}`);
  }

  return await res.json();
}

export async function scanNewsBulk(
  from_page: number = 1,
  to_page: number = 5,
  price_threshold: number = 300,
  days_threshold: number = 1
) {
  const res = await fetch(`${BASE_URL}/premarket/scan_news_bulk`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ from_page, to_page, price_threshold, days_threshold }),
  });

  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Bulk scan news failed: ${errorText}`);
  }

  return await res.json();
}

export async function getPositiveNewsTickers() {
  const res = await fetch(`${BASE_URL}/premarket/positive_news`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Get positive news tickers failed: ${errorText}`);
  }

  return await res.json() as {
    ticker: string;
    headline: string;
    verdict: string;
    reason: string;
    created_at: string;
  }[];
}

export async function fetchSavedPremarketAnalysis(ticker: string) {
  const res = await fetch(`${BASE_URL}/premarket/saved_analysis/${ticker}`);
  if (!res.ok) throw new Error(`Failed to fetch saved analysis for ${ticker}`);
  return await res.json();
}

export async function fetchSetNote(ticker: string, note: string) {
  const res = await fetch(`${BASE_URL}/premarket/set_note/${ticker}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ note }),
  });
  if (!res.ok) throw new Error(`Failed to set note for ${ticker}`);
}

export async function getLatestTradingDay(): Promise<string> {
  const res = await fetch(`${BASE_URL}/premarket/latest_trading_day`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Get latest trading day failed: ${errorText}`);
  }

  return await res.text(); // since it's a plain ISO date string like "2025-08-01"
}

export interface TickerInfo {
  ticker: string;
  name: string;
  current_price: number;
}

export async function getWatchlist(): Promise<TickerInfo[]> {
  const res = await fetch(`${BASE_URL}/premarket/get_watchlist`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Get watchlist failed: ${errorText}`);
  }

  const data = await res.json();
  return data.watchlist; // already an array of TickerInfo
}

export async function addToWatchlistBatch(tickerInput: string): Promise<string[]> {
  const params = new URLSearchParams({ tickers_str: tickerInput });

  const res = await fetch(`${BASE_URL}/premarket/add_watchlist_batch?${params.toString()}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Add to watchlist failed: ${errorText}`);
  }

  const data = await res.json();
  return data.added; // return array of successfully added tickers
}


export async function removeFromWatchlist(ticker: string): Promise<void> {
  await fetch(`${BASE_URL}/premarket/watchlist/${ticker}`, { method: "DELETE" });
}

export async function watchStock(ticker: string) {
  const res = await fetch(`${BASE_URL}/premarket/${ticker}/watch_stock`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Failed to watch stock");
  return await res.json();
}

export async function unwatchStock(ticker: string) {
  const res = await fetch(`${BASE_URL}/premarket/${ticker}/unwatch_stock`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Failed to unwatch stock");
  return await res.json();
}

export async function analyzeLiveStock(
  ticker: string,
  rawYahooJson: object,
  top_n = 3,
  model = "gpt-4o"
): Promise<any> {
  const res = await fetch(`${BASE_URL}/premarket/analyze_live/${ticker}?top_n=${top_n}&model=${model}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ raw_yahoo_json: rawYahooJson }),
  });

  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Analyze live failed: ${res.status} ${errorText}`);
  }
  return await res.json();
}

export async function scanSpikedStocks(
  price_threshold = 300,
  from_page = 1,
  to_page = 5
) {
  const res = await fetch(`${BASE_URL}/premarket/spiked_scan`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      price_threshold,
      from_page,
      to_page,
    }),
  });

  if (!res.ok) throw new Error("Spiked stock scan failed");
  return await res.json();
}

export async function startMarketNewsScanner(
  interval_minutes = 1,
  limit = 30
) {
  const res = await fetch(`${BASE_URL}/premarket/start_market_news_scanner`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      interval_minutes,
      limit,
    }),
  });

  if (!res.ok) throw new Error("Failed to start market news scanner");
  return await res.json();
}

export async function stopMarketNewsScanner() {
  const res = await fetch(`${BASE_URL}/premarket/stop_market_news_scanner`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!res.ok) throw new Error("Failed to stop market news scanner");
  return await res.json();
}

export async function scanFlatStocks(
  price_threshold = 300,
  from_page = 1,
  to_page = 40
) {
  const res = await fetch(`${BASE_URL}/premarket/flat_scan`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      price_threshold,
      from_page,
      to_page,
    }),
  });

  if (!res.ok) throw new Error("Flat stock scan failed");
  return await res.json();
}
