import httpx
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict
import os
import openai

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

def ask_gpt_to_get_relevant_news(news_items: List[Dict], ticker: str, top_n: int = 5, model: str = "gpt-3.5-turbo") -> List[Dict]:
    if not news_items or not openai.api_key:
        return news_items[:top_n]

    headlines = [item["headline"] for item in news_items]

    prompt = (
        f"You are an AI assistant analyzing stock news for the Japanese company that has ticker: {ticker}.\n"
        f"Below are recent news headlines. Your task is to select the {top_n} most relevant news headlines "
        f"that could potentially impact the company's stock price, even if the company name is not directly mentioned. "
        f"Consider earnings, product announcements, industry-wide developments, macroeconomic changes, and other impactful topics.\n\n"
        + "\n".join([f"{i+1}. {headline}" for i, headline in enumerate(headlines)]) +
        "\n\nReturn the list of the most relevant headlines in their original wording. Do not include explanations."
    )

    try:
        response = openai.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        reply = response.choices[0].message.content.strip()

        # Extract selected headlines (assumes GPT returns numbered list)
        selected_lines = [
            line.strip("1234567890. ").strip()
            for line in reply.split("\n") if line.strip()
        ]

        # Match selected lines to original items
        selected_items = []
        for selected_headline in selected_lines:
            match = next((item for item in news_items if selected_headline in item["headline"]), None)
            if match and match not in selected_items:
                selected_items.append(match)
            if len(selected_items) >= top_n:
                break

        return selected_items or news_items[:top_n]

    except Exception as e:
        print(f"❌ GPT news relevance filtering failed: {e}")
        return news_items[:top_n]

def get_relevant_kabutan_news(ticker: str) -> List[Dict]:
    news = scrape_kabutan_news(ticker)
    return ask_gpt_to_get_relevant_news(news, ticker)
