from datetime import datetime, timedelta, date
from typing import Optional
from bs4 import BeautifulSoup
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models import DailyPrice

def parse_price(text: str) -> float:
    return float(text.replace(",", "").replace("円", "").strip())

def get_latest_date_in_db(db: Session, ticker: str) -> Optional[date]:
    """
    Get the most recent date stored in DB for the ticker.
    """
    latest = (
        db.query(DailyPrice)
        .filter(DailyPrice.ticker == ticker)
        .order_by(desc(DailyPrice.date))
        .first()
    )
    return latest.date if latest else None

def fetch_price_history(ticker: str, from_date: date, to_date: date, max_days: int = 30) -> list[dict]:
    """
    Fetch OHLC price data from Yahoo Finance JP between from_date and to_date.
    Returns list of dicts: {ticker, date, open, high, low, close}.
    """
    results = []
    page = 1

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "ja,en;q=0.9",
    }

    while len(results) < max_days:
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
                break

            for row in rows:
                if len(results) >= max_days:
                    break

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

                if any(r["date"] == date_obj for r in results):
                    continue

                # Only include dates within the desired range
                if date_obj < from_date or date_obj > to_date:
                    continue

                results.append({
                    "ticker": ticker,
                    "date": date_obj,
                    "open": open_,
                    "high": high,
                    "low": low,
                    "close": close,
                })

            if len(rows) < 20:
                break

            page += 1

        except Exception as e:
            print(f"❌ Error fetching page {page} for {ticker}: {e}")
            break

    results.sort(key=lambda x: x["date"], reverse=True)
    return results[:max_days]

def save_price_data(db: Session, price_data: list[dict]):
    """
    Save fetched price data to DB, avoiding duplicates.
    """
    for item in price_data:
        exists = db.query(DailyPrice).filter_by(
            ticker=item["ticker"], date=item["date"]
        ).first()
        if exists:
            continue
        db.add(DailyPrice(
            ticker=item["ticker"],
            date=item["date"],
            open=item["open"],
            high=item["high"],
            low=item["low"],
            close=item["close"],
        ))
    db.commit()

def fetch_and_save_price_history(db: Session, ticker: str, max_days: int = 150):
    """
    Wrapper to fetch and store only NEW daily price data.
    """
    today = date.today()
    latest_db_date = get_latest_date_in_db(db, ticker)

    if latest_db_date is None:
        # No data in DB yet, fetch from 50 days ago
        from_date = today - timedelta(days=50)
    else:
        # Fetch only data newer than the latest in DB
        from_date = latest_db_date + timedelta(days=1)

    if from_date > today:
        print(f"✅ Price data for {ticker} is already up to date.")
        return

    new_data = fetch_price_history(ticker, from_date=from_date, to_date=today, max_days=max_days)
    if new_data:
        save_price_data(db, new_data)
        print(f"✅ Saved {len(new_data)} new records for {ticker}")
    else:
        print(f"ℹ️ No new data found for {ticker}")
