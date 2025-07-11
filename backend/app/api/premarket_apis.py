import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.schemas import ScanParams

from app.db.db import SessionLocal
from app.models import VolumeSnapshot, StarredStock
from app.utils.premarket.pre_volume_surge_scraper import analyze_and_snapshot_ticker, fetch_ranked_volume_tickers, scan_and_save_pre_market_volume_surges
from app.utils.shortterm.kabutan_news_ticker import get_volume_info, scrape_kabutan_news
from app.utils.premarket.pre_gpt_analyzer import premarket_analyze_with_gpt

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ✅ 1. Scan and save pre-market volume surges
@router.post("/scan")
def scan_premarket_volume_surges(
    from_page: int = Query(1, ge=1),
    to_page: int = Query(3, ge=1),
    surge_threshold: float = 1.5,
    price_threshold: float = 300.0,
    db: Session = Depends(get_db),
):
    tickers = scan_and_save_pre_market_volume_surges(
        db=db,
        surge_threshold=surge_threshold,
        price_threshold=price_threshold,
        from_page=from_page,
        to_page=to_page,
    )
    return {"saved_tickers": tickers, "count": len(tickers)}

# ✅ 2. Analyze a single ticker
@router.get("/volume_rate/{ticker}")
def analyze_single_ticker(
    ticker: str,
    surge_threshold: float = 1.5,
    price_threshold: float = 300.0,
    db: Session = Depends(get_db),
):
    snapshot = analyze_and_snapshot_ticker(
        db=db,
        ticker=ticker,
        surge_threshold=surge_threshold,
        price_threshold=price_threshold,
    )
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"No qualifying data for {ticker}")
    return {
        "ticker": snapshot.ticker,
        "name": snapshot.name,
        "current_price": snapshot.current_price,
        "current_volume": snapshot.current_volume,
        "avg_volume_5d": snapshot.avg_volume_5d,
        "volume_rate": snapshot.volume_rate,
        "money_flow_rate": snapshot.money_flow_rate,
        "detected_at": snapshot.detected_at,
    }

# ✅ 3. Fetch ranked volume tickers (Yahoo Ranking)
@router.get("/fetch_ranked")
def get_ranked_volume_tickers(
    from_page: int = Query(1, ge=1),
    to_page: int = Query(3, ge=1),
):
    tickers = fetch_ranked_volume_tickers(from_page=from_page, to_page=to_page)
    return {"ranked_tickers": tickers, "count": len(tickers)}

@router.post("/volume_scan")
def trigger_volume_scan(
    params: ScanParams,
    db: Session = Depends(get_db)
):
    # Step 1: Scan and save volume surge data (pre-market)
    tickers = scan_and_save_pre_market_volume_surges(
        db=db,
        surge_threshold=params.surge_threshold,
        price_threshold=params.price_threshold,
        from_page=params.from_page,
        to_page=params.to_page,
    )

    # Step 2: Run initial GPT-3.5-turbo analysis on all detected tickers
    for ticker in tickers:
        news = scrape_kabutan_news(ticker, limit=30)
        if not news:
            continue

        volume_info = get_volume_info(db, ticker=ticker)
        if not volume_info:
            continue

        try:
            premarket_analyze_with_gpt(
                db=db,
                ticker=ticker,
                news_items=news,
                volume_info=volume_info,
                top_n=5,
                model="gpt-3.5-turbo",
            )
        except Exception as e:
            print(f"⚠️ GPT-3.5 analysis failed for {ticker}: {e}")

    # Step 3: Re-analyze promising tickers (promising_score >= 65) with GPT-4o
    for ticker in tickers:
        volume_info = get_volume_info(db, ticker=ticker)
        if not volume_info:
            continue
        if volume_info.promising_score is not None and volume_info.promising_score >= 65:
            try:
                print(f"🔁 Re-analyzing {ticker} with GPT-4o...")
                premarket_analyze_with_gpt(db=db, ticker=ticker, news_items=news, volume_info=volume_info, top_n=5)
            except Exception as e:
                print(f"⚠️ GPT-4o analysis failed for {ticker}: {e}")

    return {"message": f"Volume scan complete. {len(tickers)} tickers analyzed."}