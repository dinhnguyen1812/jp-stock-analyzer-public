from typing import Optional, Dict
from sqlalchemy.orm import Session
from app.models import DailyPrice
import pandas as pd
import pandas_ta as ta
import logging

logger = logging.getLogger(__name__)

def fetch_price_data(db: Session, ticker: str, lookback: int = 250) -> Optional[pd.DataFrame]:
    """
    Fetch OHLC data for the ticker from DB, returns a DataFrame sorted by date ascending.
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

def calculate_technical_indicators(df: pd.DataFrame) -> Dict:
    """
    Calculate RSI, MACD, Bollinger Bands, SMA/EMA crossovers from price data.
    Returns a dictionary of indicator values for the most recent date.
    """

    # RSI (14)
    df["rsi"] = ta.rsi(df["close"], length=14)

    # MACD (12, 26, 9)
    macd = ta.macd(df["close"], fast=12, slow=26, signal=9)
    df = pd.concat([df, macd], axis=1)

    # Bollinger Bands (20, 2 std)
    bbands = ta.bbands(df["close"], length=20, std=2)
    df = pd.concat([df, bbands], axis=1)

    # SMA and EMA
    df["sma_50"] = ta.sma(df["close"], length=50)
    df["sma_200"] = ta.sma(df["close"], length=200)
    df["ema_20"] = ta.ema(df["close"], length=20)

    # Safely get latest and previous rows
    if len(df) < 2:
        logger.warning("Not enough data to calculate SMA crossover")
        latest = df.iloc[-1]
        prev = df.iloc[-1]
    else:
        latest = df.iloc[-1]
        prev = df.iloc[-2]

    # Detect SMA crossover
    sma_crossover = "none"
    if (
        pd.notna(prev["sma_50"]) and pd.notna(prev["sma_200"]) and
        pd.notna(latest["sma_50"]) and pd.notna(latest["sma_200"])
    ):
        if prev["sma_50"] < prev["sma_200"] and latest["sma_50"] > latest["sma_200"]:
            sma_crossover = "golden_cross"
        elif prev["sma_50"] > prev["sma_200"] and latest["sma_50"] < latest["sma_200"]:
            sma_crossover = "death_cross"

    return {
        "rsi": round(latest["rsi"], 2) if pd.notna(latest["rsi"]) else None,
        "macd": {
            "macd_line": round(latest["MACD_12_26_9"], 4) if pd.notna(latest["MACD_12_26_9"]) else None,
            "signal_line": round(latest["MACDs_12_26_9"], 4) if pd.notna(latest["MACDs_12_26_9"]) else None,
            "histogram": round(latest["MACDh_12_26_9"], 4) if pd.notna(latest["MACDh_12_26_9"]) else None,
        },
        "bollinger_bands": {
            "middle": round(latest["BBM_20_2.0"], 2) if pd.notna(latest["BBM_20_2.0"]) else None,
            "upper": round(latest["BBU_20_2.0"], 2) if pd.notna(latest["BBU_20_2.0"]) else None,
            "lower": round(latest["BBL_20_2.0"], 2) if pd.notna(latest["BBL_20_2.0"]) else None,
            "current_price": round(latest["close"], 2),
        },
        "moving_averages": {
            "sma_50": round(latest["sma_50"], 2) if pd.notna(latest["sma_50"]) else None,
            "sma_200": round(latest["sma_200"], 2) if pd.notna(latest["sma_200"]) else None,
            "ema_20": round(latest["ema_20"], 2) if pd.notna(latest["ema_20"]) else None,
        },
        "sma_crossover": sma_crossover,
    }

def get_technical_indicators(db: Session, ticker: str) -> Optional[Dict]:
    """
    Main function: fetch price data and calculate indicators.
    Returns dict or None if no data.
    """
    df = fetch_price_data(db, ticker)
    if df is None or df.empty:
        return None

    return calculate_technical_indicators(df)
