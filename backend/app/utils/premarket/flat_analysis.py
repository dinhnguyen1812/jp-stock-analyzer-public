import datetime
from typing import Optional, Dict
from sqlalchemy.orm import Session
import httpx
from bs4 import BeautifulSoup

from app.utils.shortterm.volume_surge_scraper import fetch_intraday_prices
from app.utils.shortterm.price_updater import fetch_and_save_price_history
from app.models import DailyPrice, DailyVolume, FlatAnalysis
from app.utils.shortterm.moneyflow_history import parse_volume
from app.utils.shortterm.volume_5d_average_updater import update_avg_volume_for_ticker


def get_prices_with_intraday_option(
    db: Session,
    ticker: str,
    analyze_intraday: bool = False,
    limit_days: int = 10
) -> list[dict]:
    """
    Fetch the latest `limit_days` from DB (newest first), then return in ascending
    date order (oldest -> newest). Optionally append/overwrite today's intraday.
    """
    # Ensure daily history is up to date
    fetch_and_save_price_history(db, ticker)

    # Get latest N days (newest first), then reverse to ascending
    rows = (
        db.query(DailyPrice)
        .filter(DailyPrice.ticker == ticker)
        .order_by(DailyPrice.date.desc())
        .limit(limit_days)
        .all()
    )
    rows = list(reversed(rows))  # oldest -> newest

    prices = [
        {
            "date": row.date.isoformat(),
            "open": row.open,
            "high": row.high,
            "low": row.low,
            "close": row.close,
        }
        for row in rows
    ]

    # add intraday snapshot
    if analyze_intraday:
        intraday_close, intraday_open, intraday_high, intraday_low = fetch_intraday_prices(ticker)
        prices.append({
            "date": datetime.datetime.now().date().isoformat(),
            "open": intraday_open,
            "high": intraday_high,
            "low": intraday_low,
            "close": intraday_close,
        })

    return prices


def get_volume_with_intraday_option(
    db: Session, ticker: str, analyze_intraday: bool = False, limit_days: int = 10
) -> Optional[list[int]]:
    """
    Get historical daily volumes for a ticker, with optional intraday volume appended.
    - Always fetches the last `limit_days` daily volumes from DB.
    - If analyze_intraday=True: scrape Yahoo Finance and append today's intraday volume.
    
    Returns:
        list[int] = [volume_dayN, ..., volume_last, (intraday_volume if available)]
        None = if no data found
    """
    update_avg_volume_for_ticker(db, ticker)

    # --- Get daily volumes from DB ---
    rows = (
        db.query(DailyVolume)
        .filter_by(ticker=ticker)
        .order_by(DailyVolume.date.desc())
        .limit(limit_days)
        .all()
    )
    if not rows:
        return None

    volumes = [row.volume for row in rows]
    volumes = list(reversed(volumes))

    # --- Optionally add intraday volume ---
    if analyze_intraday:
        url = f"https://finance.yahoo.co.jp/quote/{ticker}.T"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "ja,en;q=0.9",
        }

        try:
            resp = httpx.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # Find 出来高 (volume)
            labels = soup.select("span.DataListItem__name__3RQJ")
            for label in labels:
                if "出来高" in label.text:
                    value_span = label.find_next("span", class_="StyledNumber__value__3rXW")
                    if value_span:
                        raw_volume = value_span.text.strip()
                        if raw_volume not in {"---", "-", ""}:
                            intraday_volume = parse_volume(raw_volume)
                            if intraday_volume:
                                volumes.append(intraday_volume)
                    break

        except Exception as e:
            print(f"⚠️ Failed to fetch intraday volume for {ticker}: {e}")

    return volumes


def analyze_flat_pattern(
    db: Session,
    ticker: str,
    lookback_days: int = 7,
    surge_window_days: int = 2,
    analyze_intraday: bool = False,
) -> Optional[FlatAnalysis]:
    """
    Detects 'flat → small abnormal surge' pattern in the last N days of price/volume.
    Flat = very low volatility with stable/low volume.
    Surge = slight abnormal price rise with higher volume (not a big spike).
    """

    # --- 2. Get prices (with optional intraday) ---
    price_data = get_prices_with_intraday_option(
        db, ticker, analyze_intraday=analyze_intraday, limit_days=lookback_days
    )
    if not price_data:
        return None

    dates = [p["date"] for p in price_data]

    # --- 3. Get volumes aligned with price_data ---
    vols = get_volume_with_intraday_option(
        db, ticker, analyze_intraday=analyze_intraday, limit_days=lookback_days
    )

    # print(f"===price_data = {price_data}\nvols = {vols}")

    # --- 4. Define flat & surge windows ---
    if len(price_data) < surge_window_days + 1:
        return None

    flat_window = price_data[:-surge_window_days]
    surge_window = price_data[-surge_window_days:]

    # --- 5. Flatness metrics (use high/low) ---
    flat_highs = [p["high"] for p in flat_window]
    flat_lows = [p["low"] for p in flat_window]
    flat_volumes = vols[:-surge_window_days]

    flat_range_pct = (
        (max(flat_highs) - min(flat_lows)) / min(flat_lows) * 100
        if flat_highs and flat_lows
        else 0
    )
    flat_avg_vol = sum(flat_volumes) / len(flat_volumes) if flat_volumes else 0

    # --- 6. Surge metrics (use high/low) ---
    surge_highs = [p["high"] for p in surge_window]
    surge_lows = [p["low"] for p in surge_window]
    surge_volumes = vols[-surge_window_days:]

    surge_pct = (
        (max(surge_highs) - surge_lows[0]) / surge_lows[0] * 100
        if surge_highs and surge_lows
        else 0
    )
    surge_vol_avg = sum(surge_volumes) / len(surge_volumes) if surge_volumes else 0
    vol_multiple = surge_vol_avg / flat_avg_vol if flat_avg_vol > 0 else 0

    # --- 7. Detection rules (small abnormal rise only) ---
    pattern_detected = (
        flat_range_pct <= 8
        and 2 <= surge_pct <= 10 and vol_multiple >= 1.5
    )

    # --- 8. Scoring ---
    score = round(surge_pct * vol_multiple, 2) if pattern_detected else 0

    # --- 9. Upsert FlatAnalysis (1 record per ticker) ---
    analysis = db.query(FlatAnalysis).filter_by(ticker=ticker).first()
    if not analysis:
        analysis = FlatAnalysis(ticker=ticker)

    analysis.updated_at = datetime.datetime.utcnow()
    analysis.pattern_detected = pattern_detected
    analysis.flat_start = dates[0]
    analysis.flat_end = dates[-surge_window_days - 1]
    analysis.flat_days = len(flat_window)
    analysis.flat_price_range_pct = round(flat_range_pct, 2)
    analysis.flat_avg_volume = int(flat_avg_vol)
    analysis.surge_start = dates[-surge_window_days]
    analysis.surge_end = dates[-1]
    analysis.surge_pct = round(surge_pct, 2)
    analysis.surge_volume_multiple = round(vol_multiple, 2)
    analysis.signal_day = dates[-1] if pattern_detected else None
    analysis.score = score

    db.merge(analysis)
    db.commit()
    return analysis
