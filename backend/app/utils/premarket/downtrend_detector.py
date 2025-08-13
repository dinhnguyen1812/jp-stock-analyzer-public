import datetime
from typing import List, Optional, Dict
from sqlalchemy.orm import Session

from app.models import DailyPrice, StockDownTrendAnalysis, StockUpTrendAnalysis
from app.utils.shortterm.price_updater import fetch_and_save_price_history

def compute_downtrend_analysis(db: Session, ticker: str, days: int = 30) -> StockDownTrendAnalysis:
    fetch_and_save_price_history(db, ticker, max_days=30)

    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=days + 10)

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

    # Load previous uptrend
    uptrend: StockUpTrendAnalysis = db.query(StockUpTrendAnalysis).filter_by(ticker=ticker).first()

    if not uptrend or not uptrend.had_uptrend or not uptrend.to_date or uptrend.highest_price is None or uptrend.lowest_price is None:
        return StockDownTrendAnalysis(
            ticker=ticker,
            updated_at=datetime.datetime.now(),
            drop_pct=0.0,
            had_downtrend=False,
            from_date=None,
            to_date=None,
            highest_price=max(highs) if highs else None,
            lowest_price=min(lows) if lows else None,
            drop_from_high_pct=None,
            rebound_from_low_pct=None
        )

    uptrend_high = uptrend.highest_price
    uptrend_low = uptrend.lowest_price
    uptrend_range = uptrend_high - uptrend_low

    if uptrend_range <= 0:
        return StockDownTrendAnalysis(
            ticker=ticker,
            updated_at=datetime.datetime.now(),
            drop_pct=0.0,
            had_downtrend=False,
            from_date=None,
            to_date=None,
            highest_price=max(highs) if highs else None,
            lowest_price=min(lows) if lows else None,
            drop_from_high_pct=None,
            rebound_from_low_pct=None
        )

    # Filter prices after uptrend ends
    post_uptrend_prices = [(d, c) for d, c in zip(dates, close_prices) if d > uptrend.to_date]
    if len(post_uptrend_prices) < 2:
        return StockDownTrendAnalysis(
            ticker=ticker,
            updated_at=datetime.datetime.now(),
            drop_pct=0.0,
            had_downtrend=False,
            from_date=None,
            to_date=None,
            highest_price=max(highs) if highs else None,
            lowest_price=min(lows) if lows else None,
            drop_from_high_pct=None,
            rebound_from_low_pct=None
        )

    # Search for drop from uptrend high to lowest point after uptrend
    lowest_price = min([p for d, p in post_uptrend_prices])
    low_date = [d for d, p in post_uptrend_prices if p == lowest_price][0]

    drop_pct = (uptrend_high - lowest_price) / uptrend_range * 100
    had_downtrend = drop_pct >= 30

    drop_from_high_pct = (uptrend_high - current_price) / uptrend_range * 100 if highs else None
    rebound_from_low_pct = (current_price - lowest_price) / uptrend_range * 100 if current_price > lowest_price else None

    return StockDownTrendAnalysis(
        ticker=ticker,
        updated_at=datetime.datetime.now(),
        drop_pct=round(drop_pct, 2),
        had_downtrend=had_downtrend,
        from_date=uptrend.to_date if had_downtrend else None,
        to_date=low_date if had_downtrend else None,
        highest_price=uptrend_high if highs else None,
        lowest_price=lowest_price if lows else None,
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