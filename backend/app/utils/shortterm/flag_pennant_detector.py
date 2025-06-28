from typing import Optional, Dict
from sqlalchemy.orm import Session
from app.models import DailyPrice
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

def fetch_price_data(db: Session, ticker: str, lookback: int = 40) -> Optional[pd.DataFrame]:
    """
    Fetch OHLC data for the ticker, sorted ascending by date.
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

def detect_flags_pennants(df: pd.DataFrame, flagpole_min_pct: float = 0.1, consolidation_max_range: float = 0.05) -> Optional[Dict]:
    """
    Detect Flags or Pennants pattern in price data.

    - flagpole_min_pct: minimum % price move to consider a flagpole (e.g., 10%)
    - consolidation_max_range: max price range during consolidation as % of flagpole height (e.g., 5%)

    Returns dict with pattern info or None if not found.
    """

    closes = df["close"]

    if len(df) < 20:
        return None  # Not enough data

    # Step 1: Find strong recent move (flagpole)
    # Use last ~15 days to find sharp move
    lookback_flagpole = 15
    recent = closes[-lookback_flagpole:]
    start_price = recent.iloc[0]
    end_price = recent.iloc[-1]
    move_pct = (end_price - start_price) / start_price

    if abs(move_pct) < flagpole_min_pct:
        # No strong enough move
        return None

    # Step 2: Check consolidation after strong move
    # Consolidation = next ~10 days after flagpole start
    consolidation_window = 10
    if len(df) < lookback_flagpole + consolidation_window:
        return None  # Not enough data for consolidation

    consolidation = closes[-(lookback_flagpole + consolidation_window):-lookback_flagpole]

    # Price range in consolidation
    price_range = consolidation.max() - consolidation.min()
    if price_range / abs(end_price - start_price) > consolidation_max_range:
        # Too wide consolidation, not a flag/pennant
        return None

    # Step 3: Determine pattern type by shape of consolidation
    highs = df["high"][-(lookback_flagpole + consolidation_window):-lookback_flagpole]
    lows = df["low"][-(lookback_flagpole + consolidation_window):-lookback_flagpole]

    # Calculate linear regression slopes for highs and lows to see if converging (pennant) or parallel (flag)
    def linreg_slope(series):
        x = np.arange(len(series))
        y = series.values
        A = np.vstack([x, np.ones(len(x))]).T
        slope, _ = np.linalg.lstsq(A, y, rcond=None)[0]
        return slope

    slope_high = linreg_slope(highs)
    slope_low = linreg_slope(lows)

    pattern_type = "flag"
    # If slopes are converging (one positive, one negative), likely pennant
    if slope_high * slope_low < 0:
        pattern_type = "pennant"

    return {
        "pattern": f"{pattern_type}_pattern",
        "flagpole_pct_move": round(move_pct * 100, 2),
        "consolidation_range_pct_of_flagpole": round(price_range / abs(end_price - start_price) * 100, 2),
        "slopes": {"high_slope": slope_high, "low_slope": slope_low},
        "flagpole_start_price": round(start_price, 2),
        "flagpole_end_price": round(end_price, 2),
        "consolidation_start": str(consolidation.index[0]),
        "consolidation_end": str(consolidation.index[-1]),
    }

def detect_flags_pennants_for_ticker(db: Session, ticker: str, lookback: int = 40) -> Dict:
    """
    Fetch price data and detect flags/pennants pattern.
    """
    df = fetch_price_data(db, ticker, lookback)
    if df is None or df.empty:
        return {"ticker": ticker, "pattern_detected": False, "reason": "No price data"}

    pattern_info = detect_flags_pennants(df)

    if pattern_info:
        return {"ticker": ticker, "pattern_detected": True, "pattern_info": pattern_info}
    else:
        return {"ticker": ticker, "pattern_detected": False}
