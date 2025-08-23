from http import client
import json
import os
import re
import httpx
from datetime import datetime, time as dt_time
import time
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session
from typing import Dict
import openai

from app.models import DailyPrice, DailyVolume, VolumeSnapshot
from app.utils.premarket.pre_gpt_analyzer import check_market_hours, analyze_ticker_by_steps

openai.api_key = os.getenv("OPENAI_API_KEY")

def parse_yahoo_intraday(raw_json: dict):
    try:
        result = raw_json["chart"]["result"][0]
        timestamps = result.get("timestamp", [])
        quote = result.get("indicators", {}).get("quote", [{}])[0]
        opens = quote.get("open", [])
        highs = quote.get("high", [])
        lows = quote.get("low", [])
        closes = quote.get("close", [])
        volumes = quote.get("volume", [])

        candles = []
        for i, ts in enumerate(timestamps):
            candles.append({
                "timestamp": ts,
                "open": opens[i] if i < len(opens) else None,
                "high": highs[i] if i < len(highs) else None,
                "low": lows[i] if i < len(lows) else None,
                "close": closes[i] if i < len(closes) else None,
                "volume": volumes[i] if i < len(volumes) else None,
            })
        return candles
    except Exception as e:
        print(f"Error parsing intraday data: {e}")
        return None

def format_top_news(top_news):
    lines = []
    for news in top_news:
        dt_str = news.get("published_at", "")[:16].replace("T", " ")  # e.g. "2025-08-09 08:50"
        category = news.get("category", "N/A")
        headline = news.get("headline", "").strip()
        verdict = news.get("impact_verdict", "N/A")
        reason = news.get("impact_reason", "").strip()
        url = news.get("url", "")

        line = f"- **{dt_str} [{category}]**: [{headline}]({url})  \n  Verdict: {verdict}  \n  Reason: {reason}"
        lines.append(line)
    return "\n".join(lines)

def analyze_live_ticker(
    db: Session,
    ticker: str,
    top_n: int = 3,
    model: str = "gpt-4o",
    raw_yahoo_json: dict = None
):
    analyze_intraday = check_market_hours(db)

    # 1️⃣ Get previous day snapshot
    vs = (
        db.query(VolumeSnapshot)
        .filter(VolumeSnapshot.ticker == ticker)
        .order_by(VolumeSnapshot.detected_at.desc())
        .first()
    )

    if not vs or not vs.reasoning:
        analyze_ticker_by_steps(
            db=db,
            ticker=ticker,
            top_n=top_n,
            model=model,
            analyze_intraday=analyze_intraday
        )
        vs = (
            db.query(VolumeSnapshot)
            .filter(VolumeSnapshot.ticker == ticker)
            .order_by(VolumeSnapshot.detected_at.desc())
            .first()
        )

    # Get recent daily price and volume history
    recent_prices = (
        db.query(DailyPrice)
        .filter(DailyPrice.ticker == ticker)
        .order_by(DailyPrice.date.desc())
        .limit(15)
        .all()
    )
    daily_volumes = (
        db.query(DailyVolume)
        .filter(DailyVolume.ticker == ticker)
        .order_by(DailyVolume.date.desc())
        .limit(15)
        .all()
    )

    # 2️⃣ Intraday data and interval choice
    now = datetime.now(tz=ZoneInfo("Asia/Tokyo")).time()
    interval = "1m" if dt_time(9, 0) <= now <= dt_time(10, 0) else "5m"

    intraday_data = []
    if raw_yahoo_json:
        if "raw_yahoo_json" in raw_yahoo_json:
            raw_yahoo_json = raw_yahoo_json["raw_yahoo_json"]
        intraday_data = parse_yahoo_intraday(raw_yahoo_json) or []

    # Format price history string
    price_history_str = "\n".join(
        f"- {p.date.strftime('%Y-%m-%d')}: Open {p.open}, High {p.high}, Low {p.low}, Close {p.close}"
        for p in reversed(recent_prices)
    )
    # Format daily volume string
    volume_history_str = "\n".join(
        f"- {v.date.strftime('%Y-%m-%d')}: Volume {v.volume}"
        for v in reversed(daily_volumes)
    )

    # Parse top_news safely from string JSON or use as is
    if isinstance(vs.top_news, str):
        try:
            top_news_list = json.loads(vs.top_news)
        except json.JSONDecodeError:
            top_news_list = []
    else:
        top_news_list = vs.top_news or []

    formatted_top_news = format_top_news(top_news_list)

    # Format intraday summary string (time formatted JST)
    intraday_summary = "\n".join(
        f"- {datetime.fromtimestamp(candle['timestamp'], tz=ZoneInfo('Asia/Tokyo')).strftime('%H:%M')}: "
        f"Open {candle['open']}, High {candle['high']}, Low {candle['low']}, Close {candle['close']}, Volume {candle['volume']}"
        for candle in intraday_data if candle['open'] is not None
    )

#     gpt_prompt = f"""
# You are a professional market analyst focused on intraday trading for the Japanese stock market.

# Today’s market context for {ticker}:

# Previous day summary:
# Ticker: {vs.ticker}
# Name: {vs.name}
# Reasoning: {vs.reasoning}
# Top news (recent highlights):
# {formatted_top_news}

# Recent daily prices (last {len(recent_prices)} days):
# {price_history_str}

# Recent daily volumes (last {len(daily_volumes)} days):
# {volume_history_str}

# Current intraday situation (interval={interval}):
# {intraday_summary}

# Please provide a focused, actionable analysis strictly about *today’s* market reaction and *immediate recommendations* for an investor considering this stock.

# Use the markdown format below exactly, with concise, clear points suitable for quick decision-making:

# ### Today’s Market Reaction
# 1. **News and Sentiment Impact:** Briefly summarize how recent news and sentiment are affecting price and volume today.
# 2. **Price and Volume Behavior:** Key observations on intraday price moves and volume spikes.
# 3. **Overall Market Reaction:** What is the market signaling right now?

# ### Immediate Investor Actions
# 1. **Entry Worthiness (0-100):** Rate how favorable it is to enter or add to this position *today*, with clear reasoning.
# 2. **Next Steps:** Specific, actionable advice (e.g., wait for pullback, set alerts, partial entry, move for other stocks).
# 3. **Key Price Levels:** Important support, resistance, or pivot points to watch during today’s session.
# 4. **Risk Management:** Highlight any potential risks or warning signs for today.

# ### Summary
# A concise 2-3 sentence summary focusing on what the investor should do today.

# """
    gpt_prompt = f"""
    You are a professional intraday market analyst for the Japanese stock market. Focus especially on *today's* intraday data.

    Context for {ticker}:

    Previous day summary:
    Ticker: {vs.ticker}
    Name: {vs.name}
    Reasoning: {vs.reasoning}

    Top news (recent highlights):
    {formatted_top_news}

    Recent daily prices (last {len(recent_prices)} days):
    {price_history_str}

    Recent daily volumes (last {len(daily_volumes)} days):
    {volume_history_str}

    Current intraday situation (interval={interval}):
    {intraday_summary}

    --- TASK (be concise and decisive) ---
    The user wants to understand whether current intraday or upcoming price action is likely to be:
    - Pre-spike setup (hasn’t spiked yet, but signs point to possible strong move today, e.g., at market open),
    - Profit-taking (initial spike followed by selling pressure),
    - Re-spike (second or follow-through spike after an earlier surge, triggered by fresh buying or news),
    - Continuation (sustained buying trend, structural recovery, or strong uptrend resuming).

    Based on the intraday candles and volumes provided, do the following *in this exact order and format*:

    #### 0) **Today’s Market Reaction**
      - News and Sentiment Impact: Briefly summarize how recent news and sentiment are affecting price and volume today. Evaluate whether the news is a strong catalyst or not.
      - Price and Volume Behavior: Note any key intraday price moves and volume spikes (including premarket if relevant).
      - Overall Market Reaction: Conclude with what the market seems to be signaling right now (e.g., bullish follow-through, uncertainty, exhaustion, accumulation).  

    #### 1) **Spike Classification** — pick one label from:
      - `profit_taking`
      - `re-spike`
      - `genuine_recovery`
      - `uncertain`
      Provide a short justification (1–2 sentences).

    #### 2) **Is it likely to rise again soon?** — answer `yes` / `no` / `uncertain`. Give a one-sentence reason tied to intraday evidence (volume, higher highs/lows, follow-through, presence/absence of reversal candles).

    #### 3) **Action Recommendation (single-line)** — choose one action:
      - `enter_now` (explain position sizing and stop),
      - `wait_for_pullback` (specify pullback target or confirmation),
      - `partial_scale_in` (how much now, how much wait),
      - `avoid` (reason).
      Include a **confidence score (0-100)** and a 1-line reason.

    #### 4) **Top 3 signals / checklist used** — bullet list (each 1 short line) of the most important signals you used from the intraday data (e.g., "volume spike 3x average at 10:20", "2 consecutive higher closes after spike", "long upper wick at 11:05").

    #### 5) **Key price levels to watch** — list support and resistance (exact price levels) for today.

    #### 6) **Minimal trade plan (if recommending entry)** — entry price / stop-loss / initial target / sizing note (or blank if not entering).
    
    """

    print(f"===prompt={gpt_prompt}")

    try:
        response = openai.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": gpt_prompt}],
            temperature=0.3,
        )
        analysis = response.choices[0].message.content.strip()

        # Simple parse of GPT response sections
        sections = re.split(r'\n### ', analysis)
        parsed_analysis = {}
        for sec in sections:
            if not sec.strip():
                continue
            lines = sec.split('\n', 1)
            header = lines[0].strip(': ')
            content = lines[1].strip() if len(lines) > 1 else ""
            parsed_analysis[header] = content

        return {
            "ticker": ticker,
            "interval": interval,
            "intraday_candles": intraday_data,
            "analysis_raw": analysis,
            "analysis_parsed": parsed_analysis,
        }

    except Exception as e:
        analysis = f"Error during GPT analysis: {e}"
        return {
            "ticker": ticker,
            "interval": interval,
            "intraday_candles": intraday_data,
            "analysis_raw": analysis,
            "analysis_parsed": {},
        }
