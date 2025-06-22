import httpx
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict
import os
import openai

# Optional: Set your OpenAI API key via environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")

# Keywords indicating news that might affect stock price
KEYWORDS = [
    "決算", "業績", "売上", "増益", "減益", "黒字", "赤字",
    "予想", "上方修正", "下方修正", "配当", "新製品", "成長"
]

ASK_GPT = True

def relevance_score(headline: str) -> int:
    return sum(1 for kw in KEYWORDS if kw in headline)

def scrape_yahoo_news(ticker: str, limit: int = 50) -> List[Dict]:
    url = f"https://finance.yahoo.co.jp/quote/{ticker}.T/news"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept-Language": "ja,en;q=0.9"
    }

    try:
        resp = httpx.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        a_tags = soup.find_all("a")

        article_links = [
            a for a in a_tags
            if "/news/" in a.get("href", "") and a.get_text(strip=True)
        ]

        news_items = []
        seen_urls = set()

        for a_tag in article_links:
            headline = a_tag.get_text(strip=True)
            url = a_tag["href"]
            if not url.startswith("http"):
                url = f"https://finance.yahoo.co.jp{url}"

            if url in seen_urls:
                continue
            seen_urls.add(url)

            score = relevance_score(headline)

            news_items.append({
                "headline": headline,
                "url": url,
                "published_at": datetime.now().isoformat(),
                "score": score
            })

            if len(news_items) >= limit:
                break

        if ASK_GPT:
            return news_items

        # Sort by score (descending)
        news_items.sort(key=lambda x: x["score"], reverse=True)
        return news_items

    except Exception as e:
        print(f"❌ Error scraping Yahoo Finance News for {ticker}: {e}")
        return []

def rerank_news_with_gpt(news_items: List[Dict], ticker: str, top_n: int = 5, model = "gpt-3.5-turbo") -> List[Dict]:
    if not news_items or not openai.api_key:
        return news_items[:top_n]  # fallback if GPT can't be used

    headlines = [item["headline"] for item in news_items]

    prompt = (
        f"The following are recent news headlines about company that has ticker: {ticker}. "
        f"Please select the {top_n} most relevant headlines that are likely to affect the company's stock price, "
        f"especially based on earnings, performance, forecasts, dividends, or market-moving events.\n\n"
        + "\n".join(f"{i+1}. {hl}" for i, hl in enumerate(headlines)) +
        f"\n\nReturn a list of the most relevant headlines in original form."
    )

    try:
        response = openai.ChatCompletion.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        selected_text = response["choices"][0]["message"]["content"]
        selected_headlines = [line.strip("1234567890. ").strip() for line in selected_text.strip().split("\n") if line.strip()]
        
        # Match selected headlines back to original news_items
        selected = []
        for h in selected_headlines:
            match = next((item for item in news_items if h in item["headline"]), None)
            if match and match not in selected:
                selected.append(match)
            if len(selected) >= top_n:
                break

        return selected or news_items[:top_n]

    except Exception as e:
        print(f"❌ GPT reranking failed: {e}")
        return news_items[:top_n]


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


def get_relevant_news(ticker: str) -> List[Dict]:
    news = scrape_yahoo_news(ticker)
    return ask_gpt_to_get_relevant_news(news, ticker)