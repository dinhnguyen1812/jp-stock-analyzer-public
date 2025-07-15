import httpx
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List, Dict
import os
import re
import json
import openai
import difflib
from sqlalchemy import func
from sqlalchemy.orm import Session, aliased
from app.models import VolumeSnapshot, ShortTermAnalysisSignal
from app.utils.shortterm.save_shortterm_analysis_signal import save_shortterm_analysis_signal

openai.api_key = os.getenv("OPENAI_API_KEY")

KEYWORDS = [
    "決算", "業績", "売上", "増益", "減益", "黒字", "赤字",
    "予想", "上方修正", "下方修正", "利益", "損失", "配当",
    "合併", "提携", "契約", "買収", "子会社", "資本提携", "株式分割",
    "新規上場", "上場廃止", "株主総会", "自社株買い",
    "新製品", "成長", "研究開発", "特許", "技術革新", "市場開拓",
    "規制", "法改正", "補助金", "政策", "助成金", "訴訟", "行政処分",
    "為替", "インフレ", "金利", "経済指標", "景気", "金融政策", "米中関係",
    "役員", "人事", "内部統制", "不祥事", "リストラ", "業務提携"
]

def relevance_score(headline: str) -> int:
    return sum(1 for kw in KEYWORDS if kw in headline)

def scrape_kabutan_news(ticker: str, limit: int = 30, days_threshold: int = 30) -> List[Dict]:
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

            published_at = time_tag["datetime"]

            # ✅ Skip news older than 30 days
            try:
                published_dt = datetime.fromisoformat(published_at)
            except ValueError:
                continue
            now = datetime.now(tz=published_dt.tzinfo)
            if published_dt < now - timedelta(days=days_threshold):
                continue

            category_td = time_td.find_next_sibling("td")
            category_div = category_td.find("div", class_="newslist_ctg") if category_td else None
            category = category_div.text.strip() if category_div else None

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

        news_items.sort(key=lambda x: (x["score"], x["published_at"]), reverse=True)
        return news_items

    except Exception as e:
        print(f"❌ Error scraping Kabutan news: {e}")
        return []

def get_volume_info(db: Session, ticker: str):
    subquery = (
        db.query(
            VolumeSnapshot.ticker,
            func.max(VolumeSnapshot.detected_at).label("latest_time")
        )
        .group_by(VolumeSnapshot.ticker)
        .subquery()
    )

    VS = aliased(VolumeSnapshot)
    return (
        db.query(VS)
        .join(subquery, (VS.ticker == subquery.c.ticker) & (VS.detected_at == subquery.c.latest_time))
        .filter(VS.ticker == ticker)
        .first()
    )


def analyze_stock_surge_with_news(
    db: Session,
    ticker: str,
    news_items: List[Dict],
    volume_info: VolumeSnapshot,
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

    signal = db.query(ShortTermAnalysisSignal).filter_by(ticker=ticker).first()
    should_update = (
        not signal
        or not signal.updated_at
        or (datetime.utcnow() - signal.updated_at) > timedelta(hours=1)
    )

    if should_update:
        print(f"🔄 Refreshing technical signal for {ticker} (missing or older than 1 hour)...")
        save_shortterm_analysis_signal(db, ticker)
        signal = db.query(ShortTermAnalysisSignal).filter_by(ticker=ticker).first()

    if not volume_info or not signal:
        return {
            "ticker": ticker,
            "volume_info": None,
            "top_news": [],
            "gpt_summary": f"Missing volume or analysis signal data for {ticker}."
        }

    volume_summary = (
        f"Ticker: {volume_info.ticker}\n"
        f"Name: {volume_info.name}\n"
        f"Current Price: {volume_info.current_price} JPY\n"
        f"Price Change: {volume_info.price_change}%\n"
        f"Volume Surge: {volume_info.volume_rate}x\n"
        f"Estimated Money Flow: {volume_info.money_flow_rate}\n"
        f"Current Volume: {volume_info.current_volume} 株\n"
        f"5-Day Avg Volume: {volume_info.avg_volume_5d} 株\n"
        f"Detected At: {volume_info.detected_at.isoformat()}\n"
    )

    tech_summary = (
        f"RSI: {signal.rsi if signal.rsi is not None else 'N/A'}\n"
        f"MACD: line={signal.macd_line if signal.macd_line is not None else 'N/A'}, "
        f"signal={signal.macd_signal if signal.macd_signal is not None else 'N/A'}, "
        f"hist={signal.macd_hist if signal.macd_hist is not None else 'N/A'}\n"
        f"BBands: upper={signal.bb_upper if signal.bb_upper is not None else 'N/A'}, "
        f"middle={signal.bb_middle if signal.bb_middle is not None else 'N/A'}, "
        f"lower={signal.bb_lower if signal.bb_lower is not None else 'N/A'}, "
        f"price={signal.bb_current_price if signal.bb_current_price is not None else 'N/A'}\n"
        f"MA: SMA50={signal.sma_50 if signal.sma_50 is not None else 'N/A'}, "
        f"SMA200={signal.sma_200 if signal.sma_200 is not None else 'N/A'}, "
        f"EMA20={signal.ema_20 if signal.ema_20 is not None else 'N/A'}, "
        f"crossover={signal.sma_crossover or 'N/A'}\n"
    )

    pattern_summary = (
        f"Candle Pattern: {signal.candle_pattern or 'None'}\n"
        f"Breakout: {signal.breakout_detected}, Resistance: {signal.resistance_level if signal.resistance_level is not None else 'N/A'}, "
        f"Close: {signal.close_today if signal.close_today is not None else 'N/A'}\n"
        f"W-Shape: {signal.w_shape}, Flags/Pennants: {signal.flags_pennants}, Triangle: {signal.triangle}\n"
    )

    headlines = [f"[{item['category']}] {item['headline']}" for item in news_items]

    prompt = (
        f"You are a financial analyst evaluating the recent trading activity of Japanese stock {ticker}.\n\n"
        f"### Volume Activity:\n{volume_summary}\n"
        f"### Technical Indicators:\n{tech_summary}\n"
        f"### Pattern Signals:\n{pattern_summary}\n"
        f"### Relevant News (Headline + Category):\n"
        + "\n".join([f"{i+1}. {hl}" for i, hl in enumerate(headlines)]) +
        "\n\n### Task:\n"
        "- Prioritize your analysis based on the following importance:\n"
        "  1. **Volume surge** (volume_rate, money_flow_rate)\n"
        "  2. **News headlines** — do news influence short-term movement\n"
        "  3. **Price breakout and support/resistance levels** (breakout_detected, resistance_level, close_today)\n"
        "  4. **Chart patterns** such as W-shape, flags/pennants, or triangle formations\n"
        "  5. **Momentum indicators** like RSI and MACD — use these as supportive, not decisive\n"
        "  6. **Trend indicators** like SMA/EMA — use for additional context\n"
        "- Pay special attention to news related to major market themes such as **Bitcoin**, **AI**, **semiconductors**, and macro-political events like **wars**, **tariffs**, **elections**, or statements by influential figures (e.g., **Trump**), as these can significantly impact certain stocks.\n"
        "- Focus on explaining recent price and volume movements based on the above priorities\n"
        # "- Use relevant news to support or challenge the technical signals, but do not rely on news alone\n"
        "- Evaluate whether the news sentiment is bullish, bearish, or neutral\n"
        "- Provide an investment recommendation: **Buy**, **Hold**, **Sell**, or **Short**\n"
        "- Justify your recommendation in clear and concise bullet points (2–3 max)\n"
        "- Score the stock's short-term promise from 0–100, based on risk/reward and likelihood of sustained move\n"
        "- Estimate a short-term price target based on the analysis\n\n"
        "### Output Format:\n"
        "Headline List:\n1. ...\n2. ...\n\n"
        "Summary:\n<Brief analysis paragraph>\n\n"
        "- Investment Recommendation: Buy / Hold / Sell / Short\n"
        "- Promising Score: (0–100)\n"
        "- Expected Price Target (in JPY): <target price>"
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
            h_clean = re.sub(r"^\[[^\]]+\]\s*", "", h)
            matches = difflib.get_close_matches(h_clean, [item["headline"] for item in news_items], n=1, cutoff=0.5)
            if matches:
                match_obj = next((item for item in news_items if item["headline"] == matches[0]), None)
                if match_obj and match_obj not in selected_items:
                    selected_items.append(match_obj)
            if len(selected_items) >= top_n:
                break

        recommendation, promising_score = extract_recommendation_and_score(reply)

        volume_info.reasoning = "\n".join(summary_lines).strip() or "(No summary returned)"
        volume_info.recommendation = recommendation or "Unknown"
        volume_info.promising_score = promising_score if promising_score is not None else -1
        volume_info.top_news = json.dumps(selected_items, ensure_ascii=False)

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
                "top_news": volume_info.top_news,
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
    cleaned = re.sub(r"[*#•\-–—●★▶◆]", "", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    rec_match = re.search(r"investment recommendation\s*[:\-]?\s*(buy|sell|hold|short)", cleaned, re.I)
    recommendation = rec_match.group(1).capitalize() if rec_match else "Unknown"
    score_match = re.search(r"promising score\s*[:\-]?\s*(\d{1,3})", cleaned)
    promising_score = int(score_match.group(1)) if score_match else -1
    promising_score = max(0, min(promising_score, 100))
    return recommendation, promising_score

