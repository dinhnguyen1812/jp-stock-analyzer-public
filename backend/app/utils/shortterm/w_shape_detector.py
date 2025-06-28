from typing import Optional, Dict
from sqlalchemy.orm import Session
from app.models import DailyPrice
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

def fetch_price_data(db: Session, ticker: str, lookback: int = 80) -> Optional[pd.DataFrame]:
    """
    Fetch OHLC data for the ticker, sorted by date ascending.
    """
    rows = (
        db.query(DailyPrice)
        .filter(DailyPrice.ticker == ticker)
        .order_by(DailyPrice.date.asc())
        .limit(lookback)
        .all()
    )
    if not rows:
        logger.warning(f"No price data found for ticker {ticker}")
        return None

    df = pd.DataFrame([{
        "date": r.date,
        "open": r.open,
        "high": r.high,
        "low": r.low,
        "close": r.close,
    } for r in rows])

    df.set_index("date", inplace=True)
    return df

def detect_w_shape(df: pd.DataFrame, tolerance: float = 0.03) -> Optional[Dict]:
    """
    Detect a W-shape (Double Bottom) pattern in price data.

    tolerance: max relative difference allowed between bottoms (3% default).

    Returns dict with pattern info if detected, else None.
    """

    lows = df["low"]

    # Find local minima (bottoms) and maxima (peaks)
    local_min_idx = (lows.shift(1) > lows) & (lows.shift(-1) > lows)
    bottoms = lows[local_min_idx]

    if len(bottoms) < 2:
        return None  # Need at least two bottoms

    # Scan pairs of bottoms for "W" shape
    for i in range(len(bottoms) - 1):
        first_bottom_date = bottoms.index[i]
        second_bottom_date = bottoms.index[i + 1]

        # Middle peak must be between bottoms
        middle_range = df.loc[first_bottom_date:second_bottom_date]
        middle_peak = middle_range["high"].max()
        middle_peak_date = middle_range["high"].idxmax()

        first_bottom_price = bottoms.iloc[i]
        second_bottom_price = bottoms.iloc[i + 1]

        # Check bottoms are roughly equal within tolerance
        bottoms_similar = abs(first_bottom_price - second_bottom_price) / min(first_bottom_price, second_bottom_price) <= tolerance

        # Middle peak higher than both bottoms
        peak_higher = middle_peak > first_bottom_price and middle_peak > second_bottom_price

        # Bottoms should be separated enough (e.g. 10+ days apart)
        days_apart = (second_bottom_date - first_bottom_date).days

        if bottoms_similar and peak_higher and days_apart >= 10:
            return {
                "pattern": "w_shape_double_bottom",
                "first_bottom": {"date": str(first_bottom_date), "price": round(first_bottom_price, 2)},
                "middle_peak": {"date": str(middle_peak_date), "price": round(middle_peak, 2)},
                "second_bottom": {"date": str(second_bottom_date), "price": round(second_bottom_price, 2)},
                "days_apart": days_apart,
            }

    return None


def detect_w_shape_for_ticker(db: Session, ticker: str, lookback: int = 80) -> Dict:
    """
    Main function: fetch price data and detect W-shape pattern.
    """
    df = fetch_price_data(db, ticker, lookback)
    if df is None or df.empty:
        return {"ticker": ticker, "pattern_detected": False, "reason": "No price data"}

    pattern_info = detect_w_shape(df)

    if pattern_info:
        return {"ticker": ticker, "pattern_detected": True, "pattern_info": pattern_info}
    else:
        return {"ticker": ticker, "pattern_detected": False}
