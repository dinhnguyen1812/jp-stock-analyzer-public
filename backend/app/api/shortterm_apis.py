from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.db import SessionLocal
from app.utils.shortterm.volume_scraper import scan_and_save_volume_surges
from app.models import VolumeSnapshot
from datetime import datetime, timedelta

router = APIRouter()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/volume_scan")
def trigger_volume_scan(db: Session = Depends(get_db)):
    """Run a scan to detect volume surge stocks (default threshold = 2x)."""
    scan_and_save_volume_surges(db)
    return {"message": "Volume scan triggered and stored."}

@router.get("/volume_surges")
def get_recent_volume_surges(hours: int = 24, db: Session = Depends(get_db)):
    """Return stocks with volume surges in the last `hours`."""
    since = datetime.utcnow() - timedelta(hours=hours)
    results = db.query(VolumeSnapshot).filter(
        VolumeSnapshot.detected_at >= since
    ).order_by(VolumeSnapshot.volume_rate.desc()).all()

    return [
        {
            "ticker": r.ticker,
            "name": r.name,
            "volume_rate": r.volume_rate,
            "current_volume": r.current_volume,
            "avg_volume_5d": r.avg_volume_5d,
            "detected_at": r.detected_at.isoformat(),
        }
        for r in results
    ]
