from typing import Optional
from sqlalchemy.orm import Session
from app.models import DailyPrice
from datetime import date
import logging

# Adjust this to how many days of candles you want to inspect (usually 3–5)
CANDLE_LOOKBACK = 5

# Thresholds tuned for price < 300 yen stocks with volume surge
MIN_BODY_SIZE = 0.5  # minimum absolute candle body size in yen to count as valid
BODY_RATIO_THRESHOLD = 1.1  # second candle must be at least 10% larger than first

logger = logging.getLogger(__name__)

def get_recent_candles(db: Session, ticker: str, limit: int = CANDLE_LOOKBACK) -> list[dict]:
    """Fetch recent OHLC data for the ticker, sorted from latest to oldest."""
    prices = (
        db.query(DailyPrice)
        .filter(DailyPrice.ticker == ticker)
        .order_by(DailyPrice.date.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "date": p.date,
            "open": p.open,
            "high": p.high,
            "low": p.low,
            "close": p.close,
        }
        for p in prices
    ]

def body_size(candle: dict) -> float:
    return abs(candle["close"] - candle["open"])

def detect_candle_pattern(price_data: list[dict]) -> Optional[str]:
    """Detects basic candlestick patterns from OHLC data, with size thresholds."""
    if len(price_data) < 2:
        return None

    # Most recent candles
    c0 = price_data[0]  # today
    c1 = price_data[1]  # yesterday
    c2 = price_data[2] if len(price_data) >= 3 else None
    print(c0, c1, c2)

    # Helper lambdas
    is_bullish = lambda c: c["close"] > c["open"]
    is_bearish = lambda c: c["close"] < c["open"]
    is_doji = lambda c: abs(c["close"] - c["open"]) < 0.005 * c["close"]
    is_hammer = lambda c: (
        (c["high"] - c["low"]) > 2 * abs(c["close"] - c["open"])
        and (min(c["close"], c["open"]) - c["low"]) > 1.5 * abs(c["close"] - c["open"])
    )

    # Pattern 1: Bullish Engulfing with body size check
    if is_bearish(c1) and is_bullish(c0):
        if c0["open"] < c1["close"] and c0["close"] > c1["open"]:
            if body_size(c0) >= MIN_BODY_SIZE and body_size(c0) >= body_size(c1) * BODY_RATIO_THRESHOLD:
                return "bullish_engulfing"

    # Pattern 2: Bearish Engulfing with body size check
    if is_bullish(c1) and is_bearish(c0):
        if c0["open"] > c1["close"] and c0["close"] < c1["open"]:
            if body_size(c0) >= MIN_BODY_SIZE and body_size(c0) >= body_size(c1) * BODY_RATIO_THRESHOLD:
                return "bearish_engulfing"

    # Pattern 3: 3 consecutive bullish
    if c2 and all(is_bullish(c) for c in [c0, c1, c2]):
        return "3_bullish"

    # Pattern 4: 3 consecutive bearish
    if c2 and all(is_bearish(c) for c in [c0, c1, c2]):
        return "3_bearish"

    # Pattern 5: Doji
    if is_doji(c0):
        return "doji"

    # Pattern 6: Hammer
    if is_hammer(c0):
        return "hammer"

    return None

def analyze_candle_pattern_for_ticker(db: Session, ticker: str) -> dict:
    """Main entry point: fetch candles, detect pattern, return info."""
    try:
        candles = get_recent_candles(db, ticker)
        if not candles:
            logger.warning(f"No candle data found for ticker {ticker}")
            return {"ticker": ticker, "candle_pattern": None}

        pattern = detect_candle_pattern(candles)

        return {
            "ticker": ticker,
            "candle_pattern": pattern,
            "latest_date": candles[0]["date"] if candles else None,
        }

    except Exception as e:
        logger.error(f"Error analyzing candles for {ticker}: {e}")
        return {"ticker": ticker, "candle_pattern": None}
