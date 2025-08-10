import datetime
import json
from difflib import get_close_matches
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import Dict, List, Optional, Tuple
from threading import Event
from app.schemas import ScanParams

from app.db.db import SessionLocal
from app.models import VolumeSnapshot, StarredStock, WatchList, DailyPrice
from app.utils.longterm.jpx_perpbr_industry import update_and_get_industry_indicators
from app.utils.longterm.yahoo_indicators import fetch_current_indicators
from app.utils.premarket.uptrend_detector import get_uptrend_analysis, normalize_uptrend_for_json
from app.utils.premarket.downtrend_detector import get_downtrend_analysis, normalize_downtrend_for_json
from app.utils.premarket.pre_volume_surge_scraper import analyze_and_snapshot_ticker, fetch_ranked_volume_tickers, scan_and_save_pre_market_volume_surges
from app.utils.shortterm.kabutan_news_ticker import get_volume_info, scrape_kabutan_news
from app.utils.premarket.pre_gpt_analyzer import get_latest_trading_day, premarket_analyze_with_gpt, check_market_hours
from app.utils.premarket.pre_scan_news import fetch_low_cap_tickers, get_positive_news, scan_and_analyze_news_for_ticker
from app.api.shortterm_apis import get_latest_analysis_signal_data
from app.utils.premarket.watchlist import append_batch_to_watchlist, read_watchlist, remove_from_watchlist_csv, add_to_watchlist_csv

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
def analyze_vs_single_ticker(
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

@router.get("/scrape_kabutan_news/{ticker}")
def scrape_kabutan_news_(ticker: str, days_threshold: float):
    return scrape_kabutan_news(ticker, days_threshold)

@router.post("/volume_scan")
def trigger_volume_scan(
    params: ScanParams,
    db: Session = Depends(get_db)
):
    is_market_hours = check_market_hours(db)
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
                is_market_hours=is_market_hours
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
                premarket_analyze_with_gpt(db=db, ticker=ticker, news_items=news, volume_info=volume_info, top_n=3, model="gpt-4o", is_market_hours=is_market_hours)
            except Exception as e:
                print(f"⚠️ GPT-4o analysis failed for {ticker}: {e}")

    return {"message": f"Volume scan complete. {len(tickers)} tickers analyzed."}

def get_recent_price_data(db: Session, ticker: str, limit: int = 15) -> List[Dict]:
    recent_prices_query = (
        db.query(DailyPrice)
        .filter(DailyPrice.ticker == ticker)
        .order_by(DailyPrice.date.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "date": p.date.isoformat(),
            "open": p.open,
            "high": p.high,
            "low": p.low,
            "close": p.close,
        }
        for p in reversed(recent_prices_query)  # oldest to newest
    ]

@router.get("/get_saved_vs", response_model=List[Dict])
def get_all_saved_volume_analyses(
    surge_threshold: float = Query(0, ge=0),
    price_threshold: float = Query(0, ge=0),
    starred_only: bool = False,
    watched_only: bool = False,
    detected_at_max_age_days: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    query = (
        db.query(
            VolumeSnapshot.ticker,
            func.max(VolumeSnapshot.detected_at).label("latest_detected_at"),
        )
        .filter(VolumeSnapshot.promising_score > 0)
    )

    if detected_at_max_age_days:
        threshold_time = datetime.datetime.utcnow() - datetime.timedelta(days=detected_at_max_age_days)
        query = query.filter(VolumeSnapshot.detected_at >= threshold_time)

    if surge_threshold > 0:
        query = query.filter(VolumeSnapshot.volume_rate >= surge_threshold)

    if price_threshold > 0:
        query = query.filter(VolumeSnapshot.current_price <= price_threshold)

    if starred_only and watched_only:
        query = query.outerjoin(StarredStock, VolumeSnapshot.ticker == StarredStock.ticker) \
                    .outerjoin(WatchList, VolumeSnapshot.ticker == WatchList.ticker) \
                    .filter(
                        or_(
                            StarredStock.ticker != None,
                            WatchList.ticker != None
                        )
                    )
    elif starred_only:
        query = query.join(StarredStock, VolumeSnapshot.ticker == StarredStock.ticker)
    elif watched_only:
        query = query.join(WatchList, VolumeSnapshot.ticker == WatchList.ticker)

    query = query.group_by(VolumeSnapshot.ticker)
    subq = query.subquery()

    latest_snapshots = (
        db.query(VolumeSnapshot)
        .join(subq, (VolumeSnapshot.ticker == subq.c.ticker) & (VolumeSnapshot.detected_at == subq.c.latest_detected_at))
        .all()
    )

    if not latest_snapshots:
        raise HTTPException(status_code=404, detail="No saved analyses found")

    results = []

    for vs in latest_snapshots:
        top_news = []
        if vs.top_news:
            try:
                top_news = json.loads(vs.top_news)
            except Exception:
                top_news = []

        analysis_signal_data = get_latest_analysis_signal_data(db, vs.ticker)

        # downtrend_model = get_downtrend_analysis(db, vs.ticker)
        # downtrend_info = normalize_downtrend_for_json(downtrend_model)

        # uptrend_model = get_uptrend_analysis(db, vs.ticker)
        # uptrend_info = normalize_uptrend_for_json(uptrend_model)

        # price_stats = {
        #     "highest_price": downtrend_info.get("highest_price"),
        #     "lowest_price": downtrend_info.get("lowest_price"),
        #     "drop_from_high_pct": downtrend_info.get("drop_from_high_pct"),
        #     "rebound_from_low_pct": downtrend_info.get("rebound_from_low_pct"),
        # }

        recent_prices = get_recent_price_data(db, vs.ticker)

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
                "spiked": vs.spiked,
                "spike_next": vs.spike_next,
                "top_news": top_news,
                "highest_impact_keyword": vs.highest_impact_keyword,
                "highest_impact_rank": vs.highest_impact_rank,
                # "downtrend": downtrend_info,
                # "uptrend": uptrend_info,
                # "drop_from_high_pct": price_stats["drop_from_high_pct"],
                # "rebound_from_low_pct": price_stats["rebound_from_low_pct"],
                # "highest_price": price_stats["highest_price"],
                # "lowest_price": price_stats["lowest_price"],
                "starred": bool(db.query(StarredStock).filter_by(ticker=vs.ticker).first()),
                "watched": bool(db.query(WatchList).filter_by(ticker=vs.ticker).first()),
                "momentum_score": vs.momentum_score,
                "momentum_confidence": vs.momentum_confidence,
                "momentum_signals": vs.momentum_signals,
                "note": vs.note,
                "recent_prices": recent_prices,
            },
            "analysis_signal": analysis_signal_data,
        })

    return results

@router.get("/saved_analysis/{ticker}", response_model=Dict)
def get_premarket_saved_analysis(ticker: str, db: Session = Depends(get_db)):
    vs = (
        db.query(VolumeSnapshot)
        .filter(VolumeSnapshot.ticker == ticker)
        .filter(VolumeSnapshot.promising_score > 0)
        .order_by(VolumeSnapshot.detected_at.desc())
        .first()
    )

    if not vs:
        raise HTTPException(status_code=404, detail=f"No saved premarket analysis found for {ticker}")

    # Parse top news
    top_news = []
    if vs.top_news:
        try:
            top_news = json.loads(vs.top_news)
        except Exception:
            top_news = []

    # # Downtrend info
    # downtrend_model = get_downtrend_analysis(db, ticker)
    # downtrend_info = normalize_downtrend_for_json(downtrend_model)

    # # Uptrend info
    # uptrend_model = get_uptrend_analysis(db, ticker)
    # uptrend_info = normalize_uptrend_for_json(uptrend_model)

    # # Use price stats from cached downtrend info directly
    # price_stats = {
    #     "highest_price": downtrend_info.get("highest_price"),
    #     "lowest_price": downtrend_info.get("lowest_price"),
    #     "drop_from_high_pct": downtrend_info.get("drop_from_high_pct"),
    #     "rebound_from_low_pct": downtrend_info.get("rebound_from_low_pct"),
    # }

    # Technical signals (RSI, MACD, etc.)
    analysis_signal_data = get_latest_analysis_signal_data(db, ticker)

    # Long-term indicators
    # stock_data = fetch_current_indicators(ticker)
    # if not stock_data:
    #     raise HTTPException(status_code=500, detail=f"Could not fetch indicators for {ticker}")

    # industry_name = stock_data.get("industry", "")
    # industry_data = update_and_get_industry_indicators(industry_name, db)

    # if industry_data:
    #     industry_info = industry_data[0]
    #     industry_name = industry_info.get("industry", "N/A")
    #     industry_per = industry_info.get("per", "N/A")
    #     industry_pbr = industry_info.get("pbr", "N/A")
    #     industry_roe = industry_info.get("roe", "N/A")
    # else:
    #     industry_name = industry_per = industry_pbr = industry_roe = "N/A"

    # longterm_info = {
    #     "industry_name": industry_name,
    #     "stock_per": stock_data.get("per", "N/A"),
    #     "industry_per": industry_per,
    #     "stock_pbr": stock_data.get("pbr", "N/A"),
    #     "industry_pbr": industry_pbr,
    #     "stock_roe": stock_data.get("roe", "N/A"),
    #     "industry_roe": industry_roe,
    #     "eps": stock_data.get("eps", "N/A"),
    #     "bps": stock_data.get("bps", "N/A"),
    #     "dividend_yield": stock_data.get("dividend_yield", "N/A"),
    #     "debt_ratio": stock_data.get("debt_ratio", "N/A"),
    #     "market_cap": stock_data.get("market_cap", "N/A"),
    #     "summary": (
    #         f"- PER: {stock_data.get('per', 'N/A')} vs Industry Avg: {industry_per}\n"
    #         f"- PBR: {stock_data.get('pbr', 'N/A')} vs Industry Avg: {industry_pbr}\n"
    #         f"- ROE: {stock_data.get('roe', 'N/A')}% vs Industry Avg: {industry_roe}%\n"
    #         f"- EPS: {stock_data.get('eps', 'N/A')} / BPS: {stock_data.get('bps', 'N/A')}\n"
    #         f"- Dividend Yield: {stock_data.get('dividend_yield', 'N/A')}%\n"
    #         f"- Debt Ratio: {stock_data.get('debt_ratio', 'N/A')}%\n"
    #         f"- Market Cap: ¥{stock_data.get('market_cap', 'N/A')}\n"
    #     )
    # }
    # longterm_info = ""

    recent_prices = get_recent_price_data(db, ticker)

    return {
        "volume_info": {
            "ticker": ticker,
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
            "spiked": vs.spiked,
            "spike_next": vs.spike_next,
            "top_news": top_news,
            "highest_impact_keyword": vs.highest_impact_keyword,
            "highest_impact_rank": vs.highest_impact_rank,
            # "downtrend": downtrend_info,
            # "uptrend": uptrend_info,
            # "drop_from_high_pct": price_stats["drop_from_high_pct"],
            # "rebound_from_low_pct": price_stats["rebound_from_low_pct"],
            # "highest_price": price_stats["highest_price"],
            # "lowest_price": price_stats["lowest_price"],
            "momentum_score": vs.momentum_score,
            "momentum_confidence": vs.momentum_confidence,
            "momentum_signals": vs.momentum_signals,
            "starred": bool(db.query(StarredStock).filter_by(ticker=ticker).first()),
            "watched": bool(db.query(WatchList).filter_by(ticker=ticker).first()),
            "kabutan_chart_url": f"https://kabutan.jp/stock/chart?code={ticker}",
            "recent_prices": recent_prices,
        },
        "analysis_signal": analysis_signal_data,
        # "longterm_info": longterm_info,
    }

class NoteRequest(BaseModel):
    note: str

@router.post("/set_note/{ticker}")
def set_note(
    ticker: str,
    request: NoteRequest,
    db: Session = Depends(get_db),
):
    latest = (
        db.query(VolumeSnapshot)
        .filter(VolumeSnapshot.ticker == ticker)
        .order_by(VolumeSnapshot.detected_at.desc())
        .first()
    )

    if not latest:
        raise HTTPException(status_code=404, detail="VolumeSnapshot not found")

    latest.note = request.note
    db.commit()
    return {"status": "ok", "ticker": ticker, "note": request.note}

def analyze_ticker_by_steps(db: Session, ticker: str, top_n: int = 3, model: str = "gpt-4o", is_market_hours = False) -> Dict:
    # Step 1: Get news
    news = scrape_kabutan_news(ticker, limit=30)
    if not news:
        raise ValueError(f"No news found for ticker {ticker}")

    # Step 2: Generate & save snapshot
    snapshot = analyze_and_snapshot_ticker(
        db=db,
        ticker=ticker,
        surge_threshold=0.0,
        price_threshold=0,
    )
    if not snapshot:
        raise ValueError(f"{ticker} does not meet surge/price criteria.")

    # Step 3: Retrieve VolumeSnapshot from DB
    volume_info = get_volume_info(db, ticker=ticker)
    if not volume_info:
        raise ValueError(f"No volume data found for {ticker}")

    # Step 4: Analyze with GPT
    premarket_analyze_with_gpt(
        db=db,
        ticker=ticker,
        news_items=news,
        volume_info=volume_info,
        is_market_hours=is_market_hours,
        top_n=top_n,
        model=model,
    )
    return {"message": f"Analyzing complete. {ticker} analyzed."}

@router.post("/analyze/{ticker}", response_model=Dict)
def analyze_single_ticker(
    ticker: str,
    top_n: int = 3,
    model: str = "gpt-4o",
    db: Session = Depends(get_db)
):
    is_market_hours = check_market_hours(db)
    try:
        result = analyze_ticker_by_steps(db, ticker, top_n, model, is_market_hours=is_market_hours)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/analyze_starred", response_model=List[Dict])
def analyze_starred_tickers(
    top_n: int = 3,
    model: str = "gpt-4o",
    db: Session = Depends(get_db)
):
    is_market_hours = check_market_hours(db)
    starred_tickers = db.query(StarredStock.ticker).all()
    ticker_list = [t[0] for t in starred_tickers]  # convert list of tuples to list of strings
    results = []

    for ticker in ticker_list:
        try:
            result = analyze_ticker_by_steps(db, ticker, top_n, model, is_market_hours=is_market_hours)
            results.append(result)
        except ValueError as e:
            print(f"Skipping {ticker}: {e}")
            continue

    return results

@router.post("/analyze_watch_list", response_model=List[Dict])
def analyze_watch_list(
    top_n: int = 3,
    model: str = "gpt-4o",
    db: Session = Depends(get_db)
):
    extra_guidance = "### FOCUS ON **POSSBLE RE-SPIKE**. If there is possible re-spike, provide more details about **HOW TO ENTRY**"
    is_market_hours = check_market_hours(db)
    watchlist_tickers = db.query(WatchList.ticker).all()
    ticker_list = [t[0] for t in watchlist_tickers]  # convert list of tuples to list of strings
    results = []

    for ticker in ticker_list:
        try:
            result = analyze_ticker_by_steps(db, ticker, top_n, model, is_market_hours=is_market_hours, extra_guidance=extra_guidance)
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
    result = scan_and_analyze_news_for_ticker(db, ticker, top_n=top_n, days_threshold=30, model=model)
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
    model: str,
    days_threshold: float,
) -> Tuple[List[str], List[str]]:
    tickers = fetch_low_cap_tickers(from_page, to_page, price_threshold)
    alert_tickers = []

    for ticker in tickers:
        try:
            impacts = scan_and_analyze_news_for_ticker(
                db, ticker,
                top_n=top_n,
                days_threshold=days_threshold,
                model=model
            )
            if impacts and any(i["verdict"] in {"S+", "S", "A+", "A", "A-", "B"} for i in impacts):
                alert_tickers.append(ticker)
        except Exception as e:
            print(f"⚠️ Error scanning {ticker}: {e}")
            continue

    return tickers, alert_tickers

@router.post("/scan_news_bulk", response_model=Dict)
def scan_news_for_low_cap_bulk(
    params: ScanParams,
    db: Session = Depends(get_db),
    top_n: int = 3,
    model: str = "gpt-4o",
):
    tickers, alert_tickers = scan_and_analyze_low_cap_tickers(
        db,
        from_page=params.from_page,
        to_page=params.to_page,
        price_threshold=params.price_threshold,
        top_n=top_n,
        model=model,
        days_threshold=params.days_threshold,
    )
    return {
        "scanned_tickers": tickers,
        "alert_tickers": alert_tickers,
        "from_page": params.from_page,
        "to_page": params.to_page,
        "price_threshold": params.price_threshold,
        "days_threshold": params.days_threshold,
    }


@router.get("/positive_news", response_model=List[Dict])
def get_positive_news_api(db: Session = Depends(get_db)):
    return get_positive_news(db)

@router.get("/latest_trading_day", response_model=Optional[datetime.date])
def get_latest_trading_day_api(db: Session = Depends(get_db)):
    return get_latest_trading_day(db)

@router.get("/get_watchlist")
def get_watchlist(db: Session = Depends(get_db)):
    tickers = read_watchlist()
    results = []

    for ticker in tickers:
        snapshot = db.query(VolumeSnapshot).filter_by(ticker=ticker).first()

        if not snapshot:
            # Analyze and save snapshot if not exists
            snapshot = analyze_and_snapshot_ticker(
                db=db,
                ticker=ticker,
                surge_threshold=0.0,
                price_threshold=0,
            )

        if snapshot:
            results.append({
                "ticker": ticker,
                "name": snapshot.name,
                "current_price": snapshot.current_price
            })

    return {"watchlist": results}

@router.post("/add_watchlist_batch")
def add_watchlist_batch(tickers_str: str = Query(...), db: Session = Depends(get_db)):
    added = append_batch_to_watchlist(tickers_str)
    for ticker in added:
        if not db.query(WatchList).filter_by(ticker=ticker).first():
            db.add(WatchList(ticker=ticker))
    db.commit()
    return {"added": added}

@router.delete("/watchlist/{ticker}")
def delete_watchlist_ticker(ticker: str, db: Session = Depends(get_db)):
    remove_from_watchlist_csv(ticker)
    entry = db.query(WatchList).filter(WatchList.ticker == ticker).first()
    if not entry:
        raise HTTPException(status_code=404, detail=f"{ticker} not found in watchlist.")
    
    db.delete(entry)
    db.commit()
    return {"detail": f"{ticker} removed from watchlist."}

# For Use
@router.post("/{ticker}/watch_stock")
def star_stock(ticker: str, db: Session = Depends(get_db)):
    add_to_watchlist_csv(ticker)
    existing = db.query(WatchList).filter_by(ticker=ticker).first()
    if not existing:
        new_star = WatchList(ticker=ticker)
        db.add(new_star)
        db.commit()
    return {"status": "watched"}

# For Use
@router.delete("/{ticker}/unwatch_stock")
def unstar_stock(ticker: str, db: Session = Depends(get_db)):
    remove_from_watchlist_csv(ticker)
    existing = db.query(WatchList).filter_by(ticker=ticker).first()
    if existing:
        db.delete(existing)
        db.commit()
    return {"status": "watched"}