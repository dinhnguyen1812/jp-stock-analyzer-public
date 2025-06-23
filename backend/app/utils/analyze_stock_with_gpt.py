import os
import json
import openai
from typing import List, Dict, Optional

# Import your utilities to fetch data
from app.utils.yahoo_indicators import fetch_current_indicators
from app.utils.news_scraper import get_relevant_news
from app.utils.jpx_perpbr_industry import update_and_get_industry_indicators
from app.utils.jpx_perpbr_history import update_and_get_historical_indicators

openai.api_key = os.getenv("OPENAI_API_KEY")

def build_prompt(
    ticker: str,
    stock_data: Dict,
    industry_data: Optional[Dict],
    news_items: List[Dict],
    historical_data: List[Dict],
) -> str:
    if industry_data:
        industry_info = industry_data[0]
        industry_name = industry_info.get("industry", "N/A")
        industry_per = industry_info.get("per", "N/A")
        industry_pbr = industry_info.get("pbr", "N/A")
        industry_roe = industry_info.get("roe", "N/A")
    else:
        industry_name = industry_per = industry_pbr = industry_roe = "N/A"

    # Format historical data as JSON string (abbreviate for prompt length)
    hist_str = json.dumps(historical_data, indent=2, ensure_ascii=False)

    news_str = "\n".join(
        [f"- {item['headline']} ({item['published_at']})" for item in news_items]
    ) or "No recent news."

    prompt = f"""
You are a professional Japanese stock market analyst. Given the following information about the stock {ticker} ({stock_data.get('name', '')}), provide:

1. A concise summary of the company's financial health and recent performance.
2. An assessment of the stock's valuation relative to industry averages.
3. A sentiment rating: Bullish, Neutral, or Bearish, with reasoning.
4. An outlook on EPS growth potential based on recent news.
5. Provide the expected stock price.

Stock Data:
- Current Price: ¥{stock_data.get('current_price', 'N/A')}
- Market: {stock_data.get('market', 'N/A')}
- Industry: {industry_name}
- PER: {stock_data.get('per', 'N/A')}
- PBR: {stock_data.get('pbr', 'N/A')}
- EPS: {stock_data.get('eps', 'N/A')}
- BPS: {stock_data.get('bps', 'N/A')}
- ROE: {stock_data.get('roe', 'N/A')}
- Dividend Yield: {stock_data.get('dividend_yield', 'N/A')}%
- Debt Ratio: {stock_data.get('debt_ratio', 'N/A')}%
- Market Cap: ¥{stock_data.get('market_cap', 'N/A')}

Industry Averages:
- PER: {industry_per}
- PBR: {industry_pbr}
- ROE: {industry_roe}

Historical Indicators (Last 12 months):
{hist_str}

Recent News Headlines:
{news_str}

Provide your response in JSON format with keys: summary, sentiment, eps_outlook.
"""
    return prompt


def ask_gpt_for_analysis(prompt: str, model="gpt-4o") -> Dict:
    client = openai.OpenAI()

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a helpful stock analyst."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=1000,
    )

    content = response.choices[0].message.content
    try:
        # Expect JSON formatted string from GPT
        return json.loads(content)
    except Exception:
        # Optional fallback if it's not valid JSON
        import re
        json_match = re.search(r"{.*}", content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except:
                pass
        return {"summary": content, "sentiment": "Unknown", "eps_outlook": "N/A"}


def analyze_stock_with_gpt(ticker: str, db) -> Dict:
    # 1. Fetch stock realtime indicators
    stock_data = fetch_current_indicators(ticker)
    if not stock_data:
        raise ValueError(f"Could not fetch indicators for {ticker}")

    # 2. Fetch industry averages from DB
    industry_name = stock_data.get("industry", "")
    industry_data = update_and_get_industry_indicators(industry_name, db)

    # 3. Fetch recent relevant news
    news_items = get_relevant_news(ticker)

    # 4. Fetch historical indicators (limit 12 months)
    historical_models = update_and_get_historical_indicators(ticker, db)[:12]
    historical_data = [
        {
            "date": h.date.isoformat(),
            "per": float(h.per) if h.per is not None else None,
            "pbr": float(h.pbr) if h.pbr is not None else None
        }
        for h in historical_models
    ]

    # 5. Build prompt and query GPT
    prompt = build_prompt(ticker, stock_data, industry_data, news_items, historical_data)
    analysis = ask_gpt_for_analysis(prompt)

    # 6. Return combined result
    return {
        "summary": analysis.get("summary", ""),
        "sentiment": analysis.get("sentiment", ""),
        "eps_outlook": analysis.get("eps_outlook", ""),
        "stock_data": stock_data,
        "industry_data": industry_data,
        "news": news_items,
        "historical": historical_data,
    }
