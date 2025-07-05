import httpx
from fastapi import HTTPException
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict, Optional
import os
import openai

from app.models import StarredStock
from sqlalchemy.orm import Session

openai.api_key = os.getenv("OPENAI_API_KEY")

KEYWORDS = [
    # Economic / Macro
    "経済指標", "消費", "投資", "財政", "金融市場", "利益率", "債券", "インフレ率", "失業", 
    "景気後退", "景気回復", "景気", "政策", "金融政策", "利上げ", "利下げ", "日銀", "政府",

    # Geopolitical / Global Events
    "政治", "選挙", "米国", "中国", "欧州", "制裁", "貿易戦争", "地政学", "紛争", "戦争", 
    "サイバー攻撃", "パンデミック", "COVID", "トランプ", "ビットコイン", "仮想通貨",

    # Industry / Tech Trends
    "テクノロジー", "AI", "人工知能", "自動運転", "5G", "クリーンエネルギー", "再生可能エネルギー", 
    "半導体", "バイオテクノロジー", "新技術",

    # Financial Market Terms
    "株式市場", "投資家", "リスク", "ボラティリティ", "配当", "上場", "IPO", "資本市場", "資金調達",

    # Social / Regulatory / Environmental
    "ESG", "気候変動", "労働市場", "消費者信頼感", "規制", "法律", "法案", "合併", "提携", "契約",

    # Energy / Commodities / Others
    "原油", "エネルギー", "資源", "気象", "災害"
]

def relevance_score(headline: str) -> int:
    return sum(1 for kw in KEYWORDS if kw in headline)

def add_keyword_scores(news_items: List[Dict]) -> List[Dict]:
    for item in news_items:
        headline = item.get("headline", "")
        item["score"] = relevance_score(headline)
    return news_items

def scrape_yahoo_general_market_news(limit_per_category: int = 10, categories: Optional[List[str]] = None) -> List[Dict]:
    url = "https://finance.yahoo.co.jp/news?category=market"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept-Language": "ja,en;q=0.9"
    }

    try:
        resp = httpx.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        news_results = []
        category_blocks = soup.find_all("div", class_="categoryList__1ZhP")
        for block in category_blocks:
            h2 = block.find("h2", class_="headline02__1Uds")
            if not h2:
                continue
            category_name = h2.text.strip()

            if categories and category_name not in categories:
                continue

            ul = block.find("ul", class_="container__2U3C")
            if not ul:
                continue

            count = 0
            for li in ul.find_all("li", recursive=False):
                if "ad__" in li.get("class", []):
                    continue
                a = li.find("a")
                if not a:
                    continue

                url = a.get("href")
                if url and not url.startswith("http"):
                    url = f"https://finance.yahoo.co.jp{url}"

                headline_span = a.find("span", class_="title__36K6")
                headline = headline_span.text.strip() if headline_span else None
                if not headline:
                    continue

                spans = a.find_all("span", class_="subData__1gx5")
                source_span = spans[1] if len(spans) > 1 else None
                source = source_span.text.strip() if source_span else None

                summary_span = a.find("span", class_="summary__3UZ7")
                summary = summary_span.text.strip() if summary_span else None

                news_results.append({
                    "category": category_name,
                    "headline": headline,
                    "url": url,
                    "source": source,
                    "summary": summary,
                    "published_at": datetime.now().isoformat()
                })

                count += 1
                if count >= limit_per_category:
                    break

        news_results = add_keyword_scores(news_results)
        return news_results

    except Exception as e:
        print(f"❌ Error scraping Yahoo Finance general news: {e}")
        return []

def analyze_news_and_starred_stocks_with_gpt(news_items: List[Dict], starred_stocks: List[StarredStock], top_n: int = 10, model: str = "gpt-4o") -> Dict:
    if not news_items or not openai.api_key:
        return {"top_news": news_items[:top_n], "stock_impacts": []}

    headlines = [item["headline"] for item in news_items]

    prompt = (
        "You are a financial analyst. Given the following recent Japanese finance news headlines and a list of Japanese stocks,"
        " identify the most impactful news items for the market and evaluate potential impact on each stock.\n\n"
        "News Headlines:\n"
        + "\n".join([f"{i+1}. {headline}" for i, headline in enumerate(headlines)]) +
        "\n\nStarred Stocks:\n"
        + "\n".join([f"- {s.ticker}" for s in starred_stocks]) +
        "\n\nTasks:\n"
        "1. Rank the top 10 most impactful headlines for the Japanese market.\n"
        "2. For each starred stock, indicate:\n"
        "   - Whether any headlines may impact it\n"
        "   - The estimated impact (Positive / Negative / Neutral)\n"
        "   - A brief reason\n\n"
        "Output Format:\n"
        "Top News:\n1. ...\n2. ...\n\n"
        "Stock Impact:\nTicker: XXXX\nImpact: Positive\nReason: ...\n"
    )

    try:
        response = openai.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )
        reply = response.choices[0].message.content.strip()
        return {"raw_response": reply}  # optionally parse later
    except Exception as e:
        print(f"❌ GPT analysis failed: {e}")
        return {"top_news": news_items[:top_n], "stock_impacts": []}

def fetch_news_signals_with_stock_impacts(db: Session, limit_per_category: int = 10, top_n: int = 10) -> Dict:
    try:
        news_items = scrape_yahoo_general_market_news(limit_per_category=limit_per_category)
        if not news_items:
            raise ValueError("Failed to fetch market news.")

        starred_stocks = db.query(StarredStock).all()
        result = analyze_news_and_starred_stocks_with_gpt(news_items, starred_stocks, top_n=top_n)

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching news + stock analysis: {e}")
