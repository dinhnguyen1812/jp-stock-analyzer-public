import datetime
from typing import Optional, Dict
from app.utils.shortterm.volume_surge_scraper import fetch_intraday_prices
from sqlalchemy.orm import Session
from app.models import DailyPrice, StockSpikeAnalysis
from app.utils.shortterm.price_updater import fetch_and_save_price_history


def compute_spike_analysis(
    db: Session,
    ticker: str,
    analyze_intraday: bool = False,
    spike_threshold: float = 15.0,
    respike_threshold: float = 10.0,
    close_near_high_pct: float = 10.0,
    close_near_low_pct: float = 10.0,
    limit_days: int = 20
) -> StockSpikeAnalysis:
    """
    Detect first spike (> spike_threshold) in the last `limit_days` (including today),
    check if first spike closed near high, count respikes (ignoring continuation),
    calculate first_spike_pct, drop from highest, and whether last day closed near low.
    """

    fetch_and_save_price_history(db, ticker, max_days=limit_days)

    rows = (
        db.query(DailyPrice)
        .filter(DailyPrice.ticker == ticker)
        .order_by(DailyPrice.date.desc())
        .limit(limit_days)
        .all()
    )
    if not rows or len(rows) < 2:
        return StockSpikeAnalysis(
            ticker=ticker,
            updated_at=datetime.datetime.now(),
            spike_date=None,
            first_day_close_near_high=None,
            first_spike_pct=None,
            days_since_spike=None,
            number_of_respikes=0,
            drop_from_high_pct=None,
            last_day_close_near_low=None,
            score=0,
        )

    # Chronological order
    rows = rows[::-1]
    dates = [r.date for r in rows]
    closes = [r.close for r in rows]
    highs = [r.high for r in rows]
    lows = [r.low for r in rows]

    if analyze_intraday:
        intraday_close, _, intraday_high, intraday_low = fetch_intraday_prices(ticker)
        intraday_date = datetime.now().strftime("%Y-%m-%d")

        dates.append(intraday_date)
        closes.append(intraday_close)
        highs.append(intraday_high)
        lows.append(intraday_low)

    spike_index = None
    spike_date = None
    first_day_close_near_high = None

    # Find first spike
    for i in range(1, len(rows)):
        pct_rise = (highs[i] - closes[i - 1]) / closes[i - 1] * 100
        if pct_rise >= spike_threshold:
            spike_index = i
            spike_date = dates[i]
            high_close_threshold = highs[i] * (1 - close_near_high_pct / 100)
            first_day_close_near_high = closes[i] >= high_close_threshold
            break

    if spike_index is None:
        return StockSpikeAnalysis(
            ticker=ticker,
            updated_at=datetime.datetime.now(),
            spike_date=None,
            first_day_close_near_high=None,
            first_spike_pct=None,
            days_since_spike=None,
            number_of_respikes=0,
            drop_from_high_pct=None,
            last_day_close_near_low=None,
            score=0,
        )

    # --- Compute first_spike_pct (continuation) ---
    first_spike_close = closes[spike_index - 1]  # close before spike
    highest_in_first_spike = highs[spike_index]

    i = spike_index + 1
    while i < len(rows):
        # If next day close >= previous close, continuation
        if closes[i] >= closes[i - 1]:
            highest_in_first_spike = max(highest_in_first_spike, highs[i])
            i += 1
        else:
            break

    first_spike_pct = (highest_in_first_spike - first_spike_close) / first_spike_close * 100

    # --- Count respikes (ignore continuation) ---
    respike_count = 0
    highest_price = highest_in_first_spike

    while i < len(rows):
        pct_rise = (highs[i] - closes[i - 1]) / closes[i - 1] * 100
        if pct_rise >= respike_threshold:
            respike_count += 1
            highest_price = max(highest_price, highs[i])
        i += 1

    # Drop from highest
    last_close = closes[-1]
    drop_from_high = (highest_price - last_close) / highest_price * 100 if highest_price else None

    # Last day close near low
    last_low = lows[-1]
    last_high = highs[-1]
    near_low_threshold = last_low * (1 + close_near_low_pct / 100)
    last_day_close_near_to_low = last_close <= near_low_threshold
    last_day_close_near_low_than_high = (last_close - last_low) < 0.5 * (last_high - last_close)
    last_day_close_near_low = last_day_close_near_to_low and last_day_close_near_low_than_high

    analysis = StockSpikeAnalysis(
        ticker=ticker,
        updated_at=datetime.datetime.now(),
        spike_date=spike_date,
        first_day_close_near_high=first_day_close_near_high,
        first_spike_pct=round(first_spike_pct, 2),
        number_of_respikes=respike_count,
        drop_from_high_pct=round(drop_from_high, 2) if drop_from_high else None,
        last_day_close_near_low=last_day_close_near_low,
    )

    # rows are already reversed to chronological
    dates = [r.date for r in rows]
    if spike_index is not None:
        days_since_spike = len(dates) - 1 - spike_index
    else:
        days_since_spike = None  # or 0
    analysis.days_since_spike = days_since_spike
    analysis.score = compute_spike_score(analysis)

    return analysis


def get_spike_analysis(db: Session, ticker: str, max_age_minutes=60, analyze_intraday=False, limit_days=20, spike_threshold=15.0) -> StockSpikeAnalysis:
    """Retrieve spike analysis from DB, or recompute if stale."""
    record = db.query(StockSpikeAnalysis).filter_by(ticker=ticker).first()
    now = datetime.datetime.now()

    if record and record.updated_at and (now - record.updated_at).total_seconds() < max_age_minutes * 60:
        return record

    new_record = compute_spike_analysis(db, ticker, analyze_intraday=analyze_intraday, limit_days=limit_days, spike_threshold=spike_threshold)
    if record:
        for attr, value in vars(new_record).items():
            if attr != "_sa_instance_state":
                setattr(record, attr, value)
    else:
        db.add(new_record)
    db.commit()
    return new_record


def normalize_spike_for_json(spike: StockSpikeAnalysis) -> dict:
    """Convert spike analysis record into JSON-serializable dict."""
    return {
        "ticker": spike.ticker,
        "spike_date": spike.spike_date.isoformat() if spike.spike_date else None,
        "first_day_close_near_high": spike.first_day_close_near_high,
        "first_spike_pct": spike.first_spike_pct,
        "days_since_spike": spike.days_since_spike,
        "number_of_respikes": spike.number_of_respikes,
        "drop_from_high_pct": spike.drop_from_high_pct,
        "last_day_close_near_low": spike.last_day_close_near_low,
        "score": spike.score,  # ✅ include new field
        "updated_at": spike.updated_at.isoformat() if spike.updated_at else None,
    }


def compute_spike_score(spike: StockSpikeAnalysis) -> int:
    """Compute a 0–100 score for the spike pattern."""
    if not spike.spike_date:
        return 0

    score = 0

    if spike.first_day_close_near_high:
        score += 10

    # 1. Recency of spike (35 pts)
    if spike.days_since_spike <= 2:
        score += 35
    elif spike.days_since_spike <= 5:
        score += 25
    elif spike.days_since_spike <= 10:
        score += 15
    elif spike.days_since_spike <= 15:
        score += 5

    # 2. Drop from high (25 pts)
    if spike.drop_from_high_pct is not None:
        if spike.drop_from_high_pct >= 40:
            score += 25
        elif spike.drop_from_high_pct >= 20:
            score += 18
        elif spike.drop_from_high_pct >= 10:
            score += 10
        else:
            score += 5

    # 3. First spike pct (20 pts)
    if spike.first_spike_pct is not None:
        if spike.first_spike_pct >= 100:
            score += 20
        elif spike.first_spike_pct >= 40:
            score += 10
        elif spike.first_spike_pct >= 20:
            score += 5

    # 4. Last day close near low (15 pts)
    if spike.last_day_close_near_low:
        score += 15

    # 5. Respikes
    if spike.number_of_respikes > 3:
        score += 0  # too many respikes → no points
    else:
        score += min(spike.number_of_respikes, 1) * 5


    return score


def compute_spike_analysis_100(
    db: Session,
    ticker: str,
    limit_days: int = 50
):
    fetch_and_save_price_history(db, ticker, max_days=limit_days)

    rows = (
        db.query(DailyPrice)
        .filter(DailyPrice.ticker == ticker)
        .order_by(DailyPrice.date.desc())
        .limit(limit_days)
        .all()
    )
    if not rows or len(rows) < 2:
        return "No"

    # Chronological order
    rows = rows[::-1]
    highs = [r.high for r in rows]
    lows = [r.low for r in rows]

    highest = max(highs)
    lowest = min(lows)

    if highest > lowest * 2:
        return True
    return False
