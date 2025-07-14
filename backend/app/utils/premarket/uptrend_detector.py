# app/utils/shortterm/uptrend_detector.py

import datetime
from typing import List, Optional, Dict
from sqlalchemy.orm import Session

from app.models import DailyPrice, StockUpTrendAnalysis
from app.utils.shortterm.price_updater import fetch_and_save_price_history


def compute_uptrend_analysis(db: Session, ticker: str, days: int = 30) -> StockUpTrendAnalysis:
    fetch_and_save_price_history(db, ticker, max_days=150)

    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=days + 5)

    prices = (
        db.query(DailyPrice)
        .filter(DailyPrice.ticker == ticker, DailyPrice.date >= start_date)
        .order_by(DailyPrice.date.asc())
        .all()
    )

    if len(prices) < 10:
        return StockUpTrendAnalysis(
            ticker=ticker,
            updated_at=datetime.datetime.now(),
            rise_pct=0.0,
            had_uptrend=False,
            from_date=None,
            to_date=None,
            highest_price=None,
            lowest_price=None,
            drop_from_high_pct=None,
            rebound_from_low_pct=None
        )

    close_prices = [p.close for p in prices]
    highs = [p.high for p in prices if p.high]
    lows = [p.low for p in prices if p.low]
    dates = [p.date for p in prices]
    current_price = close_prices[-1]

    # Uptrend detection
    min_price = min(close_prices)
    min_idx = close_prices.index(min_price)
    min_date = dates[min_idx]

    post_trough_prices = close_prices[min_idx + 1:]
    post_trough_dates = dates[min_idx + 1:]

    if post_trough_prices:
        max_price = max(post_trough_prices)
        max_idx = post_trough_prices.index(max_price)
        max_date = post_trough_dates[max_idx]
        rise_pct = (max_price - min_price) / min_price * 100
        had_uptrend = rise_pct >= 10  # define threshold here
    else:
        rise_pct = 0.0
        had_uptrend = False
        max_price = None
        max_date = None

    drop_from_high_pct = (max(highs) - current_price) / max(highs) * 100 if highs else None
    rebound_from_low_pct = (current_price - min(lows)) / min(lows) * 100 if lows else None

    return StockUpTrendAnalysis(
        ticker=ticker,
        updated_at=datetime.datetime.now(),
        rise_pct=round(rise_pct, 2),
        had_uptrend=had_uptrend,
        from_date=min_date if had_uptrend else None,
        to_date=max_date if had_uptrend else None,
        highest_price=max(highs) if highs else None,
        lowest_price=min(lows) if lows else None,
        drop_from_high_pct=round(drop_from_high_pct, 2) if drop_from_high_pct else None,
        rebound_from_low_pct=round(rebound_from_low_pct, 2) if rebound_from_low_pct else None,
    )


def get_uptrend_analysis(db: Session, ticker: str, max_age_minutes=60) -> StockUpTrendAnalysis:
    record = db.query(StockUpTrendAnalysis).filter_by(ticker=ticker).first()
    now = datetime.datetime.now()

    if record and record.updated_at and (now - record.updated_at).total_seconds() < max_age_minutes * 60:
        return record

    new_record = compute_uptrend_analysis(db, ticker)
    if record:
        for attr, value in vars(new_record).items():
            if attr != "_sa_instance_state":
                setattr(record, attr, value)
    else:
        db.add(new_record)
    db.commit()
    return new_record


def normalize_uptrend_for_json(trend: StockUpTrendAnalysis) -> dict:
    return {
        "ticker": trend.ticker,
        "rise_pct": trend.rise_pct,
        "had_uptrend": trend.had_uptrend,
        "from_date": trend.from_date.isoformat() if trend.from_date else None,
        "to_date": trend.to_date.isoformat() if trend.to_date else None,
        "highest_price": trend.highest_price,
        "lowest_price": trend.lowest_price,
        "drop_from_high_pct": trend.drop_from_high_pct,
        "rebound_from_low_pct": trend.rebound_from_low_pct,
        "updated_at": trend.updated_at.isoformat() if trend.updated_at else None,
    }
