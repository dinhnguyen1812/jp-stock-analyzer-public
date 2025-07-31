import os
import httpx
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.models import StockNewsImpact
from app.utils.openai_helpers import analyze_news_headline  # ← A wrapper for GPT call
from app.database import SessionLocal

KABUTAN_NEWS_URL = "https://kabutan.jp/news/"

def fetch_today_kabutan_news() -> list[dict]:
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "ja,en;q=0.9",
    }

    resp = httpx.get(KABUTAN_NEWS_URL, headers=headers, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    today = datetime.now(timezone(timedelta(hours=9))).date()
    results = []

    rows = soup.select("table.newsTable tr")
    for row in rows:
        time_tag = row.select_one("td.news_time")
        title_tag = row.select_one("td.news_title > a")
        ticker_tag = row.select_one("td.news_title span.txt_gray")

        if not (time_tag and title_tag and ticker_tag):
            continue

        time_text = time_tag.text.strip()
        if ":" not in time_text:
            continue  # skip non-today news

        # Build full timestamp
        hour, minute = map(int, time_text.split(":"))
        published_at = datetime(today.year, today.month, today.day, hour, minute, tzinfo=timezone(timedelta(hours=9)))

        # Extract data
        headline = title_tag.text.strip()
        url = "https://kabutan.jp" + title_tag["href"]
        ticker = ticker_tag.text.strip().replace("[", "").replace("]", "")[:4]

        results.append({
            "ticker": ticker,
            "headline": headline,
            "url": url,
            "published_at": published_at
        })

    return results


def already_saved(db: Session, ticker: str, headline: str) -> bool:
    existing = db.query(StockNewsImpact).filter_by(ticker=ticker).order_by(StockNewsImpact.created_at.desc()).limit(5).all()
    return any(h.headline.strip() == headline.strip() for h in existing)


def scan_intraday_news(db: Session):
    news_items = fetch_today_kabutan_news()
    print(f"📰 Found {len(news_items)} news items today.")

    for item in news_items:
        ticker = item["ticker"]
        headline = item["headline"]

        if already_saved(db, ticker, headline):
            continue

        verdict, reason = analyze_news_headline(ticker=ticker, headline=headline)

        news_record = StockNewsImpact(
            ticker=ticker,
            headline=headline,
            verdict=verdict,
            reason=reason,
            created_at=datetime.utcnow(),
            published_at=item["published_at"],
            url=item["url"],
        )
        db.add(news_record)
        db.commit()

        if verdict in {"Decisive", "Great", "Good"}:
            print(f"🚨 [{verdict}] {ticker} - {headline} | Reason: {reason}")

def analyze_news_headline(ticker: str, headline: str, model="gpt-4o") -> tuple[str, str]:
    import openai
    openai.api_key = os.getenv("OPENAI_API_KEY")

    prompt = (
        f"Evaluate this Japanese stock news headline for {ticker}:\n"
        f"'{headline}'\n\n"
        "Return a verdict (Decisive, Great, Good, Neutral, Bad) and a brief reason."
    )

    try:
        response = openai.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        text = response.choices[0].message.content.strip()
        verdict = None
        reason = ""

        for line in text.splitlines():
            if "Verdict" in line:
                verdict = line.split(":")[1].strip()
            elif "Reason" in line:
                reason = line.split(":")[1].strip()

        return verdict or "Neutral", reason
    except Exception as e:
        print(f"❌ GPT error for {ticker}: {e}")
        return "Neutral", "Could not evaluate"
