from bs4 import BeautifulSoup
import httpx
from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session
from app.models import DailyVolume

JP_TZ = ZoneInfo("Asia/Tokyo")

def parse_volume(text: str) -> int:
    """Parse volume string like '15,889,800' or '15,889,800 株' to int."""
    return int(text.replace(",", "").replace("株", "").strip())

def fetch_daily_volume_history(ticker: str, days: int = 5):
    url = f"https://finance.yahoo.co.jp/quote/{ticker}.T/history"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "ja,en;q=0.9",
    }

    try:
        resp = httpx.get(url, headers=headers, timeout=10)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.select("table tbody tr")
        results = []

        for row in rows[:days]:
            try:
                date_th = row.find("th")
                if not date_th:
                    continue
                date_str = date_th.get_text(strip=True)  # e.g., "2025年6月25日"
                date_obj = datetime.strptime(date_str, "%Y年%m月%d日").date()

                cols = row.find_all("td")
                if len(cols) < 5:
                    continue

                volume_str = cols[4].get_text(strip=True)  # 5th column (0-indexed)
                volume = parse_volume(volume_str)
                print({
                    "ticker": ticker,
                    "date": date_obj,
                    "volume": volume,
                })

                results.append({
                    "ticker": ticker,
                    "date": date_obj,
                    "volume": volume,
                })

            except Exception as e:
                print(f"⚠️ Error parsing row: {e}")
                continue

        return results

    except Exception as e:
        print(f"❌ Error fetching volume history for {ticker}: {e}")
        return []


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
