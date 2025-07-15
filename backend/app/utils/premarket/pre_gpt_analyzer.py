import json
import os
import re
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
import openai

from app.utils.shortterm.save_shortterm_analysis_signal import save_shortterm_analysis_signal
from .calculate_momentum_score import calculate_momentum_score
from .uptrend_detector import get_uptrend_analysis, normalize_uptrend_for_json
from .downtrend_detector import get_downtrend_analysis, normalize_downtrend_for_json
from app.models import DailyPrice, VolumeSnapshot, ShortTermAnalysisSignal, StockNewsImpact
from app.api.shortterm_apis import get_latest_analysis_signal_data

openai.api_key = os.getenv("OPENAI_API_KEY")

def extract_recommendation_and_score(text: str):
    cleaned = re.sub(r"[*#•\-–—●★▶◆]", "", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    rec_match = re.search(r"investment recommendation\s*[:\-]?\s*(buy|sell|hold|short)", cleaned, re.I)
    recommendation = rec_match.group(1).capitalize() if rec_match else "Unknown"
    score_match = re.search(r"promising score\s*[:\-]?\s*(\d{1,3})", cleaned)
    promising_score = int(score_match.group(1)) if score_match else -1
    promising_score = max(0, min(promising_score, 100))
    return recommendation, promising_score


def extract_headline_impacts(text: str, top_n: int = 5) -> list[dict]:
    results = []
    lines = text.splitlines()

    current_headline = None
    verdict = None
    reason = None

    for line in lines:
        line = line.strip()

        # Headline line: number + bold text
        headline_match = re.match(r"^\d+\.\s+\*\*(.+?)\*\*$", line)
        if headline_match:
            # Save previous result if any
            if current_headline and verdict and reason:
                results.append({
                    "headline": current_headline,
                    "verdict": verdict,
                    "reason": reason,
                })
                if len(results) >= top_n:
                    break
            current_headline = headline_match.group(1).strip()
            verdict = None
            reason = None
            continue

        # Verdict line: - **Verdict: ...**
        verdict_match = re.match(r"- \*\*Verdict:\s*(.+?)\*\*", line)
        if verdict_match:
            verdict = verdict_match.group(1).strip()
            continue

        # Reason line: - **Reason: ...**
        reason_match = re.match(r"- \*\*Reason:\s*(.+?)\*\*", line)
        if reason_match:
            reason = reason_match.group(1).strip()
            continue

    # Append the last parsed item if complete
    if current_headline and verdict and reason:
        results.append({
            "headline": current_headline,
            "verdict": verdict,
            "reason": reason,
        })

    return results[:top_n]


def premarket_analyze_with_gpt(
    db: Session,
    ticker: str,
    news_items: List[Dict],
    volume_info: VolumeSnapshot,
    user_prompt: str = "",
    top_n: int = 5,
    model: str = "gpt-4o"
) -> Dict:
    if not news_items:
        return {"ticker": ticker, "volume_info": None, "top_news": [], "gpt_summary": "No recent news available."}
    if not volume_info:
        return {"ticker": ticker, "volume_info": None, "top_news": news_items[:top_n], "gpt_summary": "No volume snapshot."}

    signal: Optional[ShortTermAnalysisSignal] = db.query(ShortTermAnalysisSignal).filter_by(ticker=ticker).first()
    if not signal or not signal.updated_at or (datetime.utcnow() - signal.updated_at) > timedelta(hours=1):
        save_shortterm_analysis_signal(db, ticker)
        signal = db.query(ShortTermAnalysisSignal).filter_by(ticker=ticker).first()

    # ↓↓↓ DOWNTREND ↓↓↓
    downtrend_model = get_downtrend_analysis(db, ticker)
    downtrend_info = normalize_downtrend_for_json(downtrend_model)

    had_downtrend = downtrend_info.get("had_downtrend", False)
    drop_pct = downtrend_info.get("drop_pct", 0)
    from_date = downtrend_info.get("from_date", "?")
    to_date = downtrend_info.get("to_date", "?")
    drop_from_high_pct = downtrend_info.get("drop_from_high_pct")
    rebound_from_low_pct = downtrend_info.get("rebound_from_low_pct")
    highest_price = downtrend_info.get("highest_price")
    lowest_price = downtrend_info.get("lowest_price")

    downtrend_str = (
        f"📉 Recent Downtrend Detected: Dropped {drop_pct:.2f}% from {from_date} to {to_date}.\n"
        if had_downtrend else
        f"📈 No major downtrend in the recent 30 days. Latest range: {from_date} to {to_date}.\n"
    )

    price_stats_str = (
        f"📊 Drop from 30-day high: {drop_from_high_pct}%\n"
        f"📈 Rebound from 30-day low: {rebound_from_low_pct}%\n"
        if drop_from_high_pct is not None else ""
    )

    # ↓↓↓ UPTREND ↓↓↓
    uptrend_model = get_uptrend_analysis(db, ticker)
    uptrend_info = normalize_uptrend_for_json(uptrend_model)
    had_uptrend = uptrend_info.get("had_uptrend", False)
    rise_pct = uptrend_info.get("rise_pct", 0)
    up_from = uptrend_info.get("from_date", "?")
    up_to = uptrend_info.get("to_date", "?")

    uptrend_str = (
        f"📈 Recent Uptrend Detected: Rose {rise_pct:.2f}% from {up_from} to {up_to}.\n"
        if had_uptrend else
        f"📉 No strong uptrend in the recent 30 days. Last low-to-high range: {up_from} to {up_to}.\n"
    )

    volume_summary = (
        f"Ticker: {volume_info.ticker}\n"
        f"Name: {volume_info.name}\n"
        f"Current Price: {volume_info.current_price} JPY\n"
        f"Volume Surge: {volume_info.volume_rate}x\n"
        f"Money Flow: {volume_info.money_flow_rate}\n"
        f"Detected At: {volume_info.detected_at.isoformat()}\n"
        + downtrend_str + uptrend_str + price_stats_str
    )

    tech_summary = (
        f"RSI: {signal.rsi or 'N/A'}\n"
        f"MACD: {signal.macd_line}/{signal.macd_signal}\n"
        f"Pattern: {signal.candle_pattern or 'N/A'}\n"
    ) if signal else "N/A"

    analysis_signal_data = get_latest_analysis_signal_data(db, ticker)

    # ↓↓↓ Fetch recent prices for momentum analysis ↓↓↓
    recent_prices_query = (
        db.query(DailyPrice)
        .filter(DailyPrice.ticker == ticker)
        .order_by(DailyPrice.date.desc())
        .limit(10)
        .all()
    )
    recent_prices = [
        {
            "date": p.date.isoformat(),
            "open": p.open,
            "high": p.high,
            "low": p.low,
            "close": p.close,
        }
        for p in recent_prices_query
    ]

    # ↓↓↓ Momentum Score Calculation ↓↓↓
    momentum_result = calculate_momentum_score(volume_info, analysis_signal_data, recent_prices=recent_prices)
    volume_info.momentum_score = momentum_result["momentum_score"]
    volume_info.momentum_confidence = momentum_result["momentum_confidence"]
    volume_info.momentum_signals = momentum_result["momentum_signals"]

    # ↓↓↓ GPT Prompt ↓↓↓
    headlines = [f"[{item['category']}] {item['headline']}" for item in news_items[:top_n]]

    momentum_summary = (
        f"### Momentum Signals Summary:\n"
        f"Confidence: {momentum_result['momentum_confidence']}\n"
        f"Score: {momentum_result['momentum_score']}/10\n"
        f"Signals:\n" +
        "\n".join([f"- {signal}" for signal in momentum_result['momentum_signals']]) +
        "\n"
    )

    prompt = (
        f"You are a financial analyst providing a **pre-market** outlook for Japanese stock {ticker}.\n\n"
        f"### Volume and Price Activity:\n{volume_summary}\n"
        f"{momentum_summary}"
        f"### Technical Indicators (for reference, less emphasis):\n{tech_summary}\n"
        f"### Recent News Headlines:\n"
        + "\n".join([f"{i+1}. {hl}" for i, hl in enumerate(headlines)]) +
        "\n\n### Analysis Instructions:\n"
        "- Focus primarily on **volume surge**, **momentum signals**, **price movements**, and **news impact** to predict **tomorrow's market behavior**.\n"
        "- Use the **Momentum Signals Summary** as a key factor: if confidence is 'Strong' or score is high, explain what that implies.\n"
        "- If there was a recent **volume surge** or **price spike**, explain **why**. Is it a justified move or based on weak fundamentals/news?\n"
        "- Use technical indicators (RSI, MACD, MA, etc.) as secondary confirmation, not the main basis.\n"
        "- Identify whether the stock is likely to **break out**, remain flat, or decline in the short term — and explain why.\n"
        "- Evaluate the **sentiment and relevance** of the news — especially for themes like AI, Bitcoin, semiconductors, interest rates, or major partnerships.\n"
        "- For each headline, judge whether its impact is **bullish**, **bearish**, or **neutral**, and briefly explain.\n"
        "- Provide a clear recommendation: **Buy**, **Hold**, **Sell**, or **Short**.\n"
        "- Justify your recommendation with **2–3 concise bullet points**.\n"
        "- Give a short-term **Promising Score** from 0 to 100.\n"
        "- Estimate a **likely short-term price target** in JPY.\n"
        "- Based on all factors, clearly state if the stock should be **added to a pre-market watchlist**. Answer: Yes or No.\n\n"
        "### Output Format:\n"
        "Headline List:\n"
        "1. **[Headline text here]**\n"
        "   - **Verdict: One of [Decisive, Great, Good, Neutral, Bad]**\n"
        "   - **Reason: 1 concise sentence explaining why**\n"
        "(Repeat for each headline)\n\n"
        "Summary:\n<Brief analysis focusing on pre-market outlook>\n\n"
        "- Investment Recommendation: Buy / Hold / Sell / Short\n"
        "- Promising Score: (0–100)\n"
        "- Expected Price Target (in JPY): <target price>\n"
        "- Watchlist Recommendation: Yes / No\n"
    )

    try:
        response = openai.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        reply = response.choices[0].message.content.strip()

        recommendation, promising_score = extract_recommendation_and_score(reply)
        impacts = extract_headline_impacts(reply, top_n=top_n)
        summary_match = re.search(r"Summary:\s*(.*?)\s*(- Investment|$)", reply, re.DOTALL)
        summary = summary_match.group(1).strip() if summary_match else ""

        watchlist_recommendation = None
        for line in reply.splitlines():
            if "Watchlist Recommendation" in line:
                watchlist_recommendation = line.split(":")[-1].strip()
                break

        volume_info.reasoning = summary
        volume_info.recommendation = recommendation
        volume_info.promising_score = promising_score
        volume_info.watchlist_recommendation = watchlist_recommendation
        volume_info.top_news = json.dumps(news_items[:top_n], ensure_ascii=False)
        db.commit()

        db.query(StockNewsImpact).filter_by(ticker=ticker).delete()
        for item in impacts:
            if not item.get("headline") or not item.get("verdict"):
                continue
            matched_news = next(
                (n for n in news_items if n["headline"] == item["headline"] or f"[{n['category']}] {n['headline']}" == item["headline"]),
                {}
            )
            published_at = matched_news.get("published_at")
            url = matched_news.get("url")
            impact = StockNewsImpact(
                ticker=ticker,
                headline=item["headline"],
                verdict=item["verdict"],
                reason=item.get("reason", ""),
                created_at=datetime.utcnow(),
                published_at=published_at if published_at else datetime.utcnow(),
                url=url
            )
            db.add(impact)
        db.commit()

        return {
            "ticker": ticker,
            "recommendation": recommendation,
            "score": promising_score,
            "headline_impacts": impacts,
            "summary": summary,
            "gpt_raw_response": reply,
            "downtrend": downtrend_info,
            "uptrend": uptrend_info,
            "drop_from_high_pct": drop_from_high_pct,
            "rebound_from_low_pct": rebound_from_low_pct,
            "highest_price": highest_price,
            "lowest_price": lowest_price,
            "momentum_score": momentum_result["momentum_score"],
            "momentum_confidence": momentum_result["momentum_confidence"],
            "momentum_signals": momentum_result["momentum_signals"],
        }

    except Exception as e:
        print(f"❌ GPT error for {ticker}: {e}")
        return {"ticker": ticker, "error": str(e)}


