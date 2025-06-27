import httpx
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict
import os
import re
import openai
from datetime import datetime, timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session, aliased
from app.models import VolumeSnapshot

openai.api_key = os.getenv("OPENAI_API_KEY")

# Use same or tailored keywords for Kabutan news
KEYWORDS = [
    # Earnings & financial performance
    "決算", "業績", "売上", "増益", "減益", "黒字", "赤字",
    "予想", "上方修正", "下方修正", "利益", "損失", "配当",

    # Corporate events & strategy
    "合併", "提携", "契約", "買収", "子会社", "資本提携", "株式分割",
    "新規上場", "上場廃止", "株主総会", "自社株買い",

    # Products, technology & growth
    "新製品", "成長", "研究開発", "特許", "技術革新", "市場開拓",

    # Market and policy impact
    "規制", "法改正", "補助金", "政策", "助成金", "訴訟", "行政処分",

    # Macro/global factors possibly impacting stocks
    "為替", "インフレ", "金利", "経済指標", "景気", "金融政策", "米中関係",

    # Other important business events
    "役員", "人事", "内部統制", "不祥事", "リストラ", "業務提携"
]

ASK_GPT = True

def relevance_score(headline: str) -> int:
    return sum(1 for kw in KEYWORDS if kw in headline)

def scrape_kabutan_news(ticker: str, limit: int = 30) -> List[Dict]:
    url = f"https://kabutan.jp/stock/news?code={ticker}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "ja,en;q=0.9"
    }

    try:
        resp = httpx.get(url, headers=headers, timeout=10)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        news_table = soup.find("table", class_="s_news_list mgbt0")
        if not news_table:
            print("❌ Could not find news table on Kabutan page")
            return []

        news_items = []
        rows = news_table.find_all("tr")

        for row in rows:
            time_td = row.find("td", class_="news_time")
            if not time_td:
                continue
            time_tag = time_td.find("time")
            if not time_tag or not time_tag.has_attr("datetime"):
                continue

            published_at = time_tag["datetime"]  # ISO 8601 format, e.g. 2025-06-25T17:00:03+09:00

            # category is in second td, inside div.newslist_ctg
            category_td = time_td.find_next_sibling("td")
            category_div = category_td.find("div", class_="newslist_ctg") if category_td else None
            category = category_div.text.strip() if category_div else None

            # headline and url in third td with <a>
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

            score = relevance_score(headline)

            news_items.append({
                "published_at": published_at,
                "category": category,
                "headline": headline,
                "url": href,
                "score": score
            })

            if len(news_items) >= limit:
                break

        # Sort news by relevance score desc, then published_at desc
        news_items.sort(key=lambda x: (x["score"], x["published_at"]), reverse=True)

        return news_items

    except Exception as e:
        print(f"❌ Error scraping Kabutan news: {e}")
        return []

import json

def analyze_stock_surge_with_news(
    db: Session,
    ticker: str,
    news_items: List[Dict],
    user_prompt: str = "",
    top_n: int = 5,
    model: str = "gpt-4o"
) -> Dict:
    if not news_items or not openai.api_key:
        return {
            "ticker": ticker,
            "volume_info": None,
            "top_news": news_items[:top_n],
            "gpt_summary": "News or OpenAI API not available."
        }

    since = datetime.utcnow() - timedelta(hours=24)

    subquery = (
        db.query(
            VolumeSnapshot.ticker,
            func.max(VolumeSnapshot.detected_at).label("latest_time")
        )
        .filter(VolumeSnapshot.detected_at >= since)
        .group_by(VolumeSnapshot.ticker)
        .subquery()
    )

    VS = aliased(VolumeSnapshot)
    volume_info = (
        db.query(VS)
        .join(subquery, (VS.ticker == subquery.c.ticker) & (VS.detected_at == subquery.c.latest_time))
        .filter(VS.ticker == ticker)
        .first()
    )

    if not volume_info:
        return {
            "ticker": ticker,
            "volume_info": None,
            "top_news": [],
            "gpt_summary": f"Ticker {ticker} does not have recent volume surge data."
        }

    volume_summary = (
        f"Ticker: {volume_info.ticker}\n"
        f"Name: {volume_info.name}\n"
        f"Current Price: {volume_info.current_price} JPY\n"
        f"Price Change: {volume_info.price_change}%\n"
        f"Volume Surge: {volume_info.volume_rate}x\n"
        f"Estimated Money Flow: {volume_info.money_flow_rate} B JPY\n"
        f"Current Volume: {volume_info.current_volume}\n"
        f"5-Day Avg Volume: {volume_info.avg_volume_5d}\n"
        f"Detected At: {volume_info.detected_at.isoformat()}"
    )

    headlines = [item["headline"] for item in news_items]

    prompt = (
        f"You are a financial assistant analyzing trading activity of Japanese stock {ticker}.\n"
        f"Here is the recent volume/price activity:\n{volume_summary}\n\n"
        f"And here are recent news headlines. \n"
        "Summarize why this stock is experiencing a volume surge and recent news impact. "
        "Then, give a clear investment recommendation: buy, hold, or sell. "
        "Explain your recommendation with key risks and potential rewards. \n\n"
        + "\n".join([f"{i+1}. {hl}" for i, hl in enumerate(headlines)]) +
        f"\n\nReturn the top {top_n} most relevant headlines, followed by a short paragraph summarizing the likely reason for the volume surge. "
        f"Format:\n\nHeadline List:\n1. ...\n2. ...\n\nSummary:\n..."
        "At the end, give:"
        "- Investment Recommendation: Buy / Hold / Sell"
        "- Promising Score: (0–100, based on growth potential)"
    )

    try:
        response = openai.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )

        reply = response.choices[0].message.content.strip()

        headline_lines = []
        summary_lines = []
        in_summary = False

        for line in reply.split("\n"):
            if "summary:" in line.lower():
                in_summary = True
                continue
            if in_summary:
                summary_lines.append(line.strip())
            else:
                headline_lines.append(line.strip("1234567890. ").strip())

        selected_items = []
        for h in headline_lines:
            match = next((item for item in news_items if h in item["headline"]), None)
            if match and match not in selected_items:
                selected_items.append(match)
            if len(selected_items) >= top_n:
                break

        recommendation, promising_score = extract_recommendation_and_score(reply)

        if volume_info:
            volume_info.reasoning = "\n".join(summary_lines).strip() or "(No summary returned)"
            volume_info.recommendation = recommendation or "Unknown"
            volume_info.promising_score = promising_score if promising_score is not None else -1
            
            # Save top news JSON string
            volume_info.top_news_json = json.dumps(selected_items, ensure_ascii=False)
            
            db.commit()

        return {
            "ticker": ticker,
            "volume_info": {
                "ticker": volume_info.ticker,
                "name": volume_info.name,
                "current_price": volume_info.current_price,
                "price_change": volume_info.price_change,
                "volume_rate": volume_info.volume_rate,
                "money_flow_rate": volume_info.money_flow_rate,
                "current_volume": volume_info.current_volume,
                "avg_volume_5d": volume_info.avg_volume_5d,
                "detected_at": volume_info.detected_at.isoformat(),
                "reasoning": volume_info.reasoning,
                "recommendation": volume_info.recommendation,
                "promising_score": volume_info.promising_score,
                "top_news_json": volume_info.top_news_json,
            },
            "top_news": selected_items or news_items[:top_n],
        }

    except Exception as e:
        print(f"❌ GPT analysis failed: {e}")
        return {
            "ticker": ticker,
            "volume_info": volume_summary,
            "top_news": news_items[:top_n],
            "gpt_summary": "GPT call failed."
        }

def extract_recommendation_and_score(text: str):
    # Remove markdown symbols (e.g., "**", "###", "-", etc.)
    cleaned = re.sub(r"[*#•\-–—●★▶◆]", "", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()

    # Match recommendation
    rec_match = re.search(r"investment recommendation\s*[:\-]?\s*(buy|sell|hold)", cleaned, re.I)
    recommendation = rec_match.group(1).capitalize() if rec_match else "Unknown"

    # Match promising score
    score_match = re.search(r"promising score\s*[:\-]?\s*(\d{1,3})", cleaned)
    promising_score = int(score_match.group(1)) if score_match else -1
    promising_score = max(0, min(promising_score, 100))  # Clamp to [0, 100]

    return recommendation, promising_score