from bs4 import BeautifulSoup
import httpx
from datetime import datetime, time
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session
from app.models import VolumeSnapshot
import re

JP_TZ = ZoneInfo("Asia/Tokyo")
JP_OPEN = time(9, 0)  # 9:00 AM JST

def parse_volume(text: str) -> int:
    return int(text.replace(",", "").replace("株", "").strip())

def fetch_volume_page(page: int = 1):
    url = f"https://finance.yahoo.co.jp/stocks/ranking/volume?market=all&term=daily&page={page}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "ja,en;q=0.9",
    }

    try:
        resp = httpx.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.select("tr.RankingTable__row__1Gwp")

        results = []
        for row in rows:
            try:
                name_tag = row.select_one("td:nth-of-type(1) a")
                name = name_tag.text.strip()
                href = name_tag.get("href")
                match = re.search(r"quote/(\d+)\.T", href)
                if not match:
                    raise ValueError(f"Ticker not found in href: {href}")
                ticker = match.group(1)

                volume_td = row.select("td")[3]  # 4th column is volume
                volume_str = volume_td.get_text(strip=True)
                current_volume = parse_volume(volume_str)

                # Approximate average volume: not provided here, use placeholder or skip
                avg_volume_5d = current_volume // 3 if current_volume else 0
                if avg_volume_5d == 0:
                    continue

                now = datetime.now(JP_TZ)
                market_open = now.replace(hour=JP_OPEN.hour, minute=JP_OPEN.minute, second=0, microsecond=0)
                trading_hours_passed = max((now - market_open).total_seconds() / 3600, 0.5)  # Avoid div by 0

                expected_volume_by_now = (avg_volume_5d / 5) * (trading_hours_passed / 6)
                volume_rate = current_volume / expected_volume_by_now if expected_volume_by_now > 0 else 0

                print({
                    "ticker": ticker,
                    "name": name,
                    "current_volume": current_volume,
                    "avg_volume_5d": avg_volume_5d,
                    "volume_rate": round(volume_rate, 2),
                    "timestamp": now,
                })

                results.append({
                    "ticker": ticker,
                    "name": name,
                    "current_volume": current_volume,
                    "avg_volume_5d": avg_volume_5d,
                    "volume_rate": round(volume_rate, 2),
                    "timestamp": now,
                })

            except Exception as e:
                print(f"⚠️ Skipping row due to error: {e}")

        return results
    except Exception as e:
        print(f"❌ Error fetching volume page {page}: {e}")
        return []

def scan_and_save_volume_surges(db: Session, threshold: float = 2.0, pages: int = 3):
    all_results = []
    for page in range(1, pages + 1):
        page_data = fetch_volume_page(page)
        all_results.extend(page_data)

    now = datetime.now(JP_TZ)
    count = 0
    for stock in all_results:
        if stock["volume_rate"] >= threshold:
            snapshot = VolumeSnapshot(
                ticker=stock["ticker"],
                name=stock["name"],
                current_volume=stock["current_volume"],
                avg_volume_5d=stock["avg_volume_5d"],
                volume_rate=stock["volume_rate"],
                detected_at=now,
            )
            db.add(snapshot)
            count += 1

    db.commit()
    print(f"📈 Volume surge scan complete. {len(all_results)} stocks scanned, {count} saved.")
