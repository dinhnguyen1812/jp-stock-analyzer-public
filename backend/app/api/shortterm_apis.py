from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict
from pydantic import BaseModel

from app.db.db import SessionLocal
from app.utils.shortterm.volume_surge_scraper import scan_and_save_volume_surges, get_latest_volume_surges
from app.utils.shortterm.volume_history import fetch_daily_volume_history, save_daily_volumes
from app.utils.shortterm.moneyflow_history import fetch_daily_money_flow_history, save_daily_money_flows
from app.utils.shortterm.volume_5d_average_updater import update_avg_volume_for_ticker
from app.utils.shortterm.moneyflow_5d_average_updater import update_avg_money_flow_for_ticker
from app.utils.shortterm.yahoo_general_news import fetch_news_signals
from app.utils.shortterm.kabutan_news_ticker import scrape_kabutan_news, analyze_stock_surge_with_news

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

class ScanParams(BaseModel):
    surge_threshold: float = 2.0
    price_threshold: float = 300.0
    pages: int = 1

@router.post("/volume_scan")
def trigger_volume_scan(
    params: ScanParams,
    db: Session = Depends(get_db)
):
    scan_and_save_volume_surges(
        db=db,
        surge_threshold=params.surge_threshold,
        price_threshold=params.price_threshold,
        pages=params.pages
    )
    return {"message": "Volume scan triggered and stored."}

@router.get("/volume_surges")
def get_recent_volume_surges(hours: int = 24, db: Session = Depends(get_db)):
    """Return stocks with volume surges in the last `hours`."""
    return get_latest_volume_surges(db, hours)

@router.get("/news_signals", response_model=List[Dict])
def get_news_signals(db: Session = Depends(get_db)):
    return fetch_news_signals()

@router.get("/{ticker}/kabutan_news_analysis", response_model=Dict)
async def get_kabutan_news_analysis(
    ticker: str,
    limit: int = 30,
    top_n: int = 10,
    user_prompt: str = (
        "Summarize why this stock is experiencing a volume surge and recent news impact. "
        "Then, give a clear investment recommendation: buy, hold, or sell. "
        "Explain your recommendation with key risks and potential rewards."
    ),
    db: Session = Depends(get_db)
):
    news = scrape_kabutan_news(ticker, limit)
    if not news:
        raise HTTPException(status_code=404, detail="No news found")

    result = analyze_stock_surge_with_news(
        db=db,
        ticker=ticker,
        news_items=news,
        top_n=top_n,
        user_prompt=user_prompt,
    )

    if not result.get("volume_info"):
        raise HTTPException(status_code=404, detail=f"No recent volume surge for {ticker}")

    return result