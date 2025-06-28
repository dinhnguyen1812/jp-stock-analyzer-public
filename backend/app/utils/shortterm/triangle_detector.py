from typing import Optional, Dict
from sqlalchemy.orm import Session
from app.models import DailyPrice
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

def fetch_price_data(db: Session, ticker: str, lookback: int = 60) -> Optional[pd.DataFrame]:
    """
    Fetch OHLC data for the ticker from DB.
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
        "high": r.high,
        "low": r.low,
        "close": r.close,
    } for r in rows])
    df.set_index("date", inplace=True)
    return df

def linreg_slope(y: pd.Series) -> float:
    x = np.arange(len(y))
    A = np.vstack([x, np.ones(len(x))]).T
    slope, _ = np.linalg.lstsq(A, y.values, rcond=None)[0]
    return slope

def detect_triangle_pattern(df: pd.DataFrame, slope_threshold: float = 0.1) -> Optional[Dict]:
    """
    Detect ascending, descending, or symmetrical triangle.
    """
    highs = df["high"]
    lows = df["low"]

    high_slope = linreg_slope(highs)
    low_slope = linreg_slope(lows)

    triangle_type = None

    # Classify triangle type
    if abs(high_slope) < slope_threshold and low_slope > slope_threshold:
        triangle_type = "ascending_triangle"
    elif abs(low_slope) < slope_threshold and high_slope < -slope_threshold:
        triangle_type = "descending_triangle"
    elif high_slope < -slope_threshold and low_slope > slope_threshold:
        triangle_type = "symmetrical_triangle"
    else:
        return None  # no pattern

    return {
        "pattern": triangle_type,
        "slopes": {
            "high_slope": round(high_slope, 4),
            "low_slope": round(low_slope, 4)
        },
        "start_date": str(df.index[0]),
        "end_date": str(df.index[-1]),
        "duration_days": (df.index[-1] - df.index[0]).days,
    }

def detect_triangle_for_ticker(db: Session, ticker: str, lookback: int = 60) -> Dict:
    """
    Main function to detect triangle pattern for a given ticker.
    """
    df = fetch_price_data(db, ticker, lookback)
    if df is None or df.empty:
        return {"ticker": ticker, "pattern_detected": False, "reason": "No price data"}

    pattern_info = detect_triangle_pattern(df)

    if pattern_info:
        return {
            "ticker": ticker,
            "pattern_detected": True,
            "pattern_info": pattern_info
        }
    else:
        return {"ticker": ticker, "pattern_detected": False}
from typing import Optional, Dict
from sqlalchemy.orm import Session
from app.models import DailyPrice
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

def fetch_price_data(db: Session, ticker: str, lookback: int = 60) -> Optional[pd.DataFrame]:
    """
    Fetch OHLC data for the ticker from DB.
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
        "high": r.high,
        "low": r.low,
        "close": r.close,
    } for r in rows])
    df.set_index("date", inplace=True)
    return df

def linreg_slope(y: pd.Series) -> float:
    x = np.arange(len(y))
    A = np.vstack([x, np.ones(len(x))]).T
    slope, _ = np.linalg.lstsq(A, y.values, rcond=None)[0]
    return slope

def detect_triangle_pattern(df: pd.DataFrame, slope_threshold: float = 0.1) -> Optional[Dict]:
    """
    Detect ascending, descending, or symmetrical triangle.
    """
    highs = df["high"]
    lows = df["low"]

    high_slope = linreg_slope(highs)
    low_slope = linreg_slope(lows)

    triangle_type = None

    # Classify triangle type
    if abs(high_slope) < slope_threshold and low_slope > slope_threshold:
        triangle_type = "ascending_triangle"
    elif abs(low_slope) < slope_threshold and high_slope < -slope_threshold:
        triangle_type = "descending_triangle"
    elif high_slope < -slope_threshold and low_slope > slope_threshold:
        triangle_type = "symmetrical_triangle"
    else:
        return None  # no pattern

    return {
        "pattern": triangle_type,
        "slopes": {
            "high_slope": round(high_slope, 4),
            "low_slope": round(low_slope, 4)
        },
        "start_date": str(df.index[0]),
        "end_date": str(df.index[-1]),
        "duration_days": (df.index[-1] - df.index[0]).days,
    }

def detect_triangle_for_ticker(db: Session, ticker: str, lookback: int = 60) -> Dict:
    """
    Main function to detect triangle pattern for a given ticker.
    """
    df = fetch_price_data(db, ticker, lookback)
    if df is None or df.empty:
        return {"ticker": ticker, "pattern_detected": False, "reason": "No price data"}

    pattern_info = detect_triangle_pattern(df)

    if pattern_info:
        return {
            "ticker": ticker,
            "pattern_detected": True,
            "pattern_info": pattern_info
        }
    else:
        return {"ticker": ticker, "pattern_detected": False}
