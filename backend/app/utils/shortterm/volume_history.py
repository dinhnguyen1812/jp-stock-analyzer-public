from bs4 import BeautifulSoup
import httpx
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session
from app.models import DailyVolume

JP_TZ = ZoneInfo("Asia/Tokyo")

def parse_volume(text: str) -> int:
    """Parse volume string like '15,889,800' or '15,889,800 株' to int."""
    return int(text.replace(",", "").replace("株", "").strip())

def fetch_daily_volume_history(ticker: str, days: int = 5):
    """
    Fetch last N days of daily volume data from Yahoo Finance JP with pagination.
    Returns list of dicts with ticker, date, volume.
    """
    results = []
    page = 1
    today = date.today()
    from_date = today - timedelta(days=365)  # adjust range as needed
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
                    volume_str = cols[4].get_text(strip=True)
                    volume = parse_volume(volume_str)
                except Exception:
                    continue

                # Prevent duplicates
                if any(r["date"] == date_obj for r in results):
                    continue

                results.append({
                    "ticker": ticker,
                    "date": date_obj,
                    "volume": volume,
                })

            if len(rows) < 20:
                break

            page += 1

        except Exception as e:
            print(f"❌ Error fetching volume page {page} for {ticker}: {e}")
            break

    # Sort descending by date and return only requested days
    results.sort(key=lambda x: x["date"], reverse=True)
    return results[:days]


def save_daily_volumes(db: Session, ticker: str, volume_data: list):
    for item in volume_data:
        # Check if record exists
        existing = db.query(DailyVolume).filter_by(ticker=ticker, date=item["date"]).first()
        if existing:
            continue
        record = DailyVolume(
            ticker=item["ticker"],
            date=item["date"],
            volume=item["volume"],
        )
        db.add(record)
    db.commit()
