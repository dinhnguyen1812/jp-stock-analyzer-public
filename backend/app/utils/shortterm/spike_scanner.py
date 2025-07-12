import datetime
import openai
import os
from typing import List, Dict, Optional
from sqlalchemy.orm import Session

from app.models import DailyPrice, SpikeScan, VolumeSnapshot
from .price_updater import fetch_and_save_price_history
from .volume_surge_scraper import scan_and_save_volume_surges
from .kabutan_news_ticker import scrape_kabutan_news, get_volume_info
from app.schemas import ScanParams

openai.api_key = os.getenv("OPENAI_API_KEY")
JP_TZ = datetime.timezone(datetime.timedelta(hours=9))


def normalize_downtrend_for_json(downtrend: dict) -> dict:
    for key in ["from_date", "to_date"]:
        if isinstance(downtrend.get(key), (datetime.date, datetime.datetime)):
            downtrend[key] = downtrend[key].isoformat()
    return downtrend


def detect_recent_downtrend(db: Session, ticker: str, days: int = 30) -> dict:
    fetch_and_save_price_history(db, ticker, max_days=150)
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
        "had_downtrend": max_drop <= -10,
        "drop_pct": round(max_drop, 2),
        "from_date": dates[start_idx] if start_idx >= 0 else None,
        "to_date": dates[end_idx] if end_idx >= 0 else None
    }


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
            messages=[{"role": "user", "content": prompt.strip()}],
            temperature=0.3
        )
        content = res.choices[0].message.content.strip()
        results = []

        for line in content.splitlines():
            if not line.strip() or not any(w in line for w in ["Good", "Great", "Decisive", "Neutral"]):
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


def compute_price_stats(prices: List[DailyPrice], current_price: float) -> Dict[str, Optional[float]]:
    if not prices:
        return {
            "highest_price": None,
            "lowest_price": None,
            "drop_from_high_pct": None,
            "rebound_from_low_pct": None
        }

    highs = [p.high for p in prices if p.high]
    lows = [p.low for p in prices if p.low]

    if not highs or not lows:
        return {
            "highest_price": None,
            "lowest_price": None,
            "drop_from_high_pct": None,
            "rebound_from_low_pct": None
        }

    highest = max(highs)
    lowest = min(lows)

    drop_from_high = (
        round((highest - current_price) / highest * 100, 2)
        if highest > 0 else None
    )

    rebound_from_low = (
        round((current_price - lowest) / lowest * 100, 2)
        if lowest > 0 else None
    )

    return {
        "highest_price": highest,
        "lowest_price": lowest,
        "drop_from_high_pct": drop_from_high,
        "rebound_from_low_pct": rebound_from_low
    }


def volume_surge_news_downtrend_scan(params: ScanParams, db: Session):
    tickers = scan_and_save_volume_surges(
        db=db,
        surge_threshold=params.surge_threshold,
        price_threshold=params.price_threshold,
        from_page=params.from_page,
        to_page=params.to_page,
    )

    results = []
    now = datetime.datetime.utcnow()
    today_open = datetime.datetime.combine(datetime.date.today(), datetime.time(0, 0))

    for ticker in tickers:
        volume_info = get_volume_info(db, ticker)
        if not volume_info:
            print(f"⚠️ No volume info for {ticker}, skipping.")
            continue

        today_snapshot = (
            db.query(VolumeSnapshot)
            .filter(
                VolumeSnapshot.ticker == ticker,
                VolumeSnapshot.detected_at >= today_open,
                VolumeSnapshot.promising_score != None,
                VolumeSnapshot.promising_score > 30
            )
            .order_by(VolumeSnapshot.detected_at.desc())
            .first()
        )

        if today_snapshot and volume_info.volume_rate < 1.5 * today_snapshot.volume_rate:
            print(f"🛑 {ticker} spike weaker than today's snapshot. Skipped.")
            continue

        existing = db.query(SpikeScan).filter(SpikeScan.ticker == ticker).first()
        if existing and volume_info.volume_rate <= 1.5 * existing.volume_rate:
            print(f"⏭ {ticker} already scanned with similar or stronger volume_rate.")
            continue

        if not existing or not existing.downtrend_checked_at or (now - existing.downtrend_checked_at).total_seconds() > 86400:
            downtrend_info = detect_recent_downtrend(db, ticker)
            downtrend_info = normalize_downtrend_for_json(downtrend_info)
            downtrend_checked_at = now
        else:
            downtrend_info = existing.downtrend
            downtrend_checked_at = existing.downtrend_checked_at

        if not existing or not existing.news_checked_at or (now - existing.news_checked_at).total_seconds() > 3600:
            news_items = scrape_kabutan_news(ticker, limit=20)
            top_news = pick_top_news_by_gpt(ticker, news_items, top_n=3) if news_items else []
            news_checked_at = now
        else:
            top_news = existing.top_news
            news_checked_at = existing.news_checked_at

        if existing:
            existing.volume_rate = volume_info.volume_rate
            existing.money_flow_rate = volume_info.money_flow_rate
            existing.current_price = volume_info.current_price
            existing.detected_at = volume_info.detected_at
            existing.downtrend = downtrend_info
            existing.downtrend_checked_at = downtrend_checked_at
            existing.top_news = top_news
            existing.news_checked_at = news_checked_at
        else:
            db.add(SpikeScan(
                ticker=ticker,
                volume_rate=volume_info.volume_rate,
                money_flow_rate=volume_info.money_flow_rate,
                current_price=volume_info.current_price,
                detected_at=volume_info.detected_at,
                downtrend=downtrend_info,
                downtrend_checked_at=downtrend_checked_at,
                top_news=top_news,
                news_checked_at=news_checked_at,
            ))

        db.commit()

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
        "message": f"Scan complete. {len(results)} tickers scanned.",
        "results": results
    }


def get_all_spike_scans(db: Session) -> List[dict]:
    scans = db.query(SpikeScan).order_by(SpikeScan.updated_at.desc()).all()
    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=30)

    results = []
    for scan in scans:
        prices = (
            db.query(DailyPrice)
            .filter(
                DailyPrice.ticker == scan.ticker,
                DailyPrice.date >= start_date
            )
            .order_by(DailyPrice.date.asc())
            .all()
        )

        price_stats = compute_price_stats(prices, scan.current_price)

        results.append({
            "ticker": scan.ticker,
            "volume_rate": scan.volume_rate,
            "money_flow_rate": scan.money_flow_rate,
            "current_price": scan.current_price,
            "detected_at": scan.detected_at.isoformat() if scan.detected_at else None,
            "downtrend": scan.downtrend,
            "top_news": scan.top_news,
            "updated_at": scan.updated_at.isoformat() if scan.updated_at else None,
            **price_stats
        })

    return results
