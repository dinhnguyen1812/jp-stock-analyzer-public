import json
import os
import re
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
import openai

from app.utils.shortterm.save_shortterm_analysis_signal import save_shortterm_analysis_signal
from app.utils.shortterm.spike_scanner import compute_price_stats, detect_recent_downtrend
from app.models import DailyPrice, VolumeSnapshot, ShortTermAnalysisSignal, StockNewsImpact

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

    # Get latest short-term signal
    signal: Optional[ShortTermAnalysisSignal] = db.query(ShortTermAnalysisSignal).filter_by(ticker=ticker).first()
    if not signal or not signal.updated_at or (datetime.utcnow() - signal.updated_at) > timedelta(hours=1):
        save_shortterm_analysis_signal(db, ticker)
        signal = db.query(ShortTermAnalysisSignal).filter_by(ticker=ticker).first()

    # Get downtrend info
    downtrend = detect_recent_downtrend(db, ticker)
    downtrend_str = (
        f"📉 Recent Downtrend Detected: {downtrend['drop_pct']}% from {downtrend['from_date']} to {downtrend['to_date']}\n"
        if downtrend.get("had_downtrend") else "📈 No major downtrend in recent 30 days.\n"
    )

    # Get price history stats
    start_date = date.today() - timedelta(days=30)
    prices = (
        db.query(DailyPrice)
        .filter(DailyPrice.ticker == ticker, DailyPrice.date >= start_date)
        .order_by(DailyPrice.date.asc())
        .all()
    )
    price_stats = compute_price_stats(prices, volume_info.current_price)
    price_stats_str = (
        f"📊 Drop from 30-day high: {price_stats['drop_from_high_pct']}%\n"
        f"📈 Rebound from 30-day low: {price_stats['rebound_from_low_pct']}%\n"
        if price_stats["drop_from_high_pct"] is not None else ""
    )

    # Compose GPT prompt
    volume_summary = (
        f"Ticker: {volume_info.ticker}\n"
        f"Name: {volume_info.name}\n"
        f"Current Price: {volume_info.current_price} JPY\n"
        f"Volume Surge: {volume_info.volume_rate}x\n"
        f"Money Flow: {volume_info.money_flow_rate}\n"
        f"Detected At: {volume_info.detected_at.isoformat()}\n"
        + downtrend_str + price_stats_str
    )

    tech_summary = (
        f"RSI: {signal.rsi or 'N/A'}\n"
        f"MACD: {signal.macd_line}/{signal.macd_signal}\n"
        f"Pattern: {signal.candle_pattern or 'N/A'}\n"
    ) if signal else "N/A"

    headlines = [f"[{item['category']}] {item['headline']}" for item in news_items[:top_n]]
    prompt = (
        f"You are a financial analyst providing a **pre-market** outlook for Japanese stock {ticker}.\n\n"
        f"### Volume and Price Activity:\n{volume_summary}\n"
        f"### Technical Indicators (for reference, less emphasis):\n{tech_summary}\n"
        f"### Recent News Headlines:\n"
        + "\n".join([f"{i+1}. {hl}" for i, hl in enumerate(headlines)]) +
        "\n\n### Analysis Instructions:\n"
        "- Focus primarily on volume surge, price movements, and news impact to predict **tomorrow's market behavior**.\n"
        "- Use technical signals as supplementary confirmation.\n"
        "- Identify if the stock is likely to **break out** or have notable movement tomorrow, and why.\n"
        "- Evaluate news sentiment and relevance, especially on major themes like AI, Bitcoin, semiconductors, political events.\n"
        "- Evaluate whether the news sentiment is bullish, bearish, or neutral\n"
        "- Provide a clear recommendation: **Buy**, **Hold**, **Sell**, or **Short**.\n"
        "- Justify your recommendation with 2-3 concise bullet points.\n"
        "- Score the short-term promise from 0 to 100.\n"
        "- Estimate a likely short-term price target.\n"
        "- Based on all factors above, clearly state if the stock should be **added to a pre-market watchlist**. Answer: Yes or No.\n\n"
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

        # Extract fields from GPT reply
        recommendation, promising_score = extract_recommendation_and_score(reply)
        impacts = extract_headline_impacts(reply, top_n=top_n)
        summary_match = re.search(r"Summary:\s*(.*?)\s*(- Investment|$)", reply, re.DOTALL)
        summary = summary_match.group(1).strip() if summary_match else ""

        # Extract Watchlist Recommendation
        watchlist_recommendation = None
        for line in reply.splitlines():
            if "Watchlist Recommendation" in line:
                watchlist_recommendation = line.split(":")[-1].strip()
                break

        # Save results to DB (including published_at and url if available)
        volume_info.reasoning = summary
        volume_info.recommendation = recommendation
        volume_info.promising_score = promising_score
        volume_info.watchlist_recommendation = watchlist_recommendation
        volume_info.top_news = json.dumps(news_items[:top_n], ensure_ascii=False)
        db.commit()

        # Clear old news impact for this ticker
        db.query(StockNewsImpact).filter_by(ticker=ticker).delete()
        for idx, item in enumerate(impacts):
            if not item.get("headline") or not item.get("verdict"):
                continue
            # Try to find corresponding scraped news item for url and published_at
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
            "downtrend": downtrend,
            "drop_from_high_pct": price_stats.get("drop_from_high_pct"),
            "rebound_from_low_pct": price_stats.get("rebound_from_low_pct"),
            "highest_price": price_stats.get("highest_price"),
            "lowest_price": price_stats.get("lowest_price"),
        }

    except Exception as e:
        print(f"❌ GPT error for {ticker}: {e}")
        return {"ticker": ticker, "error": str(e)}

