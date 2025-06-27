from bs4 import BeautifulSoup
import httpx
from datetime import datetime, timedelta, date
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models import DailyPrice

def parse_price(text: str) -> float:
    return float(text.replace(",", "").replace("円", "").strip())

def fetch_price_history(ticker: str, days: int = 21):
    """
    Fetch last N days of OHLC price data from Yahoo Finance JP with pagination.
    Returns list of dicts with ticker, date, open, high, low, close.
    """
    results = []
    page = 1
    today = date.today()
    from_date = today - timedelta(days=365)  # fetch up to 1 year back (adjust if needed)
    to_date = today

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "ja,en;q=0.9",
    }

    while len(results) < days:
        url = (
            f"https://finance.yahoo.co.jp/quote/{ticker}.T/history"
            f"?styl=stock&from={from_date.strftime('%Y%m%d')}"
            f"&to={to_date.strftime('%Y%m%d')}"
            f"&timeFrame=d&page={page}"
        )
        try:
            resp = httpx.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            rows = soup.select("table tbody tr")
            if not rows:
                break  # no more data

            for row in rows:
                if len(results) >= days:
                    break  # enough data collected

                date_th = row.find("th")
                if not date_th:
                    continue
                date_str = date_th.get_text(strip=True)
                try:
                    date_obj = datetime.strptime(date_str, "%Y年%m月%d日").date()
                except Exception:
                    continue

                cols = row.find_all("td")
                if len(cols) < 5:
                    continue

                try:
                    open_ = parse_price(cols[0].get_text(strip=True))
                    high = parse_price(cols[1].get_text(strip=True))
                    low = parse_price(cols[2].get_text(strip=True))
                    close = parse_price(cols[3].get_text(strip=True))
                except Exception:
                    continue

                # Avoid duplicates if accidentally fetched same dates
                if any(r["date"] == date_obj for r in results):
                    continue

                results.append({
                    "ticker": ticker,
                    "date": date_obj,
                    "open": open_,
                    "high": high,
                    "low": low,
                    "close": close,
                })

            # If fewer rows than expected on this page, no more pages
            if len(rows) < 20:  # usually 20 rows per page
                break

            page += 1  # next page

        except Exception as e:
            print(f"❌ Error fetching page {page} for {ticker}: {e}")
            break

    # Sort results by date descending (most recent first)
    results.sort(key=lambda x: x["date"], reverse=True)

    return results[:days]

def save_daily_prices(db: Session, price_data: list):
    for item in price_data:
        existing = db.query(DailyPrice).filter_by(ticker=item["ticker"], date=item["date"]).first()
        if existing:
            continue
        record = DailyPrice(
            ticker=item["ticker"],
            date=item["date"],
            open=item["open"],
            high=item["high"],
            low=item["low"],
            close=item["close"],
        )
        db.add(record)
    db.commit()

def detect_breakout(db: Session, ticker: str, lookback_days: int = 20) -> dict:
    required_days = lookback_days + 1

    # Query price data from DB
    price_data = (
        db.query(DailyPrice)
        .filter(DailyPrice.ticker == ticker)
        .order_by(desc(DailyPrice.date))
        .limit(required_days)
        .all()
    )

    # If not enough data, fetch from Yahoo and save
    if len(price_data) < required_days:
        fetched_data = fetch_price_history(ticker, days=required_days * 2)  # Fetch extra days as buffer
        if not fetched_data:
            return {"breakout_detected": False, "reason": "Failed to fetch price data"}

        # Save to DB
        save_daily_prices(db, fetched_data)

        # Re-query after saving
        price_data = (
            db.query(DailyPrice)
            .filter(DailyPrice.ticker == ticker)
            .order_by(desc(DailyPrice.date))
            .limit(required_days)
            .all()
        )
        if len(price_data) < required_days:
            return {"breakout_detected": False, "reason": "Not enough data after fetching"}

    # Prepare data list
    price_list = [{
        "date": p.date,
        "open": p.open,
        "high": p.high,
        "low": p.low,
        "close": p.close
    } for p in price_data]

    today = price_list[0]
    resistance = max(day["high"] for day in price_list[1:])

    breakout = today["close"] > resistance

    return {
        "breakout_detected": breakout,
        "resistance_level": resistance,
        "close_today": today["close"],
        "date": today["date"]
    }