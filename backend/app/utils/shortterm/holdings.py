import datetime
import re
import httpx
from bs4 import BeautifulSoup
from zoneinfo import ZoneInfo
import openai
import os
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models import AverageMoneyFlow, AverageVolume, EntriedStock, VolumeSnapshot, ShortTermAnalysisSignal
from .volume_surge_scraper import get_intraday_volume_info_for_ticker

openai.api_key = os.getenv("OPENAI_API_KEY")

JP_TZ = ZoneInfo("Asia/Tokyo")
JP_OPEN = datetime.time(9, 0)

def get_intraday_metrics(ticker: str, db: Session):
    url = f"https://finance.yahoo.co.jp/quote/{ticker}.T"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "ja,en;q=0.9"
    }

    try:
        resp = httpx.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # === Get current price ===
        current_price = None
        price_tag = soup.select_one("div.PriceBoardMain__headerPrice__gbs7 span.StyledNumber__value__3rXW")
        if not price_tag:
            price_tag = soup.select_one("span.PriceBoard__price__1V0k span.StyledNumber__value__3rXW")
        if price_tag:
            try:
                current_price = float(price_tag.text.replace(",", "").strip())
            except ValueError:
                print(f"⚠️ Could not parse current price for {ticker}")

        # === Get high and low ===
        high = None
        low = None
        dl_tags = soup.select("dl.DataListItem__38iJ") or soup.select("dl.DataListItem__name__3RQJ")
        for dl in dl_tags:
            label = dl.find("dt")
            value_span = dl.find("span", class_="DataListItem__value__11kV")
            if label and value_span:
                label_text = label.get_text()
                try:
                    value = float(value_span.text.replace(",", "").strip())
                except ValueError:
                    continue
                if "高値" in label_text:
                    high = value
                elif "安値" in label_text:
                    low = value

        # === Get current volume ===
        current_volume = None
        for label in soup.select("span.DataListItem__name__3RQJ"):
            if "出来高" in label.text:
                value_span = label.find_next("span", class_="StyledNumber__value__3rXW")
                if value_span:
                    raw = value_span.text.strip().replace(",", "").replace("株", "")
                    try:
                        current_volume = int(raw)
                    except ValueError:
                        print(f"⚠️ Invalid volume format for {ticker}: {raw}")
                break

        # === Compute typical price ===
        if high is not None and low is not None and current_price is not None:
            typical_price = (high + low + current_price) / 3
        else:
            typical_price = current_price

        # === Compute volume_rate ===
        volume_rate = None
        if current_volume is not None:
            avg_vol = db.query(AverageVolume).filter_by(ticker=ticker).first()
            if avg_vol and avg_vol.avg_5d_volume > 0:
                now = datetime.datetime.now(JP_TZ)
                market_open = now.replace(hour=JP_OPEN.hour, minute=JP_OPEN.minute, second=0, microsecond=0)
                market_close = now.replace(hour=15, minute=0, second=0, microsecond=0)

                if now <= market_open or now >= market_close:
                    expected_volume = avg_vol.avg_5d_volume
                else:
                    hours_passed = max((now - market_open).total_seconds() / 3600, 0.5)
                    expected_volume = avg_vol.avg_5d_volume * (hours_passed / 6)

                if expected_volume > 0:
                    volume_rate = current_volume / expected_volume

        # === Compute money_flow_rate ===
        money_flow_rate = None
        if current_volume is not None and typical_price is not None:
            raw_flow = typical_price * current_volume
            avg_flow = db.query(AverageMoneyFlow).filter_by(ticker=ticker).first()
            if avg_flow and avg_flow.avg_5d_money_flow > 0:
                money_flow_rate = raw_flow / avg_flow.avg_5d_money_flow

        return {
            "current_price": current_price,
            "volume_rate": round(volume_rate, 2) if volume_rate is not None else None,
            "money_flow_rate": round(money_flow_rate, 2) if money_flow_rate is not None else None
        }

    except Exception as e:
        print(f"❌ Failed to get intraday metrics for {ticker}: {e}")
        return None

def get_current_holdings(db: Session):
    entries = db.query(EntriedStock).filter(EntriedStock.is_sold == False).all()
    result = []

    total_invested = 0
    total_current_value = 0

    for entry in entries:
        ticker = entry.ticker
        metrics = get_intraday_metrics(ticker, db) or {}
        current_price = metrics.get("current_price")
        if current_price is None:
            continue

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
            "volume_rate": metrics.get("volume_rate"),
            "money_flow_rate": metrics.get("money_flow_rate"),
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
        # print("Volume info not available")

    # 3. Get signal
    analysis_signal = (
        db.query(ShortTermAnalysisSignal)
        .filter(ShortTermAnalysisSignal.ticker == ticker)
        .first()
    )
    if not analysis_signal:
        raise HTTPException(status_code=404, detail="No signal found")

    # 4. Insert entry into DB
    entry = EntriedStock(
        ticker=ticker,
        detected_at=volume_info.detected_at,
        entry_price=entry_price,
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

    # Get historical volume snapshot at entry time
    entry_snapshot = (
        db.query(VolumeSnapshot)
        .filter(
            VolumeSnapshot.ticker == ticker,
            VolumeSnapshot.detected_at == entry.detected_at
        )
        .first()
    )

    # Get technical signal
    signal = (
        db.query(ShortTermAnalysisSignal)
        .filter_by(ticker=ticker)
        .first()
    )
    if not signal:
        raise HTTPException(status_code=404, detail="Missing technical signal")

    # Get current info from live holdings
    holdings = get_current_holdings(db)
    entry_info = None
    for e in holdings["entries"]:
        if e["ticker"] == ticker:
            entry_info = e
    if not entry_info:
        raise HTTPException(status_code=404, detail="Current holding info not found")

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

    # P/L calculation
    current_price = entry_info["current_price"]
    profit = round((current_price - entry.entry_price) * entry.amount)
    profit_pct = round(((current_price - entry.entry_price) / entry.entry_price) * 100, 2)

    now_str = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime("%Y/%m/%d %H:%M:%S")

    # Prompt
    prompt = f"""
You are a Japanese short-term trading advisor. A user entered a trade for stock {ticker} and wants quick advice.

## Current Time
{now_str}

## Trade
- Ticker: {ticker}, Entry amount: {entry.amount}
- Profit/Loss: ¥{profit} ({profit_pct}%)

## Entry Snapshot
- Entry price: {entry_info["entry_price"]}
- Entry volume rate: {entry_snapshot.volume_rate}
- Entry money flow rate: {entry_snapshot.money_flow_rate}

## Current Snapshot
- Current price: {entry_info["current_price"]}
- Current volume rate: {entry_info["volume_rate"]}
- Current money flow rate {entry_info["money_flow_rate"]}

## Technical Signals
{format_signal(signal)}

## Objective
The user targets daily profit of 3–5%. Usually sells the same day to lock profit unless there is a very strong upside.

### Output:
- Key changes since entry (2–3 lines)
- Advice: **SELL** or **HOLD**
- 2 short bullet justifications
- Confidence Score (0–100)
""".strip()

    try:
        response = openai.chat.completions.create(
            model=model,
            temperature=0.4,
            messages=[
                {"role": "system", "content": "You are a professional Japanese stock trading advisor."},
                {"role": "user", "content": prompt}
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