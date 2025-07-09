import datetime
import re
import openai
import os
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models import EntriedStock, VolumeSnapshot, ShortTermAnalysisSignal
from .volume_surge_scraper import fetch_intraday_prices, get_intraday_volume_info_for_ticker
from .save_shortterm_analysis_signal import save_shortterm_analysis_signal

openai.api_key = os.getenv("OPENAI_API_KEY")

def get_current_holdings(db: Session):
    entries = db.query(EntriedStock).filter(EntriedStock.is_sold == False).all()
    result = []

    total_invested = 0
    total_current_value = 0

    for entry in entries:
        ticker = entry.ticker

        # Always fetch latest price from Yahoo
        current_price, _, _ = fetch_intraday_prices(ticker)
        if current_price is None:
            continue  # skip if price can't be fetched

        invested = entry.entry_price * entry.amount
        current_value = current_price * entry.amount

        profit_amount = round(current_value - invested)
        profit_percent = round(((current_value - invested) / invested) * 100, 2)

        total_invested += invested
        total_current_value += current_value

        result.append({
            "id": entry.id,
            "ticker": entry.ticker,
            "entry_price": entry.entry_price,
            "current_price": current_price,
            "amount": entry.amount,
            "entry_time": entry.created_at.isoformat(),
            "profit_amount": profit_amount,
            "profit_percent": profit_percent,
        })

    total_profit = round(total_current_value - total_invested)
    total_profit_percent = round(((total_current_value - total_invested) / total_invested) * 100, 2) if total_invested > 0 else 0.0

    return {
        "entries": result,
        "summary": {
            "total_invested": round(total_invested),
            "total_current_value": round(total_current_value),
            "total_profit": total_profit,
            "total_profit_percent": total_profit_percent
        }
    }

def create_entry_and_analyze(db: Session, ticker: str, amount: int, entry_price: float):
    ticker = ticker.upper()

    # 1. Get VolumeSnapshot (live intraday info)
    volume_info = get_intraday_volume_info_for_ticker(db, ticker)
    if not volume_info:
        raise HTTPException(status_code=404, detail="Volume info not available")

    # 2. Update technical signal if needed
    save_shortterm_analysis_signal(db, ticker)

    # 3. Get latest signal (for updated_at)
    analysis_signal = (
        db.query(ShortTermAnalysisSignal)
        .filter(ShortTermAnalysisSignal.ticker == ticker)
        .order_by(ShortTermAnalysisSignal.updated_at.desc())
        .first()
    )
    if not analysis_signal:
        raise HTTPException(status_code=404, detail="No signal found")

    # 4. Insert entry into DB
    entry = EntriedStock(
        ticker=ticker,
        detected_at=volume_info.detected_at,
        updated_at=analysis_signal.updated_at,
        entry_price=entry_price,  # ✅ Use user-provided entry price
        amount=amount,
    )
    db.add(entry)
    db.commit()

    return {
        "message": "Entry added and analyzed.",
        "entry_id": entry.id,
    }

def extract_recommendation_and_score(text: str):
    cleaned = re.sub(r"[*#•\-–—●★▶◆]", "", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    rec_match = re.search(r"advice\s*[:\-]?\s*(buy|sell|hold)", cleaned, re.I)
    recommendation = rec_match.group(1).capitalize() if rec_match else "Unknown"
    score_match = re.search(r"confidence score\s*[:\-]?\s*(\d{1,3})", cleaned)
    promising_score = int(score_match.group(1)) if score_match else -1
    promising_score = max(0, min(promising_score, 100))
    return recommendation, promising_score

def ask_gpt_holding_advice(db: Session, entry, model: str = "gpt-4o"):
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    ticker = entry.ticker

    # Historical info
    entry_snapshot = (
        db.query(VolumeSnapshot)
        .filter(VolumeSnapshot.ticker == ticker, VolumeSnapshot.detected_at == entry.detected_at)
        .first()
    )
    entry_signal = (
        db.query(ShortTermAnalysisSignal)
        .filter(ShortTermAnalysisSignal.ticker == ticker, ShortTermAnalysisSignal.updated_at == entry.updated_at)
        .first()
    )

    # Current info
    current_volume_info = get_intraday_volume_info_for_ticker(db, ticker)
    if not current_volume_info:
        raise HTTPException(status_code=404, detail="Current volume info not available")

    signal = db.query(ShortTermAnalysisSignal).filter_by(ticker=ticker).first()
    should_update = (
        not signal or not signal.updated_at or
        (datetime.datetime.utcnow() - signal.updated_at) > datetime.timedelta(hours=1)
    )
    if should_update:
        save_shortterm_analysis_signal(db, ticker)
        signal = db.query(ShortTermAnalysisSignal).filter_by(ticker=ticker).first()

    if not signal:
        raise HTTPException(status_code=404, detail="Missing technical signal")

    # Formatters
    def format_volume_info(v):
        return (
            f"Ticker: {v.ticker}\n"
            f"Name: {v.name}\n"
            f"Price: ¥{v.current_price}\n"
            f"Price Change: {v.price_change}%\n"
            f"Volume Surge: {v.volume_rate:.2f}x\n"
            f"Estimated Money Flow Rate: {v.money_flow_rate:.2f}x\n"
            f"Volume: {v.current_volume:,} 株\n"
            f"5-Day Avg Volume: {v.avg_volume_5d:,} 株\n"
            f"Detected At: {v.detected_at.strftime('%Y-%m-%d %H:%M')}"
        )

    def format_signal(s):
        return (
            f"RSI: {s.rsi or 'N/A'}\n"
            f"MACD: line={s.macd_line or 'N/A'}, signal={s.macd_signal or 'N/A'}, hist={s.macd_hist or 'N/A'}\n"
            f"Bollinger Bands: upper={s.bb_upper or 'N/A'}, middle={s.bb_middle or 'N/A'}, "
            f"lower={s.bb_lower or 'N/A'}, price={s.bb_current_price or 'N/A'}\n"
            f"MA: SMA50={s.sma_50 or 'N/A'}, SMA200={s.sma_200 or 'N/A'}, EMA20={s.ema_20 or 'N/A'}, "
            f"Crossover={s.sma_crossover or 'N/A'}\n"
            f"Candle Pattern: {s.candle_pattern or 'None'}\n"
            f"Breakout: {s.breakout_detected}, Resistance: {s.resistance_level or 'N/A'}, "
            f"Close: {s.close_today or 'N/A'}\n"
            f"W-Shape: {s.w_shape}, Flags/Pennants: {s.flags_pennants}, Triangle: {s.triangle}"
        )

    # P/L
    profit = round((current_volume_info.current_price - entry.entry_price) * entry.amount)
    profit_pct = round(((current_volume_info.current_price - entry.entry_price) / entry.entry_price) * 100, 2)

    now_str = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime("%Y/%m/%d %H:%M:%S")

    # GPT Prompt
    prompt = f"""
You are a Japanese short-term trading advisor. A user entered a trade for stock {ticker} and wants quick advice.

## Trade
- Ticker: {ticker}, Entry: ¥{entry.entry_price}, Amount: {entry.amount}
- P/L: ¥{profit} ({profit_pct}%)

## Entry Info
{format_volume_info(entry_snapshot) if entry_snapshot else '(No entry volume snapshot)'}
{format_signal(entry_signal) if entry_signal else '(No entry signal)'}

## Current Info
{format_volume_info(current_volume_info)}
{format_signal(signal)}

## Objective
The user targets daily profit of 3–5%. Usually sells same day to lock profit unless very strong upside.

### Output:
- Key changes since entry (2–3 lines)
- Advice: **SELL** or **HOLD**
- 2 short bullet justifications
- Confidence Score (0–100)
"""

    try:
        response = openai.chat.completions.create(
            model=model,
            temperature=0.4,
            messages=[
                {"role": "system", "content": "You are a professional Japanese stock trading advisor."},
                {"role": "user", "content": prompt.strip()}
            ]
        )
        content = response.choices[0].message.content.strip()
        recommendation, confidence = extract_recommendation_and_score(content)

        return {
            "gpt_advice": content,
            "recommendation": recommendation,
            "confidence": confidence
        }

    except Exception as e:
        print(f"❌ GPT advice generation failed: {e}")
        return {
            "gpt_advice": "GPT advice unavailable due to error.",
            "recommendation": "Unknown",
            "confidence": -1
        }