from datetime import datetime
from typing import List, Optional
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session
import httpx
from bs4 import BeautifulSoup
import re

from app.utils.shortterm.volume_5d_average_updater import update_avg_volume_for_ticker
from app.utils.shortterm.moneyflow_5d_average_updater import update_avg_money_flow_for_ticker
from app.utils.shortterm.price_updater import fetch_and_save_price_history
from app.models import (
    VolumeSnapshot,
    AverageVolume,
    AverageMoneyFlow,
    DailyVolume,
    DailyPrice,
    StarredStock,
)

JP_TZ = ZoneInfo("Asia/Tokyo")

def parse_volume(text: str) -> int:
    return int(text.replace(",", "").replace("株", "").strip())

def get_latest_trading_day(db: Session, ticker: str) -> Optional[datetime.date]:
    latest = (
        db.query(DailyVolume.date)
        .filter(DailyVolume.ticker == ticker)
        .order_by(DailyVolume.date.desc())
        .limit(1)
        .first()
    )
    return latest[0] if latest else None

def fetch_name_from_yahoo(ticker: str) -> str:
    url = f"https://finance.yahoo.co.jp/quote/{ticker}.T"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "ja,en;q=0.9",
    }

    try:
        resp = httpx.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        name_tag = (
            soup.select_one("h2.PriceBoardMain__name__6uDh") or
            soup.select_one("h2.PriceBoard__name__166W")
        )
        return name_tag.text.strip() if name_tag else ticker
    except Exception as e:
        print(f"⚠️ Failed to fetch name for {ticker}: {e}")
        return ticker

def fetch_ranked_volume_tickers(from_page: int = 1, to_page: int = 5) -> List[str]:
    tickers = set()
    for page in range(from_page, to_page + 1):
        url = f"https://finance.yahoo.co.jp/stocks/ranking/volume?market=all&term=daily&page={page}"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "ja,en;q=0.9",
        }

        try:
            resp = httpx.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            rows = soup.select("tr.RankingTable__row__1Gwp")

            for row in rows:
                try:
                    name_tag = row.select_one("td:nth-of-type(1) a")
                    href = name_tag.get("href")
                    match = re.search(r"quote/([\dA-Za-z]+)\.T", href)
                    if match:
                        ticker = match.group(1)
                        tickers.add(ticker)
                except Exception as e:
                    print(f"⚠️ Skipping row: {e}")
        except Exception as e:
            print(f"❌ Failed to fetch volume ranking page {page}: {e}")
    return list(tickers)

def analyze_and_snapshot_ticker(
    db: Session,
    ticker: str,
    surge_threshold: float = 1.5,
    price_threshold: float = 300.0,
) -> Optional[VolumeSnapshot]:
    try:
        update_avg_volume_for_ticker(db, ticker)
        update_avg_money_flow_for_ticker(db, ticker)
        fetch_and_save_price_history(db, ticker)

        last_day = get_latest_trading_day(db, ticker)
        if not last_day:
            return None

        dv = db.query(DailyVolume).filter_by(ticker=ticker, date=last_day).first()
        if not dv or dv.volume == 0:
            return None

        avg_vol = db.query(AverageVolume).filter_by(ticker=ticker).first()
        if not avg_vol or avg_vol.avg_5d_volume == 0:
            return None

        volume_rate = dv.volume / avg_vol.avg_5d_volume
        if volume_rate < surge_threshold:
            return None

        price = db.query(DailyPrice).filter_by(ticker=ticker, date=last_day).first()
        if not price:
            return None
        current_price = price.close
        if current_price > price_threshold:
            return None

        # Money flow rate
        avg_money = db.query(AverageMoneyFlow).filter_by(ticker=ticker).first()
        money_flow_rate = None
        if avg_money and avg_money.avg_5d_money_flow > 0:
            typical_price = (price.high + price.low + price.close) / 3
            raw_money_flow = typical_price * dv.volume
            money_flow_rate = round(raw_money_flow / avg_money.avg_5d_money_flow, 2)

        # Get name
        name = fetch_name_from_yahoo(ticker)

        snapshot = VolumeSnapshot(
            ticker=ticker,
            name=name,
            current_price=current_price,
            price_change=0.0,
            current_volume=dv.volume,
            avg_volume_5d=avg_vol.avg_5d_volume,
            volume_rate=round(volume_rate, 2),
            money_flow_rate=money_flow_rate,
            detected_at=datetime.now(JP_TZ),
        )

        db.add(snapshot)
        db.commit()

        return snapshot
    except Exception as e:
        print(f"⚠️ Error analyzing {ticker}: {e}")
        return None

def scan_and_save_pre_market_volume_surges(
    db: Session,
    surge_threshold: float = 1.5,
    price_threshold: float = 300.0,
    from_page: int = 1,
    to_page: int = 5
) -> List[str]:
    tickers = fetch_ranked_volume_tickers(from_page, to_page)
    saved_tickers = []

    for ticker in tickers:
        snapshot = analyze_and_snapshot_ticker(
            db, ticker, surge_threshold, price_threshold
        )
        if snapshot:
            saved_tickers.append(ticker)

    print(f"🌅 Pre-market scan saved {len(saved_tickers)} tickers from {len(tickers)} candidates.")
    return saved_tickers
