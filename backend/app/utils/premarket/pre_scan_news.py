from difflib import SequenceMatcher
import os
import hashlib
from typing import List
import openai
from datetime import datetime
from sqlalchemy.orm import Session

from app.models import StockNewsImpact, StarredStock
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

def scan_and_analyze_news_for_ticker(db: Session, ticker: str, top_n: int = 3, days_threshold=10, model: str = "gpt-4o"):
    news_items = scrape_kabutan_news(ticker, limit=30, days_threshold=days_threshold)
    if not news_items:
        return None

    raw_headlines = [f"[{item['category']}] {item['headline']}" for item in news_items[:top_n]]
    recent_headlines = get_recent_headlines(db, ticker)

    # Filter out similar headlines (likely already reacted to)
    filtered_headlines = []
    for hl in raw_headlines:
        if not any(is_similar(hl, past_hl) for past_hl in recent_headlines):
            filtered_headlines.append(hl)

    if not filtered_headlines:
        print(f"🟡 Skipping GPT (too similar to past headlines) for {ticker}")
        return None

    prompt = (
        f"You're a financial analyst evaluating news headlines for Japanese stock {ticker}.\n"
        "- Analyze news to predict **tomorrow's market behavior**.\n"
        "- Evaluate news sentiment and relevance, especially on major themes like AI, Bitcoin, semiconductors, political events.\n"
        "- Evaluate whether the news sentiment is bullish, bearish, or neutral.\n"
        "### Output Format:\n"
        "Headline List:\n"
        "1. **[Headline text here]**\n"
        "   - **Verdict: One of [Decisive, Great, Good, Neutral, Bad]**\n"
        "   - **Reason: 1 concise sentence explaining why**\n"
        "(Repeat for each headline)\n\n"
        "News headlines:\n" + "\n".join([f"{i+1}. {hl}" for i, hl in enumerate(filtered_headlines)])
    )

    try:
        response = openai.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        reply = response.choices[0].message.content.strip()
        impacts = extract_headline_impacts(reply, top_n=top_n)

        # Clear old records for this ticker
        db.query(StockNewsImpact).filter_by(ticker=ticker).delete()

        for item in impacts:
            if not item.get("headline") or not item.get("verdict"):
                continue

            # Find the scraped news matching this headline to get published_at and url
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

        if any(i["verdict"] in {"Decisive", "Great", "Good"} for i in impacts):
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
    positive_verdicts = ["Decisive", "Great", "Good"]

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

