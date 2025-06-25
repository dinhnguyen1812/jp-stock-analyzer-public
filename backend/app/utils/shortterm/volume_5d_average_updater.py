from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.models import DailyVolume, AverageVolume

def update_avg_volume_for_ticker(db: Session, ticker: str):
    # Fetch the 5 most recent volume records for the ticker
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

    avg_volume = sum(v.volume for v in volumes) // 5

    # Upsert into AverageVolume
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
