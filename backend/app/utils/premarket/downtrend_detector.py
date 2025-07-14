import datetime
from typing import List, Optional, Dict
from sqlalchemy.orm import Session

from app.models import DailyPrice, StockDownTrendAnalysis
from app.utils.shortterm.price_updater import fetch_and_save_price_history

def compute_downtrend_analysis(db: Session, ticker: str, days: int = 30) -> StockDownTrendAnalysis:
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
        return StockDownTrendAnalysis(
            ticker=ticker,
            updated_at=datetime.datetime.now(),
            drop_pct=0.0,
            had_downtrend=False,
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

    # Downtrend detection
    max_price = max(close_prices)
    max_idx = close_prices.index(max_price)
    max_date = dates[max_idx]

    post_peak_prices = close_prices[max_idx + 1:]
    post_peak_dates = dates[max_idx + 1:]

    if post_peak_prices:
        min_price = min(post_peak_prices)
        min_idx = post_peak_prices.index(min_price)
        min_date = post_peak_dates[min_idx]
        drop_pct = (min_price - max_price) / max_price * 100
        had_downtrend = drop_pct <= -10
    else:
        drop_pct = 0.0
        had_downtrend = False
        min_price = None
        min_date = None

    drop_from_high_pct = (max(highs) - current_price) / max(highs) * 100 if highs else None
    rebound_from_low_pct = (current_price - min(lows)) / min(lows) * 100 if lows else None

    return StockDownTrendAnalysis(
        ticker=ticker,
        updated_at=datetime.datetime.now(),
        drop_pct=round(drop_pct, 2),
        had_downtrend=had_downtrend,
        from_date=max_date if had_downtrend else None,
        to_date=min_date if had_downtrend else None,
        highest_price=max(highs) if highs else None,
        lowest_price=min(lows) if lows else None,
        drop_from_high_pct=round(drop_from_high_pct, 2) if drop_from_high_pct else None,
        rebound_from_low_pct=round(rebound_from_low_pct, 2) if rebound_from_low_pct else None,
    )

def get_downtrend_analysis(db: Session, ticker: str, max_age_minutes=60) -> StockDownTrendAnalysis:
    record = db.query(StockDownTrendAnalysis).filter_by(ticker=ticker).first()
    now = datetime.datetime.now()

    if record and record.updated_at and (now - record.updated_at).total_seconds() < max_age_minutes * 60:
        return record

    new_record = compute_downtrend_analysis(db, ticker)
    if record:
        for attr, value in vars(new_record).items():
            if attr != "_sa_instance_state":
                setattr(record, attr, value)
    else:
        db.add(new_record)
    db.commit()
    return new_record

def normalize_downtrend_for_json(trend: StockDownTrendAnalysis) -> dict:
    return {
        "ticker": trend.ticker,
        "drop_pct": trend.drop_pct,
        "had_downtrend": trend.had_downtrend,
        "from_date": trend.from_date.isoformat() if trend.from_date else None,
        "to_date": trend.to_date.isoformat() if trend.to_date else None,
        "highest_price": trend.highest_price,
        "lowest_price": trend.lowest_price,
        "drop_from_high_pct": trend.drop_from_high_pct,
        "rebound_from_low_pct": trend.rebound_from_low_pct,
        "updated_at": trend.updated_at.isoformat() if trend.updated_at else None,
    }


def compute_price_stats(prices: List[DailyPrice], current_price: float) -> Dict[str, Optional[float]]:
    if not prices:
        return {
            "highest_price": None,
            "lowest_price": None,
            "drop_from_high_pct": None,
            "rebound_from_low_pct": None
        }

    highs = [p.high for p in prices if p.high]
    lows = [p.low for p in prices if p.low]

    if not highs or not lows:
        return {
            "highest_price": None,
            "lowest_price": None,
            "drop_from_high_pct": None,
            "rebound_from_low_pct": None
        }

    highest = max(highs)
    lowest = min(lows)

    drop_from_high = (
        round((highest - current_price) / highest * 100, 2)
        if highest > 0 else None
    )

    rebound_from_low = (
        round((current_price - lowest) / lowest * 100, 2)
        if lowest > 0 else None
    )

    return {
        "highest_price": highest,
        "lowest_price": lowest,
        "drop_from_high_pct": drop_from_high,
        "rebound_from_low_pct": rebound_from_low
    }