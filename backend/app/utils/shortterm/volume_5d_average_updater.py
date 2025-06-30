from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models import DailyVolume, AverageVolume
from app.utils.shortterm.volume_history import fetch_daily_volume_history, save_daily_volumes


def update_avg_volume_for_ticker(db: Session, ticker: str):
    today = datetime.utcnow().date()

    # Step 1: Check most recent date in DB
    latest_record = (
        db.query(DailyVolume)
        .filter_by(ticker=ticker)
        .order_by(DailyVolume.date.desc())
        .first()
    )

    # If missing or outdated (more than 1 day old), fetch new data
    if not latest_record or (today - latest_record.date).days >= 1:
        print(f"🔄 Updating volume history for {ticker}...")
        new_data = fetch_daily_volume_history(ticker)
        if new_data:
            save_daily_volumes(db, ticker, new_data)
        else:
            print(f"❌ Failed to fetch volume history for {ticker}")
            return

    # Step 2: Re-fetch top 5 most recent days
    volumes = (
        db.query(DailyVolume)
        .filter(DailyVolume.ticker == ticker)
        .order_by(desc(DailyVolume.date))
        .limit(5)
        .all()
    )

    if len(volumes) < 5:
        print(f"⏳ Not enough volume data for {ticker}. Need 5 days, found {len(volumes)}.")
        return

    # Optional: Check if data is too sparse
    if (volumes[0].date - volumes[-1].date).days > 10:
        print(f"⚠️ Volume data for {ticker} is too sparse for 5-day average.")
        return

    avg_volume = sum(v.volume for v in volumes) // 5

    # Upsert
    existing = db.query(AverageVolume).filter_by(ticker=ticker).first()
    if existing:
        existing.avg_5d_volume = avg_volume
        existing.updated_at = datetime.utcnow()
        print(f"🔄 Updated 5-day average volume for {ticker}: {avg_volume}")
    else:
        record = AverageVolume(
            ticker=ticker,
            avg_5d_volume=avg_volume,
            updated_at=datetime.utcnow(),
        )
        db.add(record)
        print(f"✅ Inserted 5-day average volume for {ticker}: {avg_volume}")

    db.commit()
