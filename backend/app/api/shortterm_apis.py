from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import distinct
from sqlalchemy.sql import func
from sqlalchemy.orm import aliased
from sqlalchemy.orm import Session
from typing import List, Dict
from app.db.db import SessionLocal
from app.models import VolumeSnapshot
from datetime import datetime, timedelta

from app.utils.shortterm.volume_surge_scraper import scan_and_save_volume_surges
from app.utils.shortterm.volume_history import fetch_daily_volume_history, save_daily_volumes
from app.utils.shortterm.moneyflow_history import fetch_daily_money_flow_history, save_daily_money_flows
from app.utils.shortterm.volume_5d_average_updater import update_avg_volume_for_ticker
from app.utils.shortterm.moneyflow_5d_average_updater import update_avg_money_flow_for_ticker
from app.utils.shortterm.yahoo_general_news import scrape_yahoo_general_market_news, rerank_news_with_gpt
from app.utils.shortterm.kabutan_news_ticker import scrape_kabutan_news, ask_gpt_to_get_relevant_news

router = APIRouter()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/volume/{ticker}/history")
def update_volume_history(ticker: str, db: Session = Depends(get_db)):
    """Scrape and store the past 5 daily volumes from Yahoo."""
    volume_data = fetch_daily_volume_history(ticker)
    if not volume_data:
        raise HTTPException(status_code=404, detail="Failed to fetch volume data")
    
    save_daily_volumes(db, ticker, volume_data)
    return {"message": f"Volume history updated for {ticker}", "records": len(volume_data)}

@router.post("/volume/{ticker}/average")
def update_volume_average(ticker: str, db: Session = Depends(get_db)):
    """Recalculate and store the 5-day average volume using shared updater."""
    update_avg_volume_for_ticker(db, ticker)
    return {"message": f"5-day average volume check complete for {ticker}"}

@router.post("/moneyflow/{ticker}/history")
def update_moneyflow_history(ticker: str, db: Session = Depends(get_db)):
    """
    Scrape and store the past 5 daily money flow records from Yahoo.
    """
    flow_data = fetch_daily_money_flow_history(ticker)
    if not flow_data:
        raise HTTPException(status_code=404, detail="Failed to fetch money flow data")

    save_daily_money_flows(db, ticker, flow_data)
    return {
        "message": f"Money flow history updated for {ticker}",
        "records": len(flow_data)
    }

@router.post("/moneyflow/{ticker}/average")
def update_money_flow_average(ticker: str, db: Session = Depends(get_db)):
    """
    Recalculate and store the 5-day average money flow for a given ticker.
    """
    update_avg_money_flow_for_ticker(db, ticker)
    return {"message": f"5-day average money flow check complete for {ticker}"}

@router.post("/volume_scan")
def trigger_volume_scan(db: Session = Depends(get_db), surge_threshold: float = 2.0, price_threshold: float = 300.0, pages: int = 1):
    """Run a scan to detect volume surge stocks (default threshold = 2x)."""
    scan_and_save_volume_surges(db, surge_threshold, price_threshold, pages)
    return {"message": "Volume scan triggered and stored."}

@router.get("/volume_surges")
def get_recent_volume_surges(hours: int = 24, db: Session = Depends(get_db)):
    """Return stocks with volume surges in the last `hours`."""
    since = datetime.utcnow() - timedelta(hours=hours)

    # Subquery: get the max detected_at per ticker
    subquery = (
        db.query(
            VolumeSnapshot.ticker,
            func.max(VolumeSnapshot.detected_at).label("latest_time")
        )
        .filter(VolumeSnapshot.detected_at >= since)
        .group_by(VolumeSnapshot.ticker)
        .subquery()
    )

    # Join back to get full VolumeSnapshot rows
    VS = aliased(VolumeSnapshot)
    results = (
        db.query(VS)
        .join(subquery, (VS.ticker == subquery.c.ticker) & (VS.detected_at == subquery.c.latest_time))
        .order_by(VS.volume_rate.desc())
        .all()
    )
    return [
        {
            "ticker": r.ticker,
            "name": r.name,
            "volume_rate": r.volume_rate,
            "money_flow_rate": r.money_flow_rate,
            "current_volume": r.current_volume,
            "avg_volume_5d": r.avg_volume_5d,
            "detected_at": r.detected_at.isoformat(),
        }
        for r in results
    ]

@router.get("/shortterm/news_signals", response_model=List[Dict])
def get_news_signals(db: Session = Depends(get_db)):
    try:
        # Step 1: Scrape general market news (limit 30)
        news_items = scrape_yahoo_general_market_news(limit_per_category=10)
        if not news_items:
            raise HTTPException(status_code=500, detail="Failed to fetch market news.")

        # Step 2: Use GPT to rerank top 10 impactful news
        top_news = rerank_news_with_gpt(news_items, top_n=10)

        # Step 3: Return results
        return [
            {
                "headline": item["headline"],
                "url": item["url"],
                "published_at": item["published_at"],
                "score": item["score"],
            }
            for item in top_news
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching news signals: {e}")

@router.get("/shortterm/kabutan_news", response_model=List[Dict])
async def get_kabutan_news(ticker: str, limit: int = 30, top_n: int = 10):
    news = scrape_kabutan_news(ticker, limit)
    if not news:
        raise HTTPException(status_code=404, detail="No news found")

    top_news = ask_gpt_to_get_relevant_news(news, ticker, top_n=top_n)
    return top_news