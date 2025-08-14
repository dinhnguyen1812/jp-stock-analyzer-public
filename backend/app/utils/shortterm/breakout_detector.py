from typing import Dict, List
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models import DailyPrice
from app.utils.shortterm.volume_surge_scraper import fetch_intraday_prices  # ✅ import

def detect_breakout(db: Session, ticker: str, lookback_days: int = 20) -> Dict:
    """
    Detect price breakout using the last N daily price records and today's current intraday price.
    """
    required_days = lookback_days

    price_data: List[DailyPrice] = (
        db.query(DailyPrice)
        .filter(DailyPrice.ticker == ticker)
        .order_by(desc(DailyPrice.date))
        .limit(required_days)
        .all()
    )

    if len(price_data) < required_days:
        return {"breakout_detected": False, "reason": "Not enough price data in DB"}

    price_list = [{
        "date": p.date,
        "open": p.open,
        "high": p.high,
        "low": p.low,
        "close": p.close
    } for p in price_data]

    resistance = max(day["high"] for day in price_list)

    # ✅ Fetch current intraday price
    current_price, _, _, _ = fetch_intraday_prices(ticker)
    if current_price is None:
        return {"breakout_detected": False, "reason": "Failed to fetch current price"}

    today = price_list[0]
    breakout = max(current_price, today["close"]) > resistance

    return {
        "breakout_detected": breakout,
        "resistance_level": resistance,
        "current_price": current_price,
        "date": price_list[0]["date"]
    }
