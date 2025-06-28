from datetime import datetime, timedelta, date
from bs4 import BeautifulSoup
import httpx
from sqlalchemy.orm import Session
from app.models import DailyPrice

def parse_price(text: str) -> float:
    return float(text.replace(",", "").replace("円", "").strip())

def fetch_price_history(ticker: str, days: int = 150) -> list[dict]:
    """
    Fetch last N days of OHLC price data from Yahoo Finance JP with pagination.
    Returns list of dicts: {ticker, date, open, high, low, close}.
    """
    results = []
    page = 1
    today = date.today()
    from_date = today - timedelta(days=365)  # fetch up to 1 year back
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
                break

            for row in rows:
                if len(results) >= days:
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
    return results[:days]

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

def fetch_and_save_price_history(db: Session, ticker: str, days: int = 150):
    """
    Wrapper to fetch and store recent OHLC data.
    """
    data = fetch_price_history(ticker, days=days)
    if data:
        save_price_data(db, data)
