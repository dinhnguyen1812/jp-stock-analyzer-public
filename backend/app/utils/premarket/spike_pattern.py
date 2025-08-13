import datetime
from typing import Optional, Dict
from sqlalchemy.orm import Session
from app.models import DailyPrice, StockSpikeAnalysis
from app.utils.shortterm.price_updater import fetch_and_save_price_history


def compute_spike_analysis(
    db: Session,
    ticker: str,
    spike_threshold: float = 20.0,
    respike_threshold: float = 10.0,
    close_near_high_pct: float = 10.0,
    close_near_low_pct: float = 10.0,
    limit_days: int = 15
) -> StockSpikeAnalysis:
    """
    Detect first spike (> spike_threshold) in the last `limit_days` (including today),
    check if first spike closed near high, count respikes, 
    calculate drop from highest, and whether last day closed near low.
    """

    # Optional: Ensure latest prices are up-to-date
    fetch_and_save_price_history(db, ticker, max_days=limit_days)

    # Fetch last N days of prices
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
            first_spike_close_near_high=None,
            number_of_respikes=0,
            drop_from_high_pct=None,
            last_day_close_near_low=None
        )

    # Reverse to chronological
    rows = rows[::-1]
    dates = [r.date for r in rows]
    closes = [r.close for r in rows]
    highs = [r.high for r in rows]
    lows = [r.low for r in rows]

    spike_index = None
    spike_date = None
    first_spike_close_near_high = None

    # Find first spike: high_today vs close_yesterday
    for i in range(1, len(rows)):
        pct_rise = (highs[i] - closes[i - 1]) / closes[i - 1] * 100
        if pct_rise >= spike_threshold:
            spike_index = i
            spike_date = dates[i]
            # Check if close near high
            high_close_threshold = highs[i] * (1 - close_near_high_pct / 100)
            first_spike_close_near_high = closes[i] >= high_close_threshold
            break

    if spike_index is None:
        return StockSpikeAnalysis(
            ticker=ticker,
            updated_at=datetime.datetime.now(),
            spike_date=None,
            first_spike_close_near_high=None,
            number_of_respikes=0,
            drop_from_high_pct=None,
            last_day_close_near_low=None
        )

    # Count respikes & track highest price after initial spike
    respike_count = 0
    highest_price = highs[spike_index]

    for i in range(spike_index + 1, len(rows)):
        pct_rise = (highs[i] - closes[i - 1]) / closes[i - 1] * 100
        if pct_rise >= respike_threshold:
            respike_count += 1
            highest_price = max(highest_price, highs[i])

    # Drop from highest spike
    last_close = closes[-1]
    drop_from_high = (highest_price - last_close) / highest_price * 100 if highest_price else None

    # Last day close near low
    last_low = lows[-1]
    last_high = highs[-1]
    last_close = closes[-1]

    # Compare to low
    near_low_threshold = last_low * (1 + close_near_low_pct / 100)
    last_day_close_near_to_low = last_close <= near_low_threshold

    # Compare distances: if close is much closer to low than to high
    last_day_close_near_low_than_high = (last_close - last_low) < 0.5 * (last_high - last_close)

    last_day_close_near_low = last_day_close_near_to_low and last_day_close_near_low_than_high

    return StockSpikeAnalysis(
        ticker=ticker,
        updated_at=datetime.datetime.now(),
        spike_date=spike_date,
        first_spike_close_near_high=first_spike_close_near_high,
        number_of_respikes=respike_count,
        drop_from_high_pct=round(drop_from_high, 2) if drop_from_high else None,
        last_day_close_near_low=last_day_close_near_low
    )


def get_spike_analysis(db: Session, ticker: str, max_age_minutes=60) -> StockSpikeAnalysis:
    """Retrieve spike analysis from DB, or recompute if stale."""
    record = db.query(StockSpikeAnalysis).filter_by(ticker=ticker).first()
    now = datetime.datetime.now()

    if record and record.updated_at and (now - record.updated_at).total_seconds() < max_age_minutes * 60:
        return record

    new_record = compute_spike_analysis(db, ticker)
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
        "first_spike_close_near_high": spike.first_spike_close_near_high,
        "number_of_respikes": spike.number_of_respikes,
        "drop_from_high_pct": spike.drop_from_high_pct,
        "last_day_close_near_low": spike.last_day_close_near_low,
        "updated_at": spike.updated_at.isoformat() if spike.updated_at else None,
    }
