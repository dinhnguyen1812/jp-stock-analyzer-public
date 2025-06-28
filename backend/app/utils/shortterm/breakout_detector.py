from typing import Dict, List
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models import DailyPrice

def detect_breakout(db: Session, ticker: str, lookback_days: int = 20) -> Dict:
    """
    Detect price breakout using the last N+1 daily price records from DB.
    Assumes price data already exists in DB.
    """
    required_days = lookback_days + 1

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

    today = price_list[0]
    resistance = max(day["high"] for day in price_list[1:])  # exclude today

    breakout = today["close"] > resistance

    return {
        "breakout_detected": breakout,
        "resistance_level": resistance,
        "close_today": today["close"],
        "date": today["date"]
    }
