from bs4 import BeautifulSoup
import httpx
from difflib import SequenceMatcher
import os
import hashlib
from typing import List
import openai
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models import StockNewsImpact, StarredStock, VolumeSnapshot
from app.utils.premarket.pre_volume_surge_scraper import fetch_ranked_volume_tickers
from app.utils.shortterm.volume_surge_scraper import fetch_intraday_prices
from app.utils.shortterm.kabutan_news_ticker import scrape_kabutan_news
from app.utils.premarket.pre_gpt_analyzer import extract_headline_impacts

openai.api_key = os.getenv("OPENAI_API_KEY")

def is_similar(headline1: str, headline2: str, threshold: float = 0.85) -> bool:
    return SequenceMatcher(None, headline1, headline2).ratio() >= threshold

def get_recent_headlines(db: Session, ticker: str, limit: int = 10) -> List[str]:
    impacts = (
        db.query(StockNewsImpact)
        .filter_by(ticker=ticker)
        .order_by(StockNewsImpact.created_at.desc())
        .limit(limit)
        .all()
    )
    return [i.headline for i in impacts]

def hash_headlines(headlines: list[str]) -> str:
    text = "|".join(headlines)
    return hashlib.md5(text.encode("utf-8")).hexdigest()

def fetch_low_cap_tickers(from_page: int = 1, to_page: int = 10, price_threshold: float = 300.0) -> list[str]:
    tickers = fetch_ranked_volume_tickers(from_page, to_page)
    low_cap_tickers = []

    for ticker in tickers:
        try:
            current_price, _, _ = fetch_intraday_prices(ticker)
            if current_price <= price_threshold:
                low_cap_tickers.append(ticker)
        except Exception as e:
            print(f"Failed to fetch price for {ticker}: {e}")

    return low_cap_tickers

def get_last_headline_hash(db: Session, ticker: str) -> str:
    impacts = db.query(StockNewsImpact).filter_by(ticker=ticker).order_by(StockNewsImpact.created_at.desc()).limit(3).all()
    headlines = [i.headline for i in impacts]
    return hash_headlines(headlines) if headlines else ""

def scan_and_analyze_news_for_ticker(
    db: Session,
    ticker: str,
    top_n: int = 3,
    days_threshold: float = 30.0,
    model: str = "gpt-4o"
):
    news_items = scrape_kabutan_news(ticker, limit=30, days_threshold=days_threshold)
    if not news_items:
        return None

    # ↓↓↓ Apply recency penalty and normalize timestamps ↓↓↓
    now = datetime.now(timezone.utc)
    scored_news = []
    for item in news_items:
        published_at = item.get("published_at")
        if not published_at:
            timestamp = now
        else:
            timestamp = published_at if isinstance(published_at, datetime) else datetime.fromisoformat(published_at)
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
        days_ago = (now - timestamp).days
        freshness_penalty = max(0, days_ago) * 5
        item["recency_penalty"] = freshness_penalty
        item["timestamp"] = timestamp
        scored_news.append(item)

    # Sort by freshness (newer = lower penalty)
    scored_news.sort(key=lambda x: x["recency_penalty"])

    # Headline strings with timestamp
    raw_headlines = [
        f"[{item['category']}] {item['headline']} (🕒 {item['timestamp'].isoformat()})"
        for item in scored_news
    ]

    # recent_headlines = get_recent_headlines(db, ticker)

    # # Filter out headlines similar to already-processed ones
    # filtered_headlines = []
    # for hl in raw_headlines:
    #     if not any(is_similar(hl, past_hl) for past_hl in recent_headlines):
    #         filtered_headlines.append(hl)

    # if not filtered_headlines:
    #     print(f"🟡 Skipping GPT (too similar to past headlines) for {ticker}")
    #     return None
    
    name = get_stock_name(db, ticker)

    # Build enhanced prompt (aligned with premarket GPT logic)
    prompt = (
        f"You are a Japanese market expert AI analyzing stock news for {ticker}, name: {name}.\n\n"
        "### Objective:\n"
        "- Focus **primarily on news released today**, or Friday/weekend news if it's Sunday or Monday.\n"
        "- User targets **daily profit of 3–5%** and usually sells the same day **unless upside is very strong**.\n"
        "- Identify headlines likely to trigger **intraday price movements**.\n"
        "- Pay special attention to topics like **semiconductors, AI, lithium, stock splits, offerings**, etc.\n"
        "- Even procedural headlines like 株式発行, 剰余金の処分, 業務提携 can move markets — do not dismiss them without consideration.\n"
        "- **Note: Any company name in the headlines refers to the ticker being analyzed, or an entity directly involved with it.**\n\n"

        "- 🧠 News Impact Ranking:\n"
        "- For each top headline, assign a keyword and rank based on this table:\n"
        "  {\n"
        # S rank - strongest triggers
        "    'TOB / MBO': 'S',\n"

        # A+ rank - very strong positive
        "    '独占契約': 'A+',\n"
        "    '大型受注': 'A+',\n"
        "    '業績予想 上方修正': 'A+',\n"

        # A rank - strong positive
        "    '筆頭株主変更': 'A',\n"
        "    '黒字転換': 'A',\n"
        "    '新市場参入': 'A',\n"
        "    '新サービス発表': 'A',\n"
        "    '特許取得': 'A',\n"
        "    '新製品発表': 'A',\n"
        "    '事業拡大': 'A',\n"
        "    '買収': 'A',\n"

        # A- rank - technical signals
        "    'ゴールデンクロス': 'A-',\n"
        "    '±３σブレイク': 'A-',\n"
        "    'ボリンジャーバンド上抜け': 'A-',\n"
        "    'fisco注目': 'A-',\n"

        # B rank - moderate positive
        "    '中期経営計画': 'B',\n"
        "    '株式買戻し': 'B',\n"
        "    '特別利益': 'B',\n"
        "    '特別利益計上': 'B',\n"
        "    '株主優待増額': 'B',\n"
        "    '配当増額': 'B',\n"
        "    '販売契約': 'B',\n"
        "    '大量保有報告書': 'B',\n"
        "    'サプライズ決算': 'B',\n"
        "    '四半期サプライズ決算': 'B',\n"
        "    '増益': 'B',\n"
        "    '利益倍増': 'B',\n"
        "    '今期 業績予想 50%増益以上': 'B',\n"

        # C rank - negative or neutral
        "    '施設閉鎖': 'C',\n"
        "    '運営終了': 'C',\n"
        "    '事業報告': 'C',\n"
        "    '株式発行': 'C',\n"
        "    '赤字縮小': 'C',\n"

        # D rank - negative
        "    '減益': 'D',\n"
        "    '赤字転落': 'D',\n"
        "    '資本金変更': 'D',\n"
        "    '再掲IR': 'D',\n"
        "    '過去の材料再加熱': 'D'\n"
        "  }\n"
        "\n"
        "- 🔧 Booster Instruction:\n"
        "  - Define **hot/trending sectors**: AI, Web3, semiconductors, space, quantum computing, medical tech, robotics, FinTech, crypto, mobility, biotech, data centers, EV, hydrogen.\n"
        "  - For certain keywords, **boost to 'S' or 'A+' only if strong value is clear**:\n"
        "    • 'TOB / MBO': Boost to S+ if offer has a large premium, from a notable acquirer, or leads to immediate price gap-up with strong volume.\n"
        "    • '筆頭株主変更': Boost to S if new shareholder is a large institutional investor, foreign fund, or strategic partner.\n"
        "    • '新市場参入': Boost to S only if into a **hot/trending sector** with exclusivity or growth potential.\n"
        "    • '特許取得': Boost to S only if it enables a **monopoly or first-mover advantage in hot/trending fields**.\n"
        "    • '新サービス発表': Boost to S only if it’s a **game-changer or disruptor in hot/trending sectors**.\n"
        "    • '買収': Boost to S only if it’s **accretive, cross-border, or synergistic in hot/trending markets**.\n"
        "    • '中期経営計画': Boost to A+ or S only if plan includes **aggressive growth, global expansion, or restructuring in promising areas**.\n"
        "    • '特別利益': Boost to A+ only if it **significantly improves EPS or changes valuation metrics**.\n"
        "    • '事業拡大': Boost to A+ or S only if it’s into **large-scale, strategic, or hot/trending sectors**.\n"
        "    • '今期 業績予想 50%増益以上': Boost to A+ if forecast is **unexpected, from a low-float/small-cap stock, or paired with strong catalysts**\n"
        "    • '独占契約': Boost to S only if partner is **top-tier or market scale is large**.\n"
        "    • '大型受注': Boost to S only if it’s from a **major client or long-term contract**.\n"
        "    • '黒字転換': Boost to S only if it leads to **sustained profitability or likely leads to strong market reaction**.\n"
        "    • 'サプライズ決算': Boost to S only if it's confirmed that results **exceed expectations significantly**.\n"
        "    • '四半期サプライズ決算': Boost to S only if it's confirmed that **quarterly results strongly surprise**.\n"
        "    • '増益': Boost to S if **profit growth exceeds 50% and is unexpected**, A if **between 30–50% with positive sentiment or low float**.\n"
        "    • '利益倍増': Boost to A if **2倍以上** and supported by **strong catalyst** (e.g. restructuring, new business, or entry into hot/trending sectors).\n"
        "    • 'fisco注目': Boost to A+ if stock already trending or backed by strong catalyst.\n"
        "    • '大量保有報告書': Boost to A if new investor is a known activist fund, foreign investor, or signals strategic interest.\n"

        "### Output Format:\n"
        "Headline List:\n"
        "1. **[Headline text here]**\n"
        "   - **Verdict: [S+, S, A+, A, A-, B, C, D]**\n"
        "   - **Reason: [Keyword - 1 short sentence explaining the expected short-term impact]**\n"
        "(Repeat for each headline)\n\n"
        "News headlines:\n" + "\n".join([f"{i+1}. {hl}" for i, hl in enumerate(raw_headlines)])
    )

    try:
        response = openai.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        reply = response.choices[0].message.content.strip()
        impacts = extract_headline_impacts(reply)

        # Clear old impacts before saving new ones
        db.query(StockNewsImpact).filter_by(ticker=ticker).delete()

        for item in impacts:
            if not item.get("headline") or not item.get("verdict"):
                continue

            matched_news = next(
                (n for n in news_items if n['headline'] in item['headline']), None
            )

            impact = StockNewsImpact(
                ticker=ticker,
                headline=item["headline"],
                verdict=item["verdict"],
                reason=item.get("reason", ""),
                created_at=datetime.utcnow(),
                published_at=matched_news["published_at"] if matched_news else None,
                url=matched_news["url"] if matched_news else None,
            )
            db.add(impact)
        db.commit()

        if any(i["verdict"] in {"S+", "S", "A+", "A", "A-", "B"} for i in impacts):
            print(f"🚨 Positive news detected for {ticker}: {', '.join(i['verdict'] for i in impacts)}")

        return impacts

    except Exception as e:
        print(f"❌ GPT analysis failed for {ticker}: {e}")
        return None

def scan_news_for_low_cap_stocks(db: Session):
    tickers = fetch_low_cap_tickers()
    for ticker in tickers:
        scan_and_analyze_news_for_ticker(db, ticker)

def get_positive_news(db: Session) -> List[dict]:
    positive_verdicts = ["S+", "S", "A+", "A", "A-", "B"]

    # Fetch impacts with positive verdicts
    results = (
        db.query(StockNewsImpact)
        .filter(StockNewsImpact.verdict.in_(positive_verdicts))
        .order_by(StockNewsImpact.published_at.desc())  # or .created_at.desc() if needed
        .all()
    )

    # Fetch starred tickers
    starred_ticker_set = {
        s.ticker for s in db.query(StarredStock.ticker).distinct()
    }

    # Return list of dicts including "starred" field
    return [
        {
            "ticker": r.ticker,
            "headline": r.headline,
            "verdict": r.verdict,
            "reason": r.reason,
            "created_at": r.created_at.isoformat(),
            "published_at": r.published_at.isoformat() if r.published_at else None,
            "url": r.url,
            "starred": r.ticker in starred_ticker_set  # ✅ include starred status
        }
        for r in results
    ]

def get_stock_name(db: Session, ticker: str) -> str:
    snapshot = (
        db.query(VolumeSnapshot)
        .filter_by(ticker=ticker)
        .first()
    )
    if snapshot and snapshot.name:
        return snapshot.name

    # Fallback to Yahoo scrape
    try:
        url = f"https://finance.yahoo.co.jp/quote/{ticker}.T"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "ja,en;q=0.9",
        }
        resp = httpx.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        name_tag = (
            soup.select_one("h2.PriceBoardMain__name__6uDh")
            or soup.select_one("h2.PriceBoard__name__166W")
        )
        return name_tag.text.strip() if name_tag else ticker

    except Exception as e:
        print(f"⚠️ Failed to get name for {ticker}: {e}")
        return ticker
