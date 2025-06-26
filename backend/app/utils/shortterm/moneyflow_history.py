from bs4 import BeautifulSoup
import httpx
from datetime import datetime
from sqlalchemy.orm import Session
from app.models import DailyMoneyFlow

# Parse price (float, like 2564.5)
def parse_price(text: str) -> float:
    return float(text.replace(",", "").replace("円", "").strip())

# Parse volume (int, like 16,444,700)
def parse_volume(text: str) -> int:
    return int(text.replace(",", "").replace("株", "").strip())

def fetch_daily_money_flow_history(ticker: str, days: int = 5):
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
                date_str = date_th.get_text(strip=True)
                date_obj = datetime.strptime(date_str, "%Y年%m月%d日").date()

                cols = row.find_all("td")
                if len(cols) < 6:
                    continue

                open_price = parse_price(cols[0].text.strip())
                high = parse_price(cols[1].text.strip())
                low = parse_price(cols[2].text.strip())
                close = parse_price(cols[3].text.strip())
                volume = parse_volume(cols[4].text.strip())

                typical_price = round((high + low + close) / 3, 2)
                money_flow = round(typical_price * volume)

                results.append({
                    "ticker": ticker,
                    "date": date_obj,
                    "typical_price": typical_price,
                    "volume": volume,
                    "money_flow": money_flow,
                })

            except Exception as e:
                print(f"⚠️ Error parsing row: {e}")
                continue

        return results

    except Exception as e:
        print(f"❌ Error fetching money flow history for {ticker}: {e}")
        return []

def save_daily_money_flows(db: Session, ticker: str, flow_data: list):
    for item in flow_data:
        existing = db.query(DailyMoneyFlow).filter_by(ticker=ticker, date=item["date"]).first()
        if existing:
            continue
        record = DailyMoneyFlow(**item)
        db.add(record)
    db.commit()
