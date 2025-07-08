from bs4 import BeautifulSoup
from typing import Optional, List, Dict
import re
import httpx
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session, aliased
from sqlalchemy import func
from app.models import VolumeSnapshot, AverageVolume, AverageMoneyFlow, StarredStock
from app.utils.shortterm.volume_history import fetch_daily_volume_history, save_daily_volumes
from app.utils.shortterm.volume_5d_average_updater import update_avg_volume_for_ticker
from app.utils.shortterm.moneyflow_history import fetch_daily_money_flow_history, save_daily_money_flows
from app.utils.shortterm.moneyflow_5d_average_updater import update_avg_money_flow_for_ticker

JP_TZ = ZoneInfo("Asia/Tokyo")
JP_OPEN = time(9, 0)  # 9:00 AM JST

def parse_volume(text: str) -> int:
    return int(text.replace(",", "").replace("株", "").strip())

def parse_price(text: str) -> float:
    return float(text.replace(",", "").strip())

def analyze_intraday_activity(db: Session, ticker: str, current_volume: int) -> Optional[dict]:
    now = datetime.now(JP_TZ)
    market_open = now.replace(hour=JP_OPEN.hour, minute=JP_OPEN.minute, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=0, second=0, microsecond=0)

    # Ensure avg volume exists
    avg_record = db.query(AverageVolume).filter_by(ticker=ticker).first()
    if not avg_record or avg_record.avg_5d_volume == 0:
        print(f"ℹ️ No avg_5d_volume for {ticker}, trying to scrape history and update...")
        volume_data = fetch_daily_volume_history(ticker)
        if volume_data:
            save_daily_volumes(db, ticker, volume_data)
            update_avg_volume_for_ticker(db, ticker)
            avg_record = db.query(AverageVolume).filter_by(ticker=ticker).first()
        else:
            print(f"❌ Failed to fetch volume history for {ticker}, skipping.")
            return None

    if not avg_record or avg_record.avg_5d_volume == 0:
        print(f"⏩ Still no avg_5d_volume for {ticker} after update, skipping.")
        return None

    avg_volume_5d = avg_record.avg_5d_volume
    if now <= market_open or now >= market_close:
        expected_volume_by_now = avg_volume_5d
    else:
        trading_hours_passed = max((now - market_open).total_seconds() / 3600, 0.5)
        expected_volume_by_now = avg_volume_5d * (trading_hours_passed / 6)

    volume_rate = current_volume / expected_volume_by_now if expected_volume_by_now > 0 else 0

    # Get intraday price stats
    current_price, high, low = fetch_intraday_prices(ticker)
    if not all([current_price, high, low]):
        print(f"⚠️ Skipping {ticker}: could not get high/low/current prices.")
        return None

    typical_price_now = (high + low + current_price) / 3
    raw_money_flow_now = typical_price_now * current_volume

    # Ensure avg money flow exists
    moneyflow_record = db.query(AverageMoneyFlow).filter_by(ticker=ticker).first()
    if not moneyflow_record or moneyflow_record.avg_5d_money_flow == 0:
        print(f"ℹ️ No avg_5d_money_flow for {ticker}, trying to scrape history and update...")
        flow_data = fetch_daily_money_flow_history(ticker)
        if flow_data:
            save_daily_money_flows(db, ticker, flow_data)
            update_avg_money_flow_for_ticker(db, ticker)
            moneyflow_record = db.query(AverageMoneyFlow).filter_by(ticker=ticker).first()
        else:
            print(f"❌ Failed to fetch money flow history for {ticker}, skipping money flow.")
            moneyflow_record = None

    money_flow_rate = (
        raw_money_flow_now / moneyflow_record.avg_5d_money_flow
        if moneyflow_record and moneyflow_record.avg_5d_money_flow > 0 else None
    )

    return {
        "current_price": current_price,
        "avg_volume_5d": avg_volume_5d,
        "volume_rate": round(volume_rate, 2),
        "money_flow_rate": round(money_flow_rate, 2) if money_flow_rate is not None else None,
    }

def get_intraday_volume_info_for_ticker(db: Session, ticker: str) -> Optional[VolumeSnapshot]:
    url = f"https://finance.yahoo.co.jp/quote/{ticker}.T"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "ja,en;q=0.9",
    }

    try:
        resp = httpx.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # 1. Extract name
        name_tag = (
            soup.select_one("h2.PriceBoardMain__name__6uDh")  # during trading
            or soup.select_one("h2.PriceBoard__name__166W")   # after close
        )
        name = name_tag.text.strip() if name_tag else ticker

        # 2. Extract 出来高 (current volume)
        current_volume = None
        labels = soup.select("span.DataListItem__name__3RQJ")
        for label in labels:
            if "出来高" in label.text:
                value_span = label.find_next("span", class_="StyledNumber__value__3rXW")
                if value_span:
                    raw_volume = value_span.text.strip()
                    if raw_volume not in {"---", "-", ""}:
                        try:
                            current_volume = parse_volume(raw_volume)
                        except ValueError:
                            print(f"⚠️ Invalid volume format for {ticker}: {raw_volume}")
                            return None
                    else:
                        print(f"⚠️ No valid volume for {ticker} (got: {raw_volume})")
                        return None
                break

        # 3. Extract price change percentage
        percent_change = 0.0
        change_container = soup.select_one("dd.PriceChangeLabel__description__a5Lp")
        if change_container:
            percent_spans = change_container.select("span.StyledNumber__value__3rXW")
            if len(percent_spans) >= 2:
                percent_text = percent_spans[1].text.replace("+", "").replace("%", "").strip()
                try:
                    percent_change = float(percent_text)
                except ValueError:
                    pass
            else:
                print(f"⚠️ Couldn't find percentage span for {ticker}")
        else:
            print(f"⚠️ Price change container not found for {ticker}")

        # 4. Analyze volume/money flow
        analysis = analyze_intraday_activity(db, ticker, current_volume)
        if not analysis:
            return None

        # 5. Create and store VolumeSnapshot
        now = datetime.now(JP_TZ)
        snapshot = VolumeSnapshot(
            ticker=ticker,
            name=name,
            current_price=analysis["current_price"],
            price_change=percent_change,
            current_volume=current_volume,
            avg_volume_5d=analysis["avg_volume_5d"],
            volume_rate=analysis["volume_rate"],
            money_flow_rate=analysis["money_flow_rate"],
            detected_at=now,
        )

        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)  # ensures snapshot has its ID and is attached to session

        return snapshot

    except Exception as e:
        print(f"❌ Failed to fetch intraday info for {ticker}: {e}")
        return None


def fetch_volume_page(db: Session, page: int = 1):
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
                match = re.search(r"quote/([\dA-Za-z]+)\.T", href)
                if not match:
                    raise ValueError(f"Ticker not found in href: {href}")
                ticker = match.group(1)

                volume_td = row.select("td")[3]  # 4th column is volume
                volume_str = volume_td.get_text(strip=True)
                current_volume = parse_volume(volume_str)

                price_td = row.select("td")[1]
                price_value_span = price_td.select_one("span.StyledNumber__value__3rXW")
                if not price_value_span:
                    raise ValueError("Could not find price span")

                price_change_td = row.select("td")[2]
                value_spans = price_change_td.select("span.StyledNumber__value__3rXW")
                if len(value_spans) < 2:
                    raise ValueError("Expected 2 value spans (price change and percentage), but got fewer.")
                percent_change_str = value_spans[1].text.strip()  # +0.50
                percent_change_str = percent_change_str.replace("%", "")
                percent_change = float(percent_change_str)

                analysis = analyze_intraday_activity(db, ticker, current_volume)
                if not analysis:
                    continue

                results.append({
                    "ticker": ticker,
                    "name": name,
                    "current_price": analysis["current_price"],
                    "price_change": percent_change,
                    "current_volume": current_volume,
                    "avg_volume_5d": analysis["avg_volume_5d"],
                    "volume_rate": analysis["volume_rate"],
                    "money_flow_rate": analysis["money_flow_rate"],
                    "timestamp": datetime.now(JP_TZ),
                })

            except Exception as e:
                print(f"⚠️ Skipping row due to error: {e}")

        return results
    except Exception as e:
        print(f"❌ Error fetching volume page {page}: {e}")
        return []

def scan_and_save_volume_surges(
    db: Session,
    surge_threshold: float = 1.5,
    price_threshold: float = 300.0,
    from_page: int = 1,
    to_page: int = 1
) -> List[str]:
    half_hour_ago = datetime.now(JP_TZ) - timedelta(hours=0.5)

    # Step 1: Get tickers already scanned within the past hour
    recent_tickers = {
        row.ticker
        for row in db.query(VolumeSnapshot)
        .filter(VolumeSnapshot.detected_at >= half_hour_ago)
        .all()
    }

    all_results = []
    for page in range(from_page, to_page + 1):
        page_data = fetch_volume_page(db, page)
        all_results.extend(page_data)

    now = datetime.now(JP_TZ)
    saved_tickers = []
    for stock in all_results:
        ticker = stock["ticker"]
        if (
            ticker in recent_tickers
            or stock["volume_rate"] < surge_threshold
            or stock["current_price"] > price_threshold
        ):
            continue

        snapshot = VolumeSnapshot(
            ticker=ticker,
            name=stock["name"],
            current_price=stock["current_price"],
            price_change=stock["price_change"],
            current_volume=stock["current_volume"],
            avg_volume_5d=stock["avg_volume_5d"],
            volume_rate=stock["volume_rate"],
            money_flow_rate=stock["money_flow_rate"],
            detected_at=now,
        )
        db.add(snapshot)
        saved_tickers.append(ticker)

    db.commit()
    print(
        f"📈 Volume scan complete. Scanned pages {from_page} to {to_page}. "
        f"{len(saved_tickers)} new tickers saved (skipped {len(recent_tickers)} recent ones)."
    )
    return saved_tickers

def fetch_intraday_prices(ticker: str):
    url = f"https://finance.yahoo.co.jp/quote/{ticker}.T"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "ja,en;q=0.9",
    }

    try:
        resp = httpx.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # ⬇️ Get current price from dedicated HTML structure
        def get_current_price() -> Optional[float]:
            # Try original selector first (during market open)
            price_tag = soup.select_one("div.PriceBoardMain__headerPrice__gbs7 span.StyledNumber__value__3rXW")
            if price_tag:
                try:
                    return parse_price(price_tag.text)
                except ValueError:
                    pass

            # Fallback selector (after market close)
            price_tag_alt = soup.select_one("span.PriceBoard__price__1V0k span.StyledNumber__value__3rXW")
            if price_tag_alt:
                try:
                    return parse_price(price_tag_alt.text)
                except ValueError:
                    pass

            return None

        def get_value_by_label(label_ja: str) -> Optional[float]:
            dl_tags = (soup.select("dl.DataListItem__38iJ") or soup.select("dl.DataListItem__name__3RQJ"))
            for dl in dl_tags:
                term = dl.find("dt")
                if term and label_ja in term.get_text():
                    value_tag = dl.find("span", class_="DataListItem__value__11kV")
                    if value_tag:
                        try:
                            return parse_price(value_tag.text)
                        except ValueError:
                            return None
            return None

        current = get_current_price()
        high = get_value_by_label("高値")
        low = get_value_by_label("安値")

        return current, high, low

    except Exception as e:
        print(f"❌ Failed to fetch quote info for {ticker}: {e}")
        return None, None, None

def get_latest_volume_surges(
    db: Session,
    surge_threshold: float = 2.0,
    price_threshold: float = 300.0,
    promising_score_threshold: float = 30.0,
    starred_only: bool = False,
) -> List[dict]:
    # Subquery: get latest snapshot per ticker with promising_score >= threshold
    subquery = (
        db.query(
            VolumeSnapshot.ticker,
            func.max(VolumeSnapshot.detected_at).label("latest_time")
        )
        .filter(VolumeSnapshot.promising_score >= promising_score_threshold)
        .group_by(VolumeSnapshot.ticker)
        .subquery()
    )

    VS = aliased(VolumeSnapshot)

    query = (
        db.query(VS)
        .join(subquery, (VS.ticker == subquery.c.ticker) & (VS.detected_at == subquery.c.latest_time))
        .filter(VS.volume_rate >= surge_threshold)
        .filter(VS.current_price <= price_threshold)
    )

    if starred_only:
        starred_tickers = {s.ticker for s in db.query(StarredStock).all()}
        query = query.filter(VS.ticker.in_(starred_tickers))
    else:
        starred_tickers = set()

    results = query.all()
    for r in results:
        if r.ticker=="7610":
            print(f"ticker: {r.ticker}, promising_score: {r.promising_score}, recommendation: {r.recommendation}")

    return [
        {
            "ticker": r.ticker,
            "name": r.name,
            "current_price": r.current_price,
            "price_change": r.price_change,
            "volume_rate": r.volume_rate,
            "money_flow_rate": r.money_flow_rate,
            "current_volume": r.current_volume,
            "avg_volume_5d": r.avg_volume_5d,
            "detected_at": r.detected_at.isoformat(),
            "reasoning": r.reasoning,
            "recommendation": r.recommendation,
            "promising_score": r.promising_score,
            "top_news": r.top_news,
            "starred": r.ticker in starred_tickers,
        }
        for r in results
    ]


