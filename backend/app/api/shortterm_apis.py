import json
from fastapi import APIRouter, Depends, HTTPException
from app.models import VolumeSnapshot, StarredStock, ShortTermAnalysisSignal
from sqlalchemy.orm import Session
from typing import List, Dict
from pydantic import BaseModel

from app.db.db import SessionLocal
from app.utils.shortterm.volume_surge_scraper import scan_and_save_volume_surges, get_latest_volume_surges, fetch_intraday_prices, get_intraday_volume_info_for_ticker
from app.utils.shortterm.volume_history import fetch_daily_volume_history, save_daily_volumes
from app.utils.shortterm.moneyflow_history import fetch_daily_money_flow_history, save_daily_money_flows
from app.utils.shortterm.volume_5d_average_updater import update_avg_volume_for_ticker
from app.utils.shortterm.moneyflow_5d_average_updater import update_avg_money_flow_for_ticker
from app.utils.shortterm.yahoo_general_news import fetch_news_signals
from app.utils.shortterm.kabutan_news_ticker import scrape_kabutan_news, analyze_stock_surge_with_news, get_volume_info
from app.utils.shortterm.breakout_detector import detect_breakout
from app.utils.shortterm.candle_pattern_detector import analyze_candle_pattern_for_ticker
from app.utils.shortterm.price_updater import fetch_and_save_price_history
from app.utils.shortterm.technical_indicators import get_technical_indicators
from app.utils.shortterm.w_shape_detector import detect_w_shape_for_ticker
from app.utils.shortterm.flag_pennant_detector import detect_flags_pennants_for_ticker
from app.utils.shortterm.triangle_detector import detect_triangle_for_ticker
from app.utils.shortterm.save_shortterm_analysis_signal import save_shortterm_analysis_signal

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

# For testing
@router.post("/{ticker}/intraday")
def get_intraday_prices(ticker: str):
    last, high, low = fetch_intraday_prices(ticker)
    return {"message": f"Intraday price for {ticker}: {last, high, low}"}

# For Use
class ScanParams(BaseModel):
    surge_threshold: float = 2.0
    price_threshold: float = 300.0
    from_page: int = 1
    to_page: int = 1

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
        from_page=params.from_page,
        to_page=params.to_page,
    )

    # Step 2: For each new ticker, run GPT analysis
    for ticker in tickers:
        news = scrape_kabutan_news(ticker, limit=30)
        if not news:
            continue

        volume_info = get_volume_info(db, ticker=ticker)
        try:
            analyze_stock_surge_with_news(
                db=db,
                ticker=ticker,
                news_items=news,
                volume_info=volume_info,
                top_n=5,
            )
        except Exception as e:
            print(f"⚠️ GPT analysis failed for {ticker}: {e}")

    return {"message": f"Volume scan complete. {len(tickers)} tickers analyzed and stored."}

# For Use
def get_latest_analysis_signal_data(db: Session, ticker: str) -> dict:
    signal = (
        db.query(ShortTermAnalysisSignal)
        .filter(ShortTermAnalysisSignal.ticker == ticker)
        .order_by(ShortTermAnalysisSignal.updated_at.desc())
        .first()
    )

    if not signal:
        return {}

    return {
        "candle_pattern": signal.candle_pattern,
        "breakout_detected": signal.breakout_detected,
        "resistance_level": signal.resistance_level,
        "close_today": signal.close_today,
        "rsi": signal.rsi,
        "macd_line": signal.macd_line,
        "macd_signal": signal.macd_signal,
        "macd_hist": signal.macd_hist,
        "bb_upper": signal.bb_upper,
        "bb_middle": signal.bb_middle,
        "bb_lower": signal.bb_lower,
        "bb_current_price": signal.bb_current_price,
        "sma_50": signal.sma_50,
        "sma_200": signal.sma_200,
        "ema_20": signal.ema_20,
        "sma_crossover": signal.sma_crossover,
        "w_shape": signal.w_shape,
        "flags_pennants": signal.flags_pennants,
        "triangle": signal.triangle,
    }

# For Use
@router.get("/{ticker}/volume_surge/analysis", response_model=Dict)
def get_saved_volume_analysis(ticker: str, db: Session = Depends(get_db)):
    vs = (
        db.query(VolumeSnapshot)
        .filter(VolumeSnapshot.ticker == ticker)
        .order_by(VolumeSnapshot.detected_at.desc())
        .first()
    )
    if not vs:
        raise HTTPException(status_code=404, detail="No saved analysis found")

    top_news = []
    if vs.top_news:
        try:
            top_news = json.loads(vs.top_news)
        except Exception:
            top_news = []

    analysis_signal_data = get_latest_analysis_signal_data(db, ticker)

    return {
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
        },
        "analysis_signal": analysis_signal_data,
    }


# For Use
@router.get("/volume_surges")
def get_recent_volume_surges(
    hours: int = 24,
    surge_threshold: float = 2.0,
    price_threshold: float = 150.0,
    promising_score_threshold: float = 0.0,
    db: Session = Depends(get_db),
):
    """Return stocks with volume surges in the last `hours` filtered by thresholds."""
    return get_latest_volume_surges(
        db,
        hours=hours,
        surge_threshold=surge_threshold,
        price_threshold=price_threshold,
        promising_score_threshold=promising_score_threshold,
    )

# For Use (haven't be used)
@router.get("/news_signals", response_model=List[Dict])
def get_news_signals(db: Session = Depends(get_db)):
    return fetch_news_signals()

# For Use
@router.post("/{ticker}/star")
def star_stock(ticker: str, db: Session = Depends(get_db)):
    existing = db.query(StarredStock).filter_by(ticker=ticker).first()
    if not existing:
        new_star = StarredStock(ticker=ticker)
        db.add(new_star)
        db.commit()
    return {"status": "starred"}

# For Use
@router.delete("/{ticker}/star")
def unstar_stock(ticker: str, db: Session = Depends(get_db)):
    existing = db.query(StarredStock).filter_by(ticker=ticker).first()
    if existing:
        db.delete(existing)
        db.commit()
    return {"status": "unstarred"}

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

    volume_info = get_volume_info(db, ticker=ticker)
    result = analyze_stock_surge_with_news(
        db=db,
        ticker=ticker,
        news_items=news,
        top_n=top_n,
        volume_info=volume_info,
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

# For testing
@router.post("/fetch_and_save/{ticker}")
def fetch_and_save_daily_prices(ticker: str, days: int = 150, db: Session = Depends(get_db)):
    """
    Fetch and save daily price data for a given ticker from Yahoo Finance.
    Saves up to `days` records (default = 30).
    """
    try:
        fetch_and_save_price_history(db, ticker, days)
        return {
            "message": f"Price data for {ticker} fetched and saved successfully (latest {days} days)"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch/save data for {ticker}: {e}")

# For testing
@router.get("/{ticker}/breakout")
def check_breakout(ticker: str, db: Session = Depends(get_db)):
    """
    Check breakout status for the given ticker using the latest N days of daily prices stored in the DB.
    Assumes the data has already been fetched and stored.
    """
    result = detect_breakout(db, ticker)

    if not result.get("breakout_detected") and "reason" in result:
        raise HTTPException(status_code=400, detail=result["reason"])

    return {
        "message": f"Breakout check completed for {ticker}",
        "breakout_info": result
    }

# For testing
@router.get("/{ticker}/candle_pattern")
def update_and_check_candle_pattern(ticker: str, db: Session = Depends(get_db)):
    """
    Analyze recent candlestick pattern for the given ticker using stored daily prices in DB.
    Returns the detected pattern, if any.
    """
    result = analyze_candle_pattern_for_ticker(db, ticker)
    
    if result["candle_pattern"] is None:
        return {
            "message": f"No significant candlestick pattern detected for {ticker}",
            "candle_pattern_info": result
        }
    
    return {
        "message": f"Candle pattern check completed for {ticker}",
        "candle_pattern_info": result
    }
    
# For testing
@router.get("/{ticker}/technical_indicators")
def read_technical_indicators(ticker: str, db: Session = Depends(get_db)):
    indicators = get_technical_indicators(db, ticker)
    if indicators is None:
        raise HTTPException(status_code=404, detail=f"No price data for {ticker}")
    return {
        "ticker": ticker,
        "technical_indicators": indicators,
    }

# For testing
@router.get("/{ticker}/w_shape")
def w_shape_pattern(ticker: str, db: Session = Depends(get_db)):
    """
    Detect W-shape (Double Bottom) pattern for a given ticker.
    """
    result = detect_w_shape_for_ticker(db, ticker)
    if "reason" in result:
        raise HTTPException(status_code=404, detail=result["reason"])
    return result

# For testing
@router.get("/{ticker}/flags_pennants")
def flags_pennants_pattern(ticker: str, db: Session = Depends(get_db)):
    """
    Detect Flags & Pennants pattern for the given ticker.
    """
    result = detect_flags_pennants_for_ticker(db, ticker)
    if "reason" in result:
        raise HTTPException(status_code=404, detail=result["reason"])
    return result

# For testing
@router.get("/{ticker}/triangle")
def triangle_pattern(ticker: str, db: Session = Depends(get_db)):
    """
    Detect triangle pattern (ascending, descending, symmetrical) for a given ticker.
    """
    result = detect_triangle_for_ticker(db, ticker)
    if "reason" in result:
        raise HTTPException(status_code=404, detail=result["reason"])
    return result

# For testing
@router.post("/{ticker}/analyze_shortterm")
def analyze_shortterm(ticker: str, db: Session = Depends(get_db)):
    return save_shortterm_analysis_signal(db, ticker)

# For use
@router.get("/analyze_ticker/{ticker}")
def analyze_ticker_with_gpt(ticker: str, db: Session = Depends(get_db)):
    # 1. Get volume info from Yahoo Finance
    volume_info = get_intraday_volume_info_for_ticker(db, ticker)
    if not volume_info:
        raise HTTPException(status_code=404, detail="Could not fetch intraday info")

    # 2. Get Kabutan news
    news = scrape_kabutan_news(ticker, limit=30)
    if not news:
        raise HTTPException(status_code=404, detail="No Kabutan news found")

    # 3. Ensure technical signal is up to date
    save_shortterm_analysis_signal(db, ticker)

    # 4. Fetch technical analysis signal
    analysis_signal_data = get_latest_analysis_signal_data(db, ticker)

    # 5. Analyze with GPT using live volume_info (not from DB)
    gpt_result = analyze_stock_surge_with_news(
        db=db,
        ticker=ticker,
        news_items=news,
        top_n=5,
        volume_info=volume_info,  # ⚠️ make sure your analyze_stock_surge_with_news supports this
    )

    # 6. Compose response
    return {
        "ticker": ticker,
        "volume_info": {
            "ticker": volume_info.ticker,
            "name": volume_info.name,
            "current_price": volume_info.current_price,
            "price_change": volume_info.price_change,
            "volume_rate": volume_info.volume_rate,
            "money_flow_rate": volume_info.money_flow_rate,
            "current_volume": volume_info.current_volume,
            "avg_volume_5d": volume_info.avg_volume_5d,
            "detected_at": volume_info.detected_at.isoformat(),
            "reasoning": volume_info.reasoning,
            "recommendation": volume_info.recommendation,
            "promising_score": volume_info.promising_score,
            "top_news": volume_info.top_news,
        },
        "top_news": gpt_result.get("top_news", []),
        "analysis_signal": analysis_signal_data,
        "gpt_summary": gpt_result.get("gpt_summary", ""),
    }
