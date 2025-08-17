from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models import ShortTermAnalysisSignal

# Individual signal utilities
from app.utils.shortterm.candle_pattern_detector import analyze_candle_pattern_for_ticker
from app.utils.shortterm.technical_indicators import get_technical_indicators
from app.utils.shortterm.breakout_detector import detect_breakout
from app.utils.shortterm.w_shape_detector import detect_w_shape_for_ticker
from app.utils.shortterm.flag_pennant_detector import detect_flags_pennants_for_ticker
from app.utils.shortterm.triangle_detector import detect_triangle_for_ticker
from app.utils.shortterm.price_updater import fetch_and_save_price_history

def save_shortterm_analysis_signal(db: Session, ticker: str) -> dict:
    """
    Run full signal analysis for a ticker and save to shortterm_analysis_signals table.
    If record exists for (ticker), it will be updated.
    """
    existing = db.query(ShortTermAnalysisSignal).filter_by(ticker=ticker).first()

    if existing:
        signal = existing
    else:
        signal = ShortTermAnalysisSignal(ticker=ticker)
        fetch_and_save_price_history(db, ticker, max_days=50)

    signal.date = date.today()
    signal.updated_at = datetime.utcnow()  # ✅ ensure freshness check works

    # 1. Candlestick pattern
    candle_result = analyze_candle_pattern_for_ticker(db, ticker)
    signal.candle_pattern = candle_result.get("candle_pattern")

    # 2. Breakout
    breakout = detect_breakout(db, ticker)
    signal.breakout_detected = breakout.get("breakout_detected", False)
    signal.resistance_level = breakout.get("resistance_level")
    signal.close_today = breakout.get("close_today")

    # 3. Technical Indicators
    tech = get_technical_indicators(db, ticker)
    if tech:
        signal.rsi = tech.get("rsi")

        macd = tech.get("macd", {})
        signal.macd_line = macd.get("macd_line")
        signal.macd_signal = macd.get("signal_line")
        signal.macd_hist = macd.get("histogram")

        bb = tech.get("bollinger_bands", {})
        signal.bb_upper = bb.get("upper")
        signal.bb_middle = bb.get("middle")
        signal.bb_lower = bb.get("lower")
        signal.bb_current_price = bb.get("current_price")

        ma = tech.get("moving_averages", {})
        signal.sma_50 = ma.get("sma_50")
        signal.sma_200 = ma.get("sma_200")
        signal.ema_20 = ma.get("ema_20")
        signal.sma_crossover = tech.get("sma_crossover")

    # 4. Pattern detection
    signal.w_shape = detect_w_shape_for_ticker(db, ticker).get("pattern_detected", False)
    signal.flags_pennants = detect_flags_pennants_for_ticker(db, ticker).get("pattern_detected", False)
    signal.triangle = detect_triangle_for_ticker(db, ticker).get("pattern_detected", False)

    try:
        db.add(signal)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise

    return {
        "message": f"Short-term analysis signal saved for {ticker}",
        "date": str(date.today())
    }
