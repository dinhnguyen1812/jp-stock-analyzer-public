import asyncio
import datetime
import json
from difflib import get_close_matches
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import Any, Dict, List, Optional, Tuple
from threading import Event
from app.schemas import ScanParams

from app.db.db import SessionLocal
from app.models import VolumeSnapshot, StarredStock, WatchList, DailyPrice

from app.utils.longterm.jpx_perpbr_industry import update_and_get_industry_indicators
from app.utils.longterm.yahoo_indicators import fetch_current_indicators

from app.utils.shortterm.volume_surge_scraper import fetch_intraday_prices
from app.utils.shortterm.kabutan_news_ticker import get_volume_info, scrape_kabutan_news
from app.api.shortterm_apis import get_latest_analysis_signal_data

from app.utils.premarket.uptrend_detector import get_uptrend_analysis, normalize_uptrend_for_json
from app.utils.premarket.downtrend_detector import get_downtrend_analysis, normalize_downtrend_for_json
from app.utils.premarket.pre_volume_surge_scraper import analyze_and_snapshot_ticker, fetch_name_and_price_change_from_yahoo, fetch_ranked_volume_tickers, scan_and_save_pre_market_volume_surges
from app.utils.premarket.pre_gpt_analyzer import analyze_ticker_by_steps, get_latest_trading_day, premarket_analyze_with_gpt, check_market_hours
from app.utils.premarket.pre_scan_news import fetch_low_cap_tickers, get_positive_news, scan_and_analyze_news_for_ticker
from app.utils.premarket.watchlist import append_batch_to_watchlist, read_watchlist, remove_from_watchlist_csv, add_to_watchlist_csv
from app.utils.premarket.intraday_analyzer import analyze_live_ticker, parse_yahoo_intraday
from app.utils.premarket.spike_pattern import compute_spike_analysis_100, get_spike_analysis, normalize_spike_for_json
from app.utils.premarket.kabutan_news_live import background_market_news_scanner, scan_market_news_once, scrape_kabutan_marketnews
from app.utils.premarket.flat_analysis import analyze_flat_pattern
from app.utils.shortterm.price_updater import fetch_and_save_price_history

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
    # is_market_hours = check_market_hours(db)

    # Step 1: Scan and save volume surge data (pre-market)
    tickers = scan_and_save_pre_market_volume_surges(
        db=db,
        surge_threshold=params.surge_threshold,
        price_threshold=params.price_threshold,
        from_page=params.from_page,
        to_page=params.to_page,
    )

    # Step 2: First pass — GPT-3.5 analysis
    for ticker in tickers:
        try:
            analyze_ticker_by_steps(
                db=db,
                ticker=ticker,
                top_n=3,
                model="gpt-3.5-turbo",
                # is_market_hours=is_market_hours
                detected_type="volume_surge"
            )
        except Exception as e:
            print(f"⚠️ GPT-3.5 analysis failed for {ticker}: {e}")

    # Step 3: Second pass — GPT-4o for promising tickers
    for ticker in tickers:
        volume_info = get_volume_info(db, ticker=ticker)
        if not volume_info:
            continue
        if volume_info.news_score is not None and volume_info.news_score >= 50:
            try:
                print(f"🔁 Re-analyzing {ticker} with GPT-4o...")
                analyze_ticker_by_steps(
                    db=db,
                    ticker=ticker,
                    top_n=3,
                    model="gpt-4o",
                    # is_market_hours=is_market_hours
                    detected_type="volume_surge"
                )
            except Exception as e:
                print(f"⚠️ GPT-4o analysis failed for {ticker}: {e}")

    return {"message": f"Volume scan complete. {len(tickers)} tickers analyzed."}

def get_recent_price_data(
    db: Session, ticker: str, limit: int = 50, analyze_intraday=False
) -> List[Dict]:
    recent_prices_query = (
        db.query(DailyPrice)
        .filter(DailyPrice.ticker == ticker)
        .order_by(DailyPrice.date.desc())
        .limit(limit)
        .all()
    )

    prices = [
        {
            "date": p.date.isoformat(),
            "open": p.open,
            "high": p.high,
            "low": p.low,
            "close": p.close,
        }
        for p in reversed(recent_prices_query)  # oldest to newest
    ]

    if analyze_intraday:
        intraday_close, intraday_open, intraday_high, intraday_low = fetch_intraday_prices(ticker)
        prices.append({
            "date": datetime.datetime.now().date().isoformat(),
            "open": intraday_open,
            "high": intraday_high,
            "low": intraday_low,
            "close": intraday_close,
        })

    return prices

@router.get("/get_saved_vs", response_model=List[Dict])
def get_all_saved_volume_analyses(
    surge_threshold: float = Query(0, ge=0),
    price_threshold: float = Query(0, ge=0),
    starred_only: bool = False,
    watched_only: bool = False,
    detected_at_max_age_days: float = Query(1.0, ge=0.0),
    db: Session = Depends(get_db),
):
    analyze_intraday = check_market_hours(db)

    # Base query for latest snapshots
    query = (
        db.query(
            VolumeSnapshot.ticker,
            func.max(VolumeSnapshot.detected_at).label("latest_detected_at"),
        )
        .filter(VolumeSnapshot.news_score > 0)
    )

    # Compute time threshold
    threshold_time = datetime.datetime.utcnow() - datetime.timedelta(days=detected_at_max_age_days)

    # Always include recent snapshots
    time_filter = VolumeSnapshot.detected_at >= threshold_time

    # Always include starred or watched stocks, regardless of time
    starred_subq = db.query(StarredStock.ticker).subquery()
    watched_subq = db.query(WatchList.ticker).subquery()

    query = query.filter(
        or_(
            time_filter,
            VolumeSnapshot.ticker.in_(starred_subq),
            VolumeSnapshot.ticker.in_(watched_subq),
        )
    )

    if surge_threshold > 0:
        query = query.filter(VolumeSnapshot.volume_rate >= surge_threshold)

    # if price_threshold > 0:
    #     query = query.filter(VolumeSnapshot.current_price <= price_threshold)

    # Narrow down to explicit flags if user requested
    if starred_only and watched_only:
        query = query.outerjoin(starred_subq, VolumeSnapshot.ticker == starred_subq.c.ticker) \
                     .outerjoin(watched_subq, VolumeSnapshot.ticker == watched_subq.c.ticker) \
                     .filter(
                         or_(
                             starred_subq.c.ticker != None,
                             watched_subq.c.ticker != None
                         )
                     )
    elif starred_only:
        query = query.join(starred_subq, VolumeSnapshot.ticker == starred_subq.c.ticker)
    elif watched_only:
        query = query.join(watched_subq, VolumeSnapshot.ticker == watched_subq.c.ticker)

    query = query.group_by(VolumeSnapshot.ticker)
    subq = query.subquery()

    latest_snapshots = (
        db.query(VolumeSnapshot)
        .join(
            subq,
            (VolumeSnapshot.ticker == subq.c.ticker)
            & (VolumeSnapshot.detected_at == subq.c.latest_detected_at)
        )
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
        spike_info = [normalize_spike_for_json(get_spike_analysis(db, vs.ticker))]
        recent_prices = get_recent_price_data(db, vs.ticker, analyze_intraday=analyze_intraday)
        if vs.name == vs.ticker:
            name, _ = fetch_name_and_price_change_from_yahoo(vs.ticker)
        else:
            name = vs.name

        results.append({
            "volume_info": {
                "ticker": vs.ticker,
                "name": name,
                "current_price": vs.current_price,
                "price_change": vs.price_change,
                "volume_rate": vs.volume_rate,
                "money_flow_rate": vs.money_flow_rate,
                "current_volume": vs.current_volume,
                "avg_volume_5d": vs.avg_volume_5d,
                "detected_at": vs.detected_at.isoformat(),
                "reasoning": vs.reasoning,
                "recommendation": vs.recommendation,
                "promising_score": round(
                    0.7 * vs.news_score 
                    + 0.3 * spike_info[0]['score'] 
                    + (15 if spike_info[0]['score'] == 0 else 0),
                    1
                ),
                "news_score": vs.news_score,
                "top_news": top_news,
                "highest_impact_keyword": vs.highest_impact_keyword,
                "highest_impact_rank": vs.highest_impact_rank,
                "model": vs.model,
                "starred": bool(db.query(StarredStock).filter_by(ticker=vs.ticker).first()),
                "watched": bool(db.query(WatchList).filter_by(ticker=vs.ticker).first()),
                "momentum_score": vs.momentum_score,
                "momentum_confidence": vs.momentum_confidence,
                "momentum_signals": vs.momentum_signals,
                "note": vs.note,
                "recent_prices": recent_prices,
                "spike_info": spike_info,
            },
            "analysis_signal": analysis_signal_data,
        })

    return results

@router.get("/saved_analysis/{ticker}", response_model=Dict)
def get_premarket_saved_analysis(ticker: str, db: Session = Depends(get_db)):
    vs = (
        db.query(VolumeSnapshot)
        .filter(VolumeSnapshot.ticker == ticker)
        .filter(VolumeSnapshot.news_score > 0)
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
    spike_info = [normalize_spike_for_json(get_spike_analysis(db, ticker))]

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
            "promising_score": round(0.7 * vs.news_score + 0.3 * spike_info[0]['score'], 1),
            "news_score": vs.news_score,
            # "spiked": vs.spiked,
            # "spike_next": vs.spike_next,
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
            "spike_info": spike_info,
        },
        "analysis_signal": analysis_signal_data,
        # "longterm_info": longterm_info,
    }

class NoteRequest(BaseModel):
    note: str

import json
from pathlib import Path

NOTES_FILE = Path(__file__).parent.parent / "utils" / "premarket" / "notes.json"

def load_ticker_notes() -> dict:
    if NOTES_FILE.exists():
        try:
            with open(NOTES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Failed to load notes: {e}")
            return {}
    return {}

def save_ticker_notes(notes: dict):
    try:
        with open(NOTES_FILE, "w", encoding="utf-8") as f:
            json.dump(notes, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Failed to save notes: {e}")

@router.post("/set_note/{ticker}")
def set_note(
    ticker: str,
    request: NoteRequest,
    db: Session = Depends(get_db),
):
    # Update latest snapshot
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

    # 🔹 Update JSON file
    notes = load_ticker_notes()
    notes[ticker] = request.note
    save_ticker_notes(notes)

    return {"status": "ok", "ticker": ticker, "note": request.note}

@router.post("/analyze/{ticker}", response_model=Dict)
def analyze_single_ticker(
    ticker: str,
    top_n: int = 3,
    model: str = "gpt-4o",
    # model: str = "gpt-3.5-turbo",
    db: Session = Depends(get_db)
):
    # is_market_hours = check_market_hours(db)

    # Run analysis with GPT-3.5 first
    analyze_ticker_by_steps(
        db=db,
        ticker=ticker,
        top_n=top_n,
        model=model,
        # is_market_hours=is_market_hours,
        detected_type="single"
    )

    # # Reanalyze with GPT-4o if promising
    # volume_info = get_volume_info(db, ticker=ticker)
    # if volume_info and volume_info.news_score is not None and volume_info.news_score >= 50:
    #     try:
    #         analyze_ticker_by_steps(
    #             db=db,
    #             ticker=ticker,
    #             top_n=top_n,
    #             model="gpt-4o",
    #             # is_market_hours=is_market_hours,
    #             detected_type="single"
    #         )
    #     except Exception as e:
    #         print(f"⚠️ GPT-4o analysis failed for {ticker}: {e}")

    # Return confirmation message
    return {"message": f"Analysis complete for {ticker}"}

@router.post("/analyze_tickers", response_model=Dict)
def analyze_multiple_tickers(
    tickers: str,  # Comma-separated string
    top_n: int = 3,
    model: str = "gpt-4o",
    db: Session = Depends(get_db)
):
    tickers_list = [t.strip() for t in tickers.split(",") if t.strip()]
    results = []

    for ticker in tickers_list:
        # Run analysis with GPT-3.5 first
        analyze_ticker_by_steps(
            db=db,
            ticker=ticker,
            top_n=top_n,
            model="gpt-3.5-turbo",
            detected_type="multiple"
        )

        # Reanalyze with GPT-4o if promising
        volume_info = get_volume_info(db, ticker=ticker)
        if volume_info and volume_info.news_score is not None and volume_info.news_score >= 50:
            try:
                analyze_ticker_by_steps(
                    db=db,
                    ticker=ticker,
                    top_n=top_n,
                    model="gpt-4o",
                    detected_type="multiple"
                )
            except Exception as e:
                print(f"⚠️ GPT-4o analysis failed for {ticker}: {e}")

        results.append({"ticker": ticker, "status": "Analysis complete"})

    return {"results": results}

@router.post("/analyze_starred", response_model=List[Dict])
def analyze_starred_tickers(
    top_n: int = 3,
    db: Session = Depends(get_db)
):
    # is_market_hours = check_market_hours(db)

    # Get all tickers in WatchList
    watchlist_tickers = [t[0] for t in db.query(WatchList.ticker).all()]

    # Get starred tickers excluding those in watchlist
    starred_tickers = [
        t[0]
        for t in db.query(StarredStock.ticker)
        .filter(~StarredStock.ticker.in_(watchlist_tickers))
        .all()
    ]

    results = []

    for ticker in starred_tickers:
        try:
            # First pass: GPT-3.5-turbo
            analyze_ticker_by_steps(
                db=db,
                ticker=ticker,
                top_n=top_n,
                model="gpt-3.5-turbo",
                # is_market_hours=is_market_hours,
                detected_type="starred"
            )

            # Check if promising for reanalysis
            volume_info = get_volume_info(db, ticker=ticker)
            if volume_info and volume_info.news_score is not None and volume_info.news_score >= 50:
                try:
                    analyze_ticker_by_steps(
                        db=db,
                        ticker=ticker,
                        top_n=top_n,
                        model="gpt-4o",
                        # is_market_hours=is_market_hours,
                        detected_type="starred"
                    )
                except Exception as e:
                    print(f"⚠️ GPT-4o analysis failed for {ticker}: {e}")

            results.append({"message": f"Analysis complete for {ticker}"})

        except ValueError as e:
            print(f"Skipping {ticker}: {e}")
            continue

    return results

@router.post("/analyze_watch_list", response_model=List[Dict])
def analyze_watch_list(
    top_n: int = 3,
    db: Session = Depends(get_db)
):
    extra_guidance = "### FOCUS ON **FLAT PATTERN** OR **POSSIBLE RE-SPIKE**."
    # is_market_hours = check_market_hours(db)
    watchlist_tickers = [t[0] for t in db.query(WatchList.ticker).all()]
    results = []

    for ticker in watchlist_tickers:
        try:
            # First pass: GPT-3.5-turbo with extra guidance
            analyze_ticker_by_steps(
                db=db,
                ticker=ticker,
                top_n=top_n,
                model="gpt-3.5-turbo",
                # is_market_hours=is_market_hours,
                extra_guidance=extra_guidance,
                detected_type="watchlist"
            )

            # # Check if promising for reanalysis
            # volume_info = get_volume_info(db, ticker=ticker)
            # if volume_info and volume_info.news_score is not None and volume_info.news_score >= 50:
            #     try:
            #         analyze_ticker_by_steps(
            #             db=db,
            #             ticker=ticker,
            #             top_n=top_n,
            #             model="gpt-4o",
            #             # is_market_hours=is_market_hours,
            #             extra_guidance=extra_guidance,
            #             detected_type="watchlist"
            #         )
            #     except Exception as e:
            #         print(f"⚠️ GPT-4o analysis failed for {ticker}: {e}")

            results.append({"message": f"Analysis complete for {ticker}"})

        except ValueError as e:
            print(f"Skipping {ticker}: {e}")
            continue

    return results

@router.post("/scan_news/{ticker}", response_model=Dict)
def scan_news_for_ticker(
    ticker: str,
    top_n: int = 3,
    model: str = "gpt-3.5-turbo",
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
    failed_tickers = []

    for ticker in tickers:
        try:
            scan_and_analyze_news_for_ticker(
                db, ticker,
                top_n=top_n,
                days_threshold=days_threshold,
                model=model
            )
        except Exception as e:
            print(f"⚠️ Error scanning {ticker}: {e}")
            failed_tickers.append(ticker)
            continue

    # 🔹 Debug logs
    print(f"✅ Scanned tickers ({len(tickers)}): {tickers}")
    print(f"❌ Failed tickers ({len(failed_tickers)}): {failed_tickers}")

    return tickers, failed_tickers

@router.post("/scan_news_bulk", response_model=Dict)
def scan_news_for_low_cap_bulk(
    params: ScanParams,
    db: Session = Depends(get_db),
    top_n: int = 3,
    model: str = "gpt-4o",
):
    tickers, failed_tickers = scan_and_analyze_low_cap_tickers(
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
        "failed_tickers": failed_tickers,
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

INFO_FILE = Path(__file__).parent.parent / "utils" / "premarket" / "info.json"

def read_info() -> dict:
    """Read info.json, returning a dict. Returns empty dict on failure."""
    if INFO_FILE.exists():
        try:
            with open(INFO_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Failed to read info.json: {e}")
            return {}
    return {}

@router.get("/get_watchlist")
def get_watchlist(db: Session = Depends(get_db)):
    tickers = read_watchlist()
    results = []

    analyze_intraday = check_market_hours(db)
    info_dict = read_info()  # load all info once

    for ticker in tickers:
        fetch_and_save_price_history(db, ticker)
        snapshot = db.query(VolumeSnapshot).filter_by(ticker=ticker).first()

        if not snapshot:
            snapshot = analyze_and_snapshot_ticker(
                db=db,
                ticker=ticker,
                surge_threshold=0.0,
                price_threshold=0,
            )

        if snapshot:
            recent_prices = get_recent_price_data(
                db, snapshot.ticker, analyze_intraday=analyze_intraday
            )

            # Get all info fields from info.json for this ticker, fallback to empty dict
            ticker_info = info_dict.get(ticker, {})

            results.append({
                "ticker": ticker,
                "name": snapshot.name,
                "current_price": snapshot.current_price,
                "recent_prices": recent_prices,
                **ticker_info,  # spreads all fields like industry, finance_strength, etc.
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

@router.post("/analyze_live/{ticker}", response_model=Dict)
def analyze_live_stock(
    ticker: str,
    top_n: int = 3,
    model: str = "gpt-3.5-turbo",
    raw_yahoo_json: Optional[dict] = Body(None),
    db: Session = Depends(get_db)
):
    result = analyze_live_ticker(
        db=db,
        ticker=ticker,
        top_n=top_n,
        model=model,
        raw_yahoo_json=raw_yahoo_json
    )
    return result

@router.post("/test_parse_intraday/{ticker}", response_model=Dict)
def test_parse_intraday(
    ticker: str,
    raw_yahoo_json: Optional[dict] = Body(None),
    db: Session = Depends(get_db)
):
    if raw_yahoo_json is None:
        return {"error": "raw_yahoo_json body is required"}

    parsed_data = parse_yahoo_intraday(raw_yahoo_json)
    return {
        "ticker": ticker,
        "parsed_intraday": parsed_data,
    }

@router.post("/spiked_scan")
def spiked_scan(
    params: ScanParams,
    db: Session = Depends(get_db),
    analyze_intraday = False
):
    """
    Scan pages for spiked stocks (spike_date exists and first_day_close_near_high=True)
    and analyze them with GPT.
    """
    # is_market_hours = check_market_hours(db)
    analyze_intraday = check_market_hours(db)

    # Step 1: Scan pages to get tickers
    tickers = scan_and_save_pre_market_volume_surges(
        db=db,
        surge_threshold=0,
        price_threshold=params.price_threshold,
        from_page=params.from_page,
        to_page=params.to_page,
    )

    # Step 2: Filter only spiked stocks
    spiked_tickers = []
    for ticker in tickers:
        spike_info = normalize_spike_for_json(get_spike_analysis(db, ticker, analyze_intraday=analyze_intraday))
        if spike_info.get("spike_date") or (spike_info.get("first_day_close_near_high") and spike_info.get("first_spike_pct") >= 25):
            spiked_tickers.append(ticker)

    print(f"Found {len(spiked_tickers)} spiked tickers: {spiked_tickers}")

    # Step 3: GPT-3.5 analysis
    for ticker in spiked_tickers:
        try:
            analyze_ticker_by_steps(
                db=db,
                ticker=ticker,
                top_n=3,
                model="gpt-3.5-turbo",
                analyze_intraday=analyze_intraday,
                detected_type="spiked"
            )
        except Exception as e:
            print(f"⚠️ GPT-3.5 analysis failed for {ticker}: {e}")

    # Step 4: Re-analyze promising stocks with GPT-4o
    for ticker in spiked_tickers:
        volume_info = get_volume_info(db, ticker=ticker)
        if volume_info and volume_info.news_score and volume_info.news_score >= 50:
            try:
                print(f"🔁 Re-analyzing {ticker} with GPT-4o...")
                analyze_ticker_by_steps(
                    db=db,
                    ticker=ticker,
                    top_n=3,
                    model="gpt-4o",
                    analyze_intraday=analyze_intraday,
                    detected_type="spiked"
                )
            except Exception as e:
                print(f"⚠️ GPT-4o analysis failed for {ticker}: {e}")

    return {"spiked_tickers": spiked_tickers, "count": len(spiked_tickers)}

@router.post("/scan_first_spike_over_100")
def scan_first_spike_over_100(
    params: ScanParams = Body(...),
    db: Session = Depends(get_db)
):
    # Step 1: Scan pages to get tickers
    tickers = scan_and_save_pre_market_volume_surges(
        db=db,
        surge_threshold=0,
        price_threshold=params.price_threshold,
        from_page=params.from_page,
        to_page=params.to_page,
    )

    # Step 2: Filter tickers with first_spike_pct >= 100% in last 30 days
    spiked_tickers = []
    for ticker in tickers:
        if compute_spike_analysis_100(db, ticker):
            spiked_tickers.append(ticker)

    print(f"====spiked_tickers={spiked_tickers}")
    print(f"Found {len(spiked_tickers)} tickers with first_spike_pct >= 100%: {spiked_tickers}")
    return spiked_tickers

# @router.post("/scan_market_news")
# def scan_market_news(params: ScanParams = Body(...), db: Session = Depends(get_db)):
#     interval_minutes = getattr(params, "interval_minutes", 5)
#     limit = getattr(params, "limit", 30)

#     # Run scanner once
#     alerts = run_market_news_scanner(db=db, interval_minutes=interval_minutes, limit=limit)

#     return {
#         "status": "success",
#         "alerts": alerts
#     }
@router.post("/scan_market_news_once")
async def scan_market_news(db: Session = Depends(get_db)):
    alerts = await scan_market_news_once(db)
    return {
        "status": "success",
        "alerts": alerts
    }

scanner_task: Optional[asyncio.Task] = None

@router.post("/start_market_news_scanner")
async def start_market_news_scanner(db: Session = Depends(get_db), interval_minutes: int = 1, limit: int = 30):
    global scanner_task

    if scanner_task and not scanner_task.done():
        return {"status": "already_running"}

    # Create background task
    scanner_task = asyncio.create_task(background_market_news_scanner(db, interval_minutes=interval_minutes, limit=limit))
    return {"status": "scanner_started"}

@router.post("/stop_market_news_scanner")
async def stop_market_news_scanner():
    global scanner_task
    if scanner_task:
        scanner_task.cancel()
        scanner_task = None
        return {"status": "scanner_stopped"}
    return {"status": "no_scanner_running"}

@router.post("/flat_scan")
def flat_scan(
    params: ScanParams,
    db: Session = Depends(get_db),
    analyze_intraday: bool = False
):
    """
    Scan pages for flat-pattern stocks (tight range + small abnormal surge or rising volume)
    and analyze them with GPT, then add to watchlist.
    """
    analyze_intraday = check_market_hours(db)

    # print(f"====price_threshold={params.price_threshold}, from_page={params.from_page}, to_page={params.to_page}")

    # Step 1: Scan pages to get tickers
    tickers = scan_and_save_pre_market_volume_surges(
        db=db,
        surge_threshold=0,
        price_threshold=params.price_threshold,
        from_page=params.from_page,
        to_page=params.to_page,
    )

    # Step 2: Filter only flat-pattern stocks
    flat_tickers = []
    for ticker in tickers:
        flat_info = analyze_flat_pattern(db, ticker, analyze_intraday=analyze_intraday)
        if flat_info and flat_info.pattern_detected:  # flat pattern detected
            flat_tickers.append(ticker)

    print(f"✅ Found {len(flat_tickers)} flat pattern tickers: {flat_tickers}")

    # Step 3: Add detected tickers to WatchList
    if flat_tickers:
        tickers_str = ",".join(flat_tickers)
        added = append_batch_to_watchlist(tickers_str)
        for ticker in added:
            if not db.query(WatchList).filter_by(ticker=ticker).first():
                db.add(WatchList(ticker=ticker))
        db.commit()
        print(f"📌 Added {len(added)} tickers to watchlist: {added}")
    else:
        added = []

    # # Step 3: GPT-3.5 analysis
    # for ticker in flat_tickers:
    #     try:
    #         analyze_ticker_by_steps(
    #             db=db,
    #             ticker=ticker,
    #             top_n=3,
    #             model="gpt-3.5-turbo",
    #             analyze_intraday=analyze_intraday,
    #             detected_type="flat"
    #         )
    #     except Exception as e:
    #         print(f"⚠️ GPT-3.5 analysis failed for {ticker}: {e}")

    # # Step 4: Re-analyze promising stocks with GPT-4o
    # for ticker in flat_tickers:
    #     volume_info = get_volume_info(db, ticker=ticker)
    #     if volume_info and volume_info.news_score and volume_info.news_score >= 50:
    #         try:
    #             print(f"🔁 Re-analyzing {ticker} with GPT-4o...")
    #             analyze_ticker_by_steps(
    #                 db=db,
    #                 ticker=ticker,
    #                 top_n=3,
    #                 model="gpt-4o",
    #                 analyze_intraday=analyze_intraday,
    #                 detected_type="flat"
    #             )
    #         except Exception as e:
    #             print(f"⚠️ GPT-4o analysis failed for {ticker}: {e}")

    return {
        "found": flat_tickers,
        "added_to_watchlist": added
    }

@router.post("/test_flat_scan/{ticker}")
def test_flat_scan(
    ticker: str,
    db: Session = Depends(get_db),
    analyze_intraday: bool = False,
    lookback_days: int = 10,
    surge_window_days: int = 2,
):
    """
    Test flat-pattern detection for one ticker only.
    """
    # analyze_intraday = check_market_hours(db)

    flat_info = analyze_flat_pattern(
        db=db,
        ticker=ticker,
        lookback_days=lookback_days,
        surge_window_days=surge_window_days,
        analyze_intraday=analyze_intraday,
    )

    if flat_info and flat_info.pattern_detected:
        print(f"✅ Flat pattern detected for {ticker}")
        return {"ticker": ticker, "pattern": True, "info": flat_info}
    else:
        print(f"❌ No flat pattern for {ticker}")
        return {"ticker": ticker, "pattern": False}


