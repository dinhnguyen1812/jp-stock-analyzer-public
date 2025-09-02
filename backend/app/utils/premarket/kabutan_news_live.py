import re
import httpx
import os
import openai
from bs4 import BeautifulSoup
from datetime import date, datetime, timedelta
import asyncio
import requests

from sqlalchemy.orm import Session
from typing import List, Dict

from app.models import StockNewsImpact
from app.utils.premarket.pre_gpt_analyzer import extract_headline_impacts
from app.utils.shortterm.volume_surge_scraper import fetch_intraday_prices

openai.api_key = os.getenv("OPENAI_API_KEY")

def scrape_kabutan_marketnews(limit: int = 30, days_threshold: float = 0.1) -> List[Dict]:
    base_url = "https://kabutan.jp/news/marketnews/?category=2&page="
    # base_url = "https://kabutan.jp/news/marketnews/?page="
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "ja,en;q=0.9"
    }
    news_items = []
    page = 1

    try:
        while len(news_items) < limit and page <= 5:  # allow up to 5 pages
            url = base_url + str(page)
            resp = httpx.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # find ALL news tables (because page can contain 2)
            news_tables = soup.find_all("table", class_="s_news_list")
            if not news_tables:
                print(f"❌ Could not find news tables on Kabutan market news page {page}")
                break

            for news_table in news_tables:
                rows = news_table.find_all("tr")
                if not rows:
                    continue

                for row in rows:
                    time_td = row.find("td", class_="news_time")
                    if not time_td:
                        continue
                    time_tag = time_td.find("time")
                    if not time_tag or not time_tag.has_attr("datetime"):
                        continue

                    published_at = time_tag["datetime"]
                    try:
                        published_dt = datetime.fromisoformat(published_at)
                    except ValueError:
                        continue

                    now = datetime.now(tz=published_dt.tzinfo)
                    if published_dt < now - timedelta(days=days_threshold):
                        continue  # Skip old news

                    # Category (optional)
                    category_td = time_td.find_next_sibling("td")
                    category_div = category_td.find("div") if category_td else None
                    category = category_div.text.strip() if category_div else None

                    # Headline
                    headline_td = category_td.find_next_sibling("td") if category_td else None
                    if not headline_td:
                        continue
                    a_tag = headline_td.find("a")
                    if not a_tag or not a_tag.text.strip():
                        continue

                    headline = a_tag.text.strip()
                    href = a_tag.get("href")
                    if href and not href.startswith("http"):
                        href = f"https://kabutan.jp{href}"

                    news_items.append({
                        "published_at": published_at,
                        "category": category,
                        "headline": headline,
                        "url": href
                    })

                    if len(news_items) >= limit:
                        break
                if len(news_items) >= limit:
                    break
            if len(news_items) >= limit:
                break

            page += 1

        # Sort newest first
        news_items.sort(key=lambda x: x["published_at"], reverse=True)
        return news_items

    except Exception as e:
        print(f"❌ Error scraping Kabutan market news: {e}")
        return []

def save_marketnews_to_db(db: Session, news_items: List[Dict], ticker: str = None):
    for item in news_items:
        published_at = None
        try:
            published_at = datetime.fromisoformat(item["published_at"])
        except Exception:
            pass

        db_item = StockNewsImpact(
            ticker=ticker or "MARKET",
            headline=item["headline"],
            verdict=None,  # GPT analysis can fill later
            reason=None,   # GPT analysis can fill later
            published_at=published_at,
            url=item.get("url")
        )
        db.add(db_item)
    db.commit()

def delete_old_market_news(db: Session):
    today = date.today()

    db.query(StockNewsImpact).filter(
        StockNewsImpact.ticker == "MARKET",
        StockNewsImpact.published_at.isnot(None),
        StockNewsImpact.published_at < datetime.combine(today, datetime.min.time()),
    ).delete(synchronize_session=False)

    db.commit()

def analyze_market_news(db: Session, news_items: List[Dict], model="gpt-3.5-turbo") -> str:
    # Step 1: get the last 50 headlines
    existing_headlines = {
        h[0]
        for h in (
            db.query(StockNewsImpact.headline)
            .order_by(StockNewsImpact.created_at.desc())
            .limit(50)
            .all()
        )
    }

    new_items = [item for item in news_items if item["headline"] not in existing_headlines]

    if not new_items:
        return "No new market news to analyze."

    # Step 2: pre-filter by current price
    filtered_items = []
    for item in new_items:
        news_url = item.get("url")
        tickers = extract_ticker_from_html(news_url) if news_url else []

        if tickers:
            ticker = tickers[0]
            try:
                current_price, _, _, _ = fetch_intraday_prices(ticker)
            except Exception:
                print(f"⚠️ Failed to fetch price for {ticker}, skipping")
                continue
        else:
            ticker = "MARKET"
            current_price = 0  # always include MARKET

        if current_price and current_price <= 300:
            item["ticker"] = ticker
            item["current_price"] = current_price
            filtered_items.append(item)
        else:
            print(f"Skipping {ticker} ({current_price}¥) because price > 300")

    if not filtered_items:
        return "No news to analyze after price filter."

    # Step 3: collect raw headlines for GPT prompt
    raw_headlines = [item["headline"] for item in filtered_items]

    # Step 4: build prompt
    prompt = (
        f"You are a Japanese market expert AI analyzing stock news.\n\n"
        "### Objective:\n"
        "- Identify headlines likely to trigger **intraday price movements**.\n"
        "- Pay special attention to topics like **semiconductors, AI, lithium, stock splits, offerings**, etc.\n"
        "- Even procedural headlines like 株式発行, 剰余金の処分, 業務提携 can move markets — do not dismiss them without consideration.\n"

        "- 🧠 News Impact Ranking:\n"
        "- For each top headline, assign a keyword and rank based on this table:\n"
        "  {\n"
        # S rank - strongest triggers
        "    'TOB / MBO': 'S',\n"

        # A+ rank - very strong positive
        "    '大型受注': 'A+',\n"

        # A rank - strong positive
        "    '黒字転換': 'A',\n"
        "    '新市場参入': 'A',\n"
        "    '新サービス発表': 'A',\n"
        "    '特許取得': 'A',\n"
        "    '新製品発表': 'A',\n"
        "    '事業拡大': 'A',\n"
        "    '買収': 'A',\n"
        "    '独占契約': 'A',\n"
        "    '新任紹介': 'A',\n"
        "    '受賞': 'A',\n"
        "    '新ビージョン': 'A',\n"
        "    '販売契約': 'A',\n"
        "    '増益': 'A',\n"
        "    '今期 業績予想 50%増益以上': 'A',\n"
        "    'サプライズ決算': 'A',\n"
        "    '四半期サプライズ決算': 'A',\n"
        "    '利益倍増': 'A',\n"

        # A- rank - technical signals
        "    'ゴールデンクロス': 'A-',\n"
        "    '±３σブレイク': 'A-',\n"
        "    'ボリンジャーバンド上抜け': 'A-',\n"
        "    'fisco注目': 'A-',\n"
        "    'ストップ高': 'A-',\n"
        "    '動意株': 'A-',\n"
        "    'Technical': 'A-',\n"
        "    '業績予想 上方修正': 'A-',\n"

        # B rank - moderate positive
        "    '中期経営計画': 'B',\n"
        "    '株式買戻し': 'B',\n"
        "    '特別利益': 'B',\n"
        "    '株主優待増額': 'B',\n"
        "    '配当増額': 'B',\n"
        "    '大量保有報告書': 'B',\n"
        "    '赤字縮小': 'B',\n"
        "    '月次売上・業績データ': 'B',\n"
        "    '筆頭株主変更': 'B',\n"

        # C rank - negative or neutral
        "    '施設閉鎖': 'C',\n"
        "    '運営終了': 'C',\n"
        "    '事業報告': 'C',\n"
        "    '株式発行': 'C',\n"
        "    '株主総会': 'C',\n"
        "    '一目均衡表・雲抜け': 'C',\n"

        # D rank - negative
        "    '減益': 'D',\n"
        "    '赤字転落': 'D',\n"
        "    '赤字拡大': 'D'\n"
        "    '資本金変更': 'D',\n"
        "    '再掲IR': 'D',\n"
        "    '過去の材料再加熱': 'D'\n"
        "    '上場廃止': 'D'\n"
        "  }\n\n"

        "- 🔧 Booster Instruction:\n"
        "  - HOT/TRENDING SECTORS: Data center, AI, Web3, semiconductors, space, quantum computing, medical tech, robotics, FinTech, crypto, mobility, biotech, data centers, EV, hydrogen.\n"
        "  - Boost ranks (S+, A+, etc.) if the news related to the HOT/TRENDING SECTORS, major institution, foreign fund, strategic partner, or high profitability.\n\n"

        "### Output Format:\n"
        "Headline List:\n"
        "1. **[Headline text here]**\n"
        "   - **Verdict: [S+, S, A+, A, A-, B, C, D]**\n"
        "   - **Reason: [Keyword - 1 short sentence explaining the expected short-term impact]**\n"
        "(Repeat for each headline)\n\n"
        "News headlines:\n" + "\n".join([f"{i+1}. {hl}" for i, hl in enumerate(raw_headlines)])
    )
    # Step 5: call GPT
    try:
        response = openai.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        reply = response.choices[0].message.content.strip()
        impacts = extract_headline_impacts(reply)
        print(f"====impacts={impacts}")

        # Step 6: save impacts to DB
        for item in impacts:
            if not item.get("headline") or not item.get("verdict"):
                continue

            matched_news = next(
                (n for n in filtered_items if n['headline'] in item['headline']), None
            )

            news_url = matched_news.get("url") if matched_news else None
            ticker = matched_news.get("ticker") if matched_news else "MARKET"

            impact = StockNewsImpact(
                ticker=ticker,
                headline=item["headline"],
                verdict=item["verdict"],
                reason=item.get("reason", ""),
                created_at=datetime.utcnow(),
                published_at=matched_news.get("published_at") if matched_news else None,
                url=news_url,
            )
            db.add(impact)

        db.commit()

        if any(i["verdict"] in {"S+", "S", "A+", "A", "A-", "B"} for i in impacts):
            print(f"🚨 Positive news detected: {', '.join(i['verdict'] for i in impacts)}")

        return impacts

    except Exception as e:
        print(f"❌ GPT analysis failed: {e}")
        return None
    
VERDICT_PRIORITY = {"S+":5, "S":4, "A+":3, "A":2, "A-":1, "B":0, "C":0, "D":0}

async def scan_market_news_once(db: Session, limit: int = 30):
    try:
        # Delete old news
        delete_old_market_news(db)

        # Scrape latest news
        news_items: List[Dict] = scrape_kabutan_marketnews(limit=limit)
        if not news_items:
            return []

        # Step 1: GPT-3.5 analysis
        impacts = analyze_market_news(db, news_items, model="gpt-4o")
        if not impacts:
            return []

        # # Step 2: GPT-4o re-analysis for high-impact items
        # high_impact_items = [
        #     i for i in impacts if VERDICT_PRIORITY.get(i["verdict"], 0) > VERDICT_PRIORITY["A-"]
        # ]
        # if high_impact_items:
        #     temp_news_items = [
        #         {"headline": i["headline"], "published_at": i.get("published_at"), "url": i.get("url"), "category": None}
        #         for i in high_impact_items
        #     ]
        #     analyze_market_news(db, temp_news_items, model="gpt-4o")

        # Step 3: return alerts for ≥ A
        alert_items = [i for i in impacts if VERDICT_PRIORITY.get(i["verdict"], 0) >= VERDICT_PRIORITY["A-"]]
        return alert_items

    except Exception as e:
        print(f"❌ Error in single market news scan: {e}")
        return []

async def background_market_news_scanner(db: Session, interval_minutes: int = 1, limit: int = 30):
    while True:
        try:
            print(f"🗑️ Deleting old market news...")
            delete_old_market_news(db)

            print(f"📡 Scraping latest market news (limit={limit})...")
            news_items: List[Dict] = scrape_kabutan_marketnews(limit=limit)

            if not news_items:
                print("ℹ️ No news found from scraping.")
                await asyncio.sleep(interval_minutes * 60)
                continue

            print(f"💡 Analyzing {len(news_items)} news items with GPT-3.5...")
            impacts = analyze_market_news(db, news_items, model="gpt-3.5-turbo")

            if impacts:
                high_impact_items = [i for i in impacts if VERDICT_PRIORITY.get(i["verdict"], 0) > VERDICT_PRIORITY["A-"]]
                if high_impact_items:
                    print(f"🚀 Re-analyzing {len(high_impact_items)} high-impact items with GPT-4o...")
                    temp_news_items = [{"headline": i["headline"], "published_at": i.get("published_at"), "url": i.get("url"), "category": None} for i in high_impact_items]
                    analyze_market_news(db, temp_news_items, model="gpt-4o")

            alert_items = [i for i in impacts if VERDICT_PRIORITY.get(i["verdict"], 0) >= VERDICT_PRIORITY["A"]]
            if alert_items:
                print("🚨 Market Alert! Important news detected:")
                for i in alert_items:
                    print(f"- [{i['verdict']}] {i['headline']}")

        except Exception as e:
            print(f"❌ Error in market news scanner loop: {e}")

        print(f"⏳ Sleeping for {interval_minutes} minutes...\n")
        await asyncio.sleep(interval_minutes * 60)

def extract_ticker_from_html(url: str) -> list[str]:
    """
    Fetch HTML from `url`, extract ticker codes like <1234> or < 1234 >,
    return list of tickers as strings.
    """
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        text_content = soup.get_text(" ", strip=True)

        # match <1234> or < 1234 >
        matches = re.findall(r"<\s*(\d{4})\s*>", text_content)
        return list(set(matches))  # unique tickers
    except Exception as e:
        print(f"⚠️ Failed to extract ticker from {url}: {e}")
        return []
