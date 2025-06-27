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

# For testing
@router.post("/volume/{ticker}/history")
def update_volume_history(ticker: str, db: Session = Depends(get_db)):
    """Scrape and store the past 5 daily volumes from Yahoo."""
    volume_data = fetch_daily_volume_history(ticker)
    if not volume_data:
        raise HTTPException(status_code=404, detail="Failed to fetch volume data")
    
    save_daily_volumes(db, ticker, volume_data)
    return {"message": f"Volume history updated for {ticker}", "records": len(volume_data)}

# For testing
@router.post("/volume/{ticker}/average")
def update_volume_average(ticker: str, db: Session = Depends(get_db)):
    """Recalculate and store the 5-day average volume using shared updater."""
    update_avg_volume_for_ticker(db, ticker)
    return {"message": f"5-day average volume check complete for {ticker}"}

# For testing
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

# For testing
@router.post("/moneyflow/{ticker}/average")
def update_money_flow_average(ticker: str, db: Session = Depends(get_db)):
    """
    Recalculate and store the 5-day average money flow for a given ticker.
    """
    update_avg_money_flow_for_ticker(db, ticker)
    return {"message": f"5-day average money flow check complete for {ticker}"}

# For Use
class ScanParams(BaseModel):
    surge_threshold: float = 2.0
    price_threshold: float = 300.0
    pages: int = 1

# For Use
@router.post("/volume_scan")
def trigger_volume_scan(
    params: ScanParams,
    db: Session = Depends(get_db)
):

    # Step 1: Scan and save volume surge data
    tickers = scan_and_save_volume_surges(
        db=db,
        surge_threshold=params.surge_threshold,
        price_threshold=params.price_threshold,
        pages=params.pages
    )

    # Step 2: For each new ticker, run GPT analysis
    for ticker in tickers:
        news = scrape_kabutan_news(ticker, limit=30)
        if not news:
            continue

        try:
            analyze_stock_surge_with_news(
                db=db,
                ticker=ticker,
                news_items=news,
                top_n=5,
            )
        except Exception as e:
            print(f"⚠️ GPT analysis failed for {ticker}: {e}")

    return {"message": f"Volume scan complete. {len(tickers)} tickers analyzed and stored."}

# For Use
@router.get("/volume_surges")
def get_recent_volume_surges(hours: int = 24, db: Session = Depends(get_db)):
    """Return stocks with volume surges in the last `hours`."""
    return get_latest_volume_surges(db, hours)

# For Use
@router.get("/news_signals", response_model=List[Dict])
def get_news_signals(db: Session = Depends(get_db)):
    return fetch_news_signals()

# For testing
@router.get("/{ticker}/kabutan_news_analysis", response_model=Dict)
async def get_kabutan_news_analysis(
    ticker: str,
    limit: int = 30,
    top_n: int = 10,
    user_prompt: str = "",
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

    volume_info = result.get("volume_info")
    if not volume_info:
        raise HTTPException(status_code=404, detail=f"No recent volume surge for {ticker}")

    return {
        "ticker": ticker,
        "top_news": result.get("top_news", []),
        "volume_info": {
            "ticker": volume_info.get("ticker"),
            "name": volume_info.get("name"),
            "current_price": volume_info.get("current_price"),
            "price_change": volume_info.get("price_change"),
            "volume_rate": volume_info.get("volume_rate"),
            "money_flow_rate": volume_info.get("money_flow_rate"),
            "current_volume": volume_info.get("current_volume"),
            "avg_volume_5d": volume_info.get("avg_volume_5d"),
            "detected_at": volume_info.get("detected_at"),
            "reasoning": volume_info.get("reasoning"),
            "recommendation": volume_info.get("recommendation"),
            "promising_score": volume_info.get("promising_score"),
        }
    }