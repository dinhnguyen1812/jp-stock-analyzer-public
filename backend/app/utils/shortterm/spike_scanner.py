import datetime
from sqlalchemy.orm import Session
from app.models import DailyPrice
from .price_updater import fetch_and_save_price_history
from .volume_surge_scraper import scan_and_save_volume_surges
from .kabutan_news_ticker import scrape_kabutan_news, get_volume_info
import openai
from typing import List, Dict
import os
from app.schemas import ScanParams

def detect_recent_downtrend(db: Session, ticker: str, days: int = 30) -> dict:
    """
    Detects if there's been a significant downtrend in the last `days`.
    Returns dict with result, percentage drop, and date range.
    """
    # Ensure we have enough data
    fetch_and_save_price_history(db, ticker, max_days=150)

    # Date range
    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=days + 5)

    prices = (
        db.query(DailyPrice)
        .filter(DailyPrice.ticker == ticker, DailyPrice.date >= start_date)
        .order_by(DailyPrice.date.asc())
        .all()
    )

    if not prices or len(prices) < 10:
        return {
            "ticker": ticker,
            "had_downtrend": False,
            "drop_pct": 0.0,
            "from_date": None,
            "to_date": None
        }

    close_prices = [p.close for p in prices]
    dates = [p.date for p in prices]

    # Detect biggest drop from peak to trough
    max_drop = 0.0
    start_idx, end_idx = -1, -1

    for i in range(len(close_prices)):
        high = close_prices[i]
        for j in range(i + 1, len(close_prices)):
            low = close_prices[j]
            drop_pct = (low - high) / high * 100
            if drop_pct < max_drop:
                max_drop = drop_pct
                start_idx = i
                end_idx = j

    return {
        "ticker": ticker,
        "had_downtrend": max_drop <= -10,  # example threshold
        "drop_pct": round(max_drop, 2),
        "from_date": dates[start_idx] if start_idx >= 0 else None,
        "to_date": dates[end_idx] if end_idx >= 0 else None
    }

openai.api_key = os.getenv("OPENAI_API_KEY")

def pick_top_news_by_gpt(
    ticker: str,
    news_items: List[Dict],
    model: str = "gpt-3.5-turbo",
    top_n: int = 3
) -> List[Dict]:
    if not news_items or not openai.api_key:
        return []

    headlines = [f"{i+1}. {item['headline']}" for i, item in enumerate(news_items[:20])]

    prompt = f"""
You are a Japanese stock market expert. Analyze the following news headlines for stock {ticker}.  
For each, judge how impactful it is for short-term trading, based on relevance, positivity, and clarity.

### Output Format:
- Return a ranked list of the most impactful headlines (max {top_n})
- For each, include:
    - Verdict (e.g. "Neutral", "Good", "Great", "Decisive")
    - Short reason (max 1 line)

### Headlines:
{chr(10).join(headlines)}
"""

    try:
        res = openai.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": prompt.strip()}
            ],
            temperature=0.3
        )
        content = res.choices[0].message.content.strip()

        # Example expected response parsing
        results = []
        for line in content.splitlines():
            if not line.strip() or not any(word in line for word in ["Good", "Great", "Decisive", "Neutral"]):
                continue
            parts = line.split(":", 1)
            if len(parts) != 2:
                continue
            idx = int(parts[0].strip().split(".")[0]) - 1
            verdict_reason = parts[1].strip().split(" - ")
            verdict = verdict_reason[0].strip()
            reason = verdict_reason[1].strip() if len(verdict_reason) > 1 else ""
            if 0 <= idx < len(news_items):
                results.append({
                    "headline": news_items[idx]["headline"],
                    "url": news_items[idx].get("url"),
                    "verdict": verdict,
                    "reason": reason
                })
            if len(results) >= top_n:
                break

        return results

    except Exception as e:
        print(f"❌ GPT news analysis failed: {e}")
        return []

def volume_surge_news_downtrend_scan(
    params: ScanParams,
    db: Session
):
    # Step 1: Scan and save volume surge data
    tickers = scan_and_save_volume_surges(
        db=db,
        surge_threshold=params.surge_threshold,
        price_threshold=params.price_threshold,
        from_page=params.from_page,
        to_page=params.to_page,
    )

    results = []

    for ticker in tickers:
        # Step 2: Get latest volume surge info
        volume_info = get_volume_info(db, ticker)
        if not volume_info:
            print(f"⚠️ No volume info for {ticker}, skipping.")
            continue

        # Step 3: Detect recent downtrend in last 30 days
        downtrend_info = detect_recent_downtrend(db, ticker, days=30)

        # Step 4: Scrape news for ticker
        news_items = scrape_kabutan_news(ticker, limit=20)
        if not news_items:
            print(f"⚠️ No news found for {ticker}, skipping GPT news pick.")
            top_news = []
        else:
            # Step 5: Pick top news using GPT (returns verdicts)
            top_news = pick_top_news_by_gpt(ticker, news_items, top_n=3)

        results.append({
            "ticker": ticker,
            "volume_info": {
                "current_price": volume_info.current_price,
                "volume_rate": volume_info.volume_rate,
                "money_flow_rate": volume_info.money_flow_rate,
                "detected_at": volume_info.detected_at.isoformat(),
            },
            "downtrend": downtrend_info,
            "top_news": top_news,
        })

    return {
        "message": f"Scan complete. {len(tickers)} tickers scanned.",
        "results": results
    }