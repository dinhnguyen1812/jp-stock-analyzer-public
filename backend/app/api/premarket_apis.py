import datetime
import json
from difflib import get_close_matches
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, List, Optional, Tuple
from threading import Event
from app.schemas import ScanParams

from app.db.db import SessionLocal
from app.models import DailyPrice, StockNewsImpact, VolumeSnapshot, StarredStock
from app.utils.premarket.pre_volume_surge_scraper import analyze_and_snapshot_ticker, fetch_ranked_volume_tickers, scan_and_save_pre_market_volume_surges
from app.utils.shortterm.kabutan_news_ticker import get_volume_info, scrape_kabutan_news
from app.utils.shortterm.spike_scanner import compute_price_stats, detect_recent_downtrend, normalize_downtrend_for_json
from app.utils.premarket.pre_gpt_analyzer import premarket_analyze_with_gpt
from app.utils.premarket.pre_scan_news import fetch_low_cap_tickers, get_positive_news, scan_and_analyze_news_for_ticker
from app.api.shortterm_apis import get_latest_analysis_signal_data

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
                top_n=3,
                model="gpt-3.5-turbo",
            )
        except Exception as e:
            print(f"⚠️ GPT-3.5 analysis failed for {ticker}: {e}")

    # Step 3: Re-analyze promising tickers (promising_score >= 60) with GPT-4o
    for ticker in tickers:
        news = scrape_kabutan_news(ticker, limit=30)
        if not news:
            continue
        volume_info = get_volume_info(db, ticker=ticker)
        if not volume_info:
            continue
        if volume_info.promising_score is not None and volume_info.promising_score >= 60:
            try:
                print(f"🔁 Re-analyzing {ticker} with GPT-4o...")
                premarket_analyze_with_gpt(db=db, ticker=ticker, news_items=news, volume_info=volume_info, top_n=3, model="gpt-4o")
            except Exception as e:
                print(f"⚠️ GPT-4o analysis failed for {ticker}: {e}")

    return {"message": f"Volume scan complete. {len(tickers)} tickers analyzed."}

@router.get("/get_saved_vs", response_model=List[Dict])
def get_all_saved_volume_analyses(
    surge_threshold: float = Query(0, ge=0),
    price_threshold: float = Query(0, ge=0),
    starred_only: bool = False,
    db: Session = Depends(get_db),
):
    # Base query for latest snapshot per ticker
    query = (
        db.query(
            VolumeSnapshot.ticker,
            func.max(VolumeSnapshot.detected_at).label("latest_detected_at"),
        )
        .filter(VolumeSnapshot.promising_score > 0)
    )

    if surge_threshold > 0:
        query = query.filter(VolumeSnapshot.volume_rate >= surge_threshold)

    if price_threshold > 0:
        query = query.filter(VolumeSnapshot.current_price <= price_threshold)

    if starred_only:
        # Join with StarredStock to filter only starred tickers
        query = query.join(
            StarredStock,
            VolumeSnapshot.ticker == StarredStock.ticker
        )

    query = query.group_by(VolumeSnapshot.ticker)
    subq = query.subquery()

    latest_snapshots = (
        db.query(VolumeSnapshot)
        .join(
            subq,
            (VolumeSnapshot.ticker == subq.c.ticker)
            & (VolumeSnapshot.detected_at == subq.c.latest_detected_at),
        )
        .all()
    )

    if not latest_snapshots:
        raise HTTPException(status_code=404, detail="No saved analyses found")

    # Prepare tickers list
    tickers = [snap.ticker for snap in latest_snapshots]

    # Fetch related news impact data
    all_impacts = (
        db.query(StockNewsImpact)
        .filter(StockNewsImpact.ticker.in_(tickers))
        .order_by(StockNewsImpact.created_at.desc())
        .all()
    )

    impact_by_ticker = {}
    for impact in all_impacts:
        impact_by_ticker.setdefault(impact.ticker, []).append(impact)

    results = []

    for vs in latest_snapshots:
        top_news = []
        if vs.top_news:
            try:
                top_news = json.loads(vs.top_news)
            except Exception:
                top_news = []

        # Match news items with impact verdict
        impacts = impact_by_ticker.get(vs.ticker, [])
        impact_headlines = [imp.headline for imp in impacts]

        for news_item in top_news:
            headline = news_item.get("headline", "")
            match = get_close_matches(headline, impact_headlines, n=1, cutoff=0.6)
            if match:
                matched_impact = next((imp for imp in impacts if imp.headline == match[0]), None)
                if matched_impact:
                    news_item["impact_verdict"] = matched_impact.verdict
                    news_item["impact_reason"] = matched_impact.reason
            else:
                news_item["impact_verdict"] = None
                news_item["impact_reason"] = None

        analysis_signal_data = get_latest_analysis_signal_data(db, vs.ticker)
        start_date = datetime.date.today() - datetime.timedelta(days=30)
        prices = (
            db.query(DailyPrice)
            .filter(DailyPrice.ticker == vs.ticker, DailyPrice.date >= start_date)
            .order_by(DailyPrice.date.asc())
            .all()
        )

        downtrend_info = normalize_downtrend_for_json(detect_recent_downtrend(db, vs.ticker))
        price_stats = compute_price_stats(prices, vs.current_price)

        results.append({
            "volume_info": {
                "ticker": vs.ticker,
                "name": vs.name,
                "current_price": vs.current_price,
                "price_change": vs.price_change,
                "volume_rate": vs.volume_rate,
                "money_flow_rate": vs.money_flow_rate,
                "current_volume": vs.current_volume,
                "avg_volume_5d": vs.avg_volume_5d,
                "detected_at": vs.detected_at.isoformat(),
                "reasoning": vs.reasoning,
                "recommendation": vs.recommendation,
                "promising_score": vs.promising_score,
                "top_news": top_news,
                "watchlist_recommendation": vs.watchlist_recommendation,
                "downtrend": downtrend_info,
                "drop_from_high_pct": price_stats.get("drop_from_high_pct"),
                "rebound_from_low_pct": price_stats.get("rebound_from_low_pct"),
                "highest_price": price_stats.get("highest_price"),
                "lowest_price": price_stats.get("lowest_price"),
                "starred": bool(db.query(StarredStock).filter_by(ticker=vs.ticker).first()),  # Add `starred` field
            },
            "analysis_signal": analysis_signal_data,
        })

    return results

def analyze_ticker_by_steps(db: Session, ticker: str, top_n: int = 3, model: str = "gpt-4o") -> Dict:
    # Step 1: Get news
    news = scrape_kabutan_news(ticker, limit=30)
    if not news:
        raise ValueError(f"No news found for ticker {ticker}")

    # Step 2: Generate & save snapshot
    snapshot = analyze_and_snapshot_ticker(
        db=db,
        ticker=ticker,
        surge_threshold=0.0,
        price_threshold=1000,
    )
    if not snapshot:
        raise ValueError(f"{ticker} does not meet surge/price criteria.")

    # Step 3: Retrieve VolumeSnapshot from DB
    volume_info = get_volume_info(db, ticker=ticker)
    if not volume_info:
        raise ValueError(f"No volume data found for {ticker}")

    # Step 4: Analyze with GPT
    return premarket_analyze_with_gpt(
        db=db,
        ticker=ticker,
        news_items=news,
        volume_info=volume_info,
        top_n=top_n,
        model=model,
    )

@router.post("/analyze/{ticker}", response_model=Dict)
def analyze_single_ticker(
    ticker: str,
    top_n: int = 3,
    model: str = "gpt-4o",
    db: Session = Depends(get_db)
):
    try:
        result = analyze_ticker_by_steps(db, ticker, top_n, model)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/analyze_starred", response_model=List[Dict])
def analyze_starred_tickers(
    top_n: int = 3,
    # model: str = "gpt-4o",
    model: str = "gpt-3.5-turbo",
    db: Session = Depends(get_db)
):
    starred_tickers = db.query(StarredStock.ticker).all()
    print(f"====starred_tickers={starred_tickers}")
    ticker_list = [t[0] for t in starred_tickers]  # convert list of tuples to list of strings
    results = []

    for ticker in ticker_list:
        print(f"====ticker={ticker}")
        try:
            result = analyze_ticker_by_steps(db, ticker, top_n, model)
            results.append(result)
        except ValueError as e:
            print(f"Skipping {ticker}: {e}")
            continue

    return results

@router.post("/scan_news/{ticker}", response_model=Dict)
def scan_news_for_ticker(
    ticker: str,
    top_n: int = 3,
    model: str = "gpt-4o",
    db: Session = Depends(get_db),
):
    """
    Analyze news for a specific ticker using GPT. 
    Caches headline hash to avoid duplicate GPT calls.
    """

    result = scan_and_analyze_news_for_ticker(db, ticker, top_n=top_n, model=model)
    return {
        "ticker": ticker,
        "status": "updated" if result else "skipped (cached)",
        "top_n": top_n,
        "verdicts": result or [],
    }

def scan_and_analyze_low_cap_tickers(
    db: Session,
    from_page: int,
    to_page: int,
    price_threshold: float,
    top_n: int,
    model: str
) -> Tuple[List[str], List[str]]:
    tickers = fetch_low_cap_tickers(from_page, to_page, price_threshold)
    alert_tickers = []

    for ticker in tickers:
        try:
            impacts = scan_and_analyze_news_for_ticker(db, ticker, top_n=top_n, model=model)
            if impacts and any(i["verdict"] in {"Decisive", "Great", "Good"} for i in impacts):
                alert_tickers.append(ticker)
        except Exception as e:
            print(f"⚠️ Error scanning {ticker}: {e}")
            continue

    return tickers, alert_tickers

@router.post("/scan_news_bulk", response_model=Dict)
def scan_news_for_low_cap_bulk(
    from_page: int = 1,
    to_page: int = 5,
    price_threshold: float = 300,
    top_n: int = 3,
    model: str = "gpt-4o",
    db: Session = Depends(get_db),
):
    tickers, alert_tickers = scan_and_analyze_low_cap_tickers(db, from_page, to_page, price_threshold, top_n, model)
    return {
        "scanned_tickers": tickers,
        "alert_tickers": alert_tickers,
        "from_page": from_page,
        "to_page": to_page,
        "price_threshold": price_threshold,
    }

auto_scan_stop_event = Event()

@router.post("/auto_scan_news", response_model=Dict)
def auto_scan_news(
    interval_minutes: int = 60,
    from_page: int = 1,
    to_page: int = 5,
    price_threshold: float = 300,
    top_n: int = 3,
    model: str = "gpt-4o",
    db: Session = Depends(get_db),
):
    auto_scan_stop_event.clear()
    # This endpoint can trigger the same scanning logic, and you can extend it with scheduling or state management later
    tickers, alert_tickers = scan_and_analyze_low_cap_tickers(db, from_page, to_page, price_threshold, top_n, model)
    
    # Optionally: store or log scan time, results, etc.
    
    return {
        "message": f"Auto scan complete. Interval: {interval_minutes} minutes",
        "scanned_tickers": tickers,
        "alert_tickers": alert_tickers,
    }

@router.post("/stop_auto_scan")
def stop_auto_scan():
    auto_scan_stop_event.set()
    return {"message": "Auto scan stopped"}

@router.get("/positive_news", response_model=List[Dict])
def get_positive_news_api(db: Session = Depends(get_db)):
    return get_positive_news(db)
