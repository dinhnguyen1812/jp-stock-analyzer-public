import datetime
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

def ask_gpt_holding_advice(db: Session, entry, model: str = "gpt-4o"):
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    ticker = entry.ticker

    # Historical data at entry time
    entry_snapshot = (
        db.query(VolumeSnapshot)
        .filter(
            VolumeSnapshot.ticker == ticker,
            VolumeSnapshot.detected_at == entry.detected_at
        )
        .first()
    )

    entry_signal = (
        db.query(ShortTermAnalysisSignal)
        .filter(
            ShortTermAnalysisSignal.ticker == ticker,
            ShortTermAnalysisSignal.updated_at == entry.updated_at
        )
        .first()
    )

    # Current data
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

    # Construct summaries
    def format_volume_info(volume_info):
        return (
            f"Ticker: {volume_info.ticker}\n"
            f"Name: {volume_info.name}\n"
            f"Price: ¥{volume_info.current_price}\n"
            f"Price Change: {volume_info.price_change}%\n"
            f"Volume Surge: {volume_info.volume_rate:.2f}x\n"
            f"Estimated Money Flow Rate: {volume_info.money_flow_rate:.2f}x\n"
            f"Volume: {volume_info.current_volume:,} 株\n"
            f"5-Day Avg Volume: {volume_info.avg_volume_5d:,} 株\n"
            f"Detected At: {volume_info.detected_at.strftime('%Y-%m-%d %H:%M')}"
        )

    def format_signal(sig):
        return (
            f"RSI: {sig.rsi or 'N/A'}\n"
            f"MACD: line={sig.macd_line or 'N/A'}, signal={sig.macd_signal or 'N/A'}, hist={sig.macd_hist or 'N/A'}\n"
            f"Bollinger Bands: upper={sig.bb_upper or 'N/A'}, middle={sig.bb_middle or 'N/A'}, "
            f"lower={sig.bb_lower or 'N/A'}, price={sig.bb_current_price or 'N/A'}\n"
            f"MA: SMA50={sig.sma_50 or 'N/A'}, SMA200={sig.sma_200 or 'N/A'}, EMA20={sig.ema_20 or 'N/A'}, "
            f"Crossover={sig.sma_crossover or 'N/A'}\n"
            f"Candle Pattern: {sig.candle_pattern or 'None'}\n"
            f"Breakout: {sig.breakout_detected}, Resistance: {sig.resistance_level or 'N/A'}, "
            f"Close: {sig.close_today or 'N/A'}\n"
            f"W-Shape: {sig.w_shape}, Flags/Pennants: {sig.flags_pennants}, Triangle: {sig.triangle}"
        )

    # Profit calc
    profit = round((current_volume_info.current_price - entry.entry_price) * entry.amount)
    profit_pct = round(((current_volume_info.current_price - entry.entry_price) / entry.entry_price) * 100, 2)

    # JST time
    now_str = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime("%Y/%m/%d %H:%M:%S")

    # Final GPT Prompt
    prompt = f"""
You are a short-term trading advisor. A user entered a trade for the Japanese stock {ticker} and is now seeking advice.

## Trade Info
- Ticker: {ticker}
- Entry Price: ¥{entry.entry_price}
- Entry Amount: {entry.amount} shares
- Entry Time Volume Snapshot:
{format_volume_info(entry_snapshot) if entry_snapshot else '(No entry volume snapshot)'}
- Entry Time Technical Signals:
{format_signal(entry_signal) if entry_signal else '(No entry signal)'}

## Current Info
- Current Volume Snapshot:
{format_volume_info(current_volume_info)}
- Current Technical Signals:
{format_signal(signal)}
- Current Time: {now_str}
- Profit/Loss: ¥{profit} ({profit_pct}%)

## User Objective
The user is pursuing short-term gains through active trading, targeting an average daily return of 3–5%. 
Some loss days are acceptable if the overall strategy trends toward steady short-term growth.

### Output:
- Summary of key changes from entry to now
- Advice: **SELL** or **HOLD**
- Justify your advice (2–3 bullet points)
- Confidence Score (0–100) based on whether target profit is likely to be achieved soon
"""

    response = openai.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": "You are a professional Japanese stock trading advisor."},
            {"role": "user", "content": prompt.strip()}
        ]
    )

    content = response.choices[0].message.content.strip()

    return {
        "gpt_advice": content,
        "summary": signal.gpt_summary if signal else "",
        "confidence": signal.promising_score if signal else None,
        "recommendation": "SELL" if "SELL" in content.upper() else "HOLD"
    }

