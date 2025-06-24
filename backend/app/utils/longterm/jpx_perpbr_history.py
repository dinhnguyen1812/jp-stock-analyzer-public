from typing import Optional
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import datetime
import os
import csv

from typing import List
from sqlalchemy.orm import Session

from app.models import HistoricalIndicator

def parse_indicator_table(soup, label) -> dict:
    data = {}
    table_div = soup.find("div", {"aria-label": label})
    if not table_div:
        return data

    rows = table_div.find("table").find_all("tr")
    for row in rows[1:]:
        cols = row.find_all("td")
        if len(cols) < 2:
            continue
        try:
            date = datetime.datetime.strptime(cols[0].text.strip(), "%Y/%m/%d").date()
            val = float(cols[1].text.replace("倍", "").strip())
            data[date] = val
        except:
            continue
    return data

def reduce_to_one_per_month(per_data: dict, pbr_data: dict) -> list[dict]:
    monthly_data = {}
    for date in sorted(per_data.keys(), reverse=True):
        month = (date.year, date.month)
        if month not in monthly_data:
            # Prefer 15th, fallback to 14th, then 13th
            for d in [15, 14, 13]:
                try_date = datetime.date(date.year, date.month, d)
                if try_date in per_data:
                    monthly_data[month] = {
                        "date": try_date,
                        "per": per_data.get(try_date),
                        "pbr": pbr_data.get(try_date)
                    }
                    break
    return list(monthly_data.values())

def fetch_historical_indicators_irbank(ticker: str) -> list[dict]:
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # PER
            page.goto(f"https://irbank.net/{ticker}/per", timeout=15000)
            soup_per = BeautifulSoup(page.content(), "html.parser")
            per_data = parse_indicator_table(soup_per, "グラフ内のデータを表形式で表しています。")

            # PBR
            page.goto(f"https://irbank.net/{ticker}/pbr", timeout=15000)
            soup_pbr = BeautifulSoup(page.content(), "html.parser")
            pbr_data = parse_indicator_table(soup_pbr, "グラフ内のデータを表形式で表しています。")

            browser.close()

            return reduce_to_one_per_month(per_data, pbr_data)

    except Exception as e:
        print(f"❌ Error scraping IRBank historical indicators for {ticker}: {e}")
        return []

    
def save_historical_to_csv(ticker: str, records: list[dict]):
    path = f"app/data/historical/{ticker}.csv"
    os.makedirs(os.path.dirname(path), exist_ok=True)

    existing_dates = set()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_dates.add(row["date"])

    new_records = [r for r in records if r["date"].isoformat() not in existing_dates]
    if not new_records:
        return

    write_header = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "per", "pbr"])
        if write_header:
            writer.writeheader()
        for r in new_records:
            writer.writerow({
                "date": r["date"].isoformat(),
                "per": r.get("per", ""),
                "pbr": r.get("pbr", "")
            })

def update_and_get_historical_indicators(ticker: str, db: Session) -> List[HistoricalIndicator]:
    scraped = fetch_historical_indicators_irbank(ticker)
    save_historical_to_csv(ticker, scraped)

    inserted = 0
    for row in scraped:
        date = row["date"]
        existing = db.query(HistoricalIndicator).filter_by(ticker=ticker, date=date).first()
        if existing:
            continue
        db.add(HistoricalIndicator(
            ticker=ticker,
            date=date,
            per=row.get("per"),
            pbr=row.get("pbr")
        ))
        inserted += 1
    db.commit()

    results = db.query(HistoricalIndicator)\
        .filter(HistoricalIndicator.ticker == ticker)\
        .order_by(HistoricalIndicator.date.desc())\
        .limit(12)\
        .all()

    return results[::-1]