from difflib import get_close_matches
import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
import openai

from app.utils.shortterm.price_updater import fetch_and_save_price_history
from app.utils.shortterm.save_shortterm_analysis_signal import save_shortterm_analysis_signal
from .calculate_momentum_score import calculate_momentum_score
from .uptrend_detector import get_uptrend_analysis, normalize_uptrend_for_json
from .downtrend_detector import get_downtrend_analysis, normalize_downtrend_for_json
from app.utils.shortterm.volume_5d_average_updater import update_avg_volume_for_ticker
from app.utils.shortterm.moneyflow_5d_average_updater import update_avg_money_flow_for_ticker
from app.models import DailyPrice, VolumeSnapshot, ShortTermAnalysisSignal
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


def extract_headline_impacts(text: str) -> list[dict]:
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

    return results


def premarket_analyze_with_gpt(
    db: Session,
    ticker: str,
    news_items: List[Dict],
    volume_info: VolumeSnapshot,
    user_prompt: str = "",
    top_n: int = 3,
    model: str = "gpt-4o"
) -> Dict:
    fetch_and_save_price_history(db, ticker)
    update_avg_volume_for_ticker(db, ticker)
    update_avg_money_flow_for_ticker(db, ticker)

    if not news_items:
        return {"ticker": ticker, "volume_info": None, "top_news": [], "gpt_summary": "No recent news available."}
    if not volume_info:
        return {"ticker": ticker, "volume_info": None, "top_news": news_items[:top_n], "gpt_summary": "No volume snapshot."}

    signal = db.query(ShortTermAnalysisSignal).filter_by(ticker=ticker).first()
    if not signal or not signal.updated_at or (datetime.utcnow() - signal.updated_at) > timedelta(hours=1):
        save_shortterm_analysis_signal(db, ticker)
        signal = db.query(ShortTermAnalysisSignal).filter_by(ticker=ticker).first()

    uptrend_info = normalize_uptrend_for_json(get_uptrend_analysis(db, ticker))
    downtrend_info = normalize_downtrend_for_json(get_downtrend_analysis(db, ticker))

    # Extract key trend data
    drop_pct = downtrend_info.get("drop_pct", 0)
    rise_pct = uptrend_info.get("rise_pct", 0)
    down_from = downtrend_info.get("from_date", "?")
    down_to = downtrend_info.get("to_date", "?")
    up_from = uptrend_info.get("from_date", "?")
    up_to = uptrend_info.get("to_date", "?")

    drop_from_high_pct = downtrend_info.get("drop_from_high_pct")
    rebound_from_low_pct = downtrend_info.get("rebound_from_low_pct")
    highest_price = downtrend_info.get("highest_price")
    lowest_price = downtrend_info.get("lowest_price")

    # # 🧠 Detect if uptrend was news-triggered
    # uptrend_news_matches = []
    # if up_to and up_to != "?":
    #     uptrend_date = datetime.fromisoformat(up_to).date()
    #     for item in news_items:
    #         published_at = item.get("published_at")
    #         if isinstance(published_at, str):
    #             published_at = datetime.fromisoformat(published_at)
    #         if published_at.date() == uptrend_date:
    #             uptrend_news_matches.append(item)

    # 📉 Downtrend after uptrend check
    downtrend_after_up = (
        uptrend_info.get("had_uptrend") and
        downtrend_info.get("had_downtrend") and
        up_to and down_from and down_from >= up_to
    )

    # 🧾 Trend Summary Construction
    trend_summary = ""

    # ⬆️ Uptrend Section
    if uptrend_info.get("had_uptrend"):
        uptrend_section = (
            f"📈 Uptrend: Rose {rise_pct:.2f}% from {up_from} to {up_to}.\n"
            f"- Starting price: {uptrend_info.get('start_price')} JPY\n"
            f"- Ending price: {uptrend_info.get('end_price')} JPY\n"
            f"- Duration: {uptrend_info.get('duration_days')} days\n"
        )
    else:
        uptrend_section = f"📉 No strong uptrend in the recent 10 days. Last low-to-high range: {up_from} to {up_to}.\n"

    # # 📰 News Trigger (if any)
    # if uptrend_news_matches:
    #     news_lines = [
    #         f"- \"{item['headline']}\" ({item['published_at']})"
    #         for item in uptrend_news_matches
    #     ]
    #     news_str = "\n".join(news_lines)
    #     uptrend_section += f"📰 Likely News-Driven Spike ({len(uptrend_news_matches)} match{'es' if len(uptrend_news_matches) > 1 else ''}):\n{news_str}\n"

    # ⬇️ Downtrend Section
    if downtrend_info.get("had_downtrend"):
        downtrend_section = (
            f"📉 Downtrend: Dropped {drop_pct:.2f}% from {down_from} to {down_to}.\n"
            f"- Starting price: {downtrend_info.get('start_price')} JPY\n"
            f"- Ending price: {downtrend_info.get('end_price')} JPY\n"
            f"- Duration: {downtrend_info.get('duration_days')} days\n"
        )
    else:
        downtrend_section = f"📈 No major downtrend in the recent 10 days. Latest range: {down_from} to {down_to}.\n"

    # 📊 Price Stats
    price_stats_str = ""
    if drop_from_high_pct is not None:
        price_stats_str += f"📊 Drop from 10-day high: {drop_from_high_pct}%\n"
    if rebound_from_low_pct is not None:
        price_stats_str += f"📈 Rebound from 10-day low: {rebound_from_low_pct}%\n"

    # ⚠️ Pattern Alert
    pattern_str = ""
    if downtrend_after_up:
        pattern_str += (
            "⚠️ The stock has pulled back after a prior uptrend (possibly news-based).\n"
            "📈 Watch for potential 2nd/3rd wave rebound opportunities.\n"
        )

    # Combine trend sections
    trend_summary = uptrend_section + downtrend_section + price_stats_str + pattern_str

    volume_summary = (
        f"Ticker: {volume_info.ticker}\n"
        f"Name: {volume_info.name}\n"
        f"Current Price: {volume_info.current_price} JPY\n"
        f"Volume Surge: {volume_info.volume_rate}x\n"
        f"Money Flow: {volume_info.money_flow_rate}\n"
        f"Detected At: {volume_info.detected_at.isoformat()}\n"
    )

    tech_summary = (
        f"RSI: {signal.rsi or 'N/A'}\n"
        f"MACD: {signal.macd_line}/{signal.macd_signal}\n"
        f"Pattern: {signal.candle_pattern or 'N/A'}\n"
    ) if signal else "N/A"

    analysis_signal_data = get_latest_analysis_signal_data(db, ticker)

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

    momentum_result = calculate_momentum_score(volume_info, analysis_signal_data, recent_prices=recent_prices)
    volume_info.momentum_score = momentum_result["momentum_score"]
    volume_info.momentum_confidence = momentum_result["momentum_confidence"]
    volume_info.momentum_signals = momentum_result["momentum_signals"]

    momentum_summary = (
        f"Confidence: {momentum_result['momentum_confidence']}\n"
        f"Score: {momentum_result['momentum_score']}/10\n"
        f"Signals:\n" +
        "\n".join([f"- {signal}" for signal in momentum_result['momentum_signals']]) +
        "\n"
    )

    # ↓↓↓ Apply recency penalty & prepare headline prompt ↓↓↓
    now = datetime.now(timezone.utc)
    scored_news = []
    for item in news_items:
        published_at = item.get("published_at")
        timestamp = published_at if isinstance(published_at, datetime) else datetime.fromisoformat(published_at)
        days_ago = (now - timestamp).days
        freshness_penalty = max(0, days_ago) * 5  # 5 point penalty per day
        item["recency_penalty"] = freshness_penalty
        scored_news.append(item)

    # Sort news by recency
    scored_news.sort(key=lambda x: x["recency_penalty"])

    headlines = [
        f"[{item['category']}] {item['headline']} (🕒 {item['published_at']})"
        for item in scored_news
    ]

    price_history_str = "\n".join(
        [
            f"- {p['date']}: Open: {p['open']}, High: {p['high']}, Low: {p['low']}, Close: {p['close']}"
            for p in reversed(recent_prices)  # reversed to show oldest to newest
        ]
    )

    prompt = (
        f"You are a Japanese market expert AI providing a **pre-market outlook** for stock {ticker}.\n\n"
        f"### Volume and Price Activity:\n{volume_summary}\n"
        f"### Price History (Past Days):\n{price_history_str}\n"
        f"### Trend Summary (Up/Down Movements):\n{trend_summary}\n"
        f"### Momentum Signals Summary:\n{momentum_summary}\n"
        f"### Technical Indicators (for reference only):\n{tech_summary}\n"
        f"### Recent News Headlines (timestamp included):\n"
        + "\n".join([f"{i+1}. {hl}" for i, hl in enumerate(headlines)]) +
        "\n\n### Instructions:\n"
        "- Focus primarily on **VERY RECENT NEWS**: prioritize today's news, or Friday/weekend if analyzing on Sunday/Monday.\n"
        "- The user targets **daily profit of 3–5%**, typically selling same-day **unless very strong upside** is likely.\n"
        "- Judge whether each news item is **strong enough to trigger an intraday move** — this is the main purpose.\n"
        "- Check if the price has **already reacted to the news** (based on recent price movement and trend summary). If yes, consider whether further upside is still likely or if the move is exhausted.\n"
        f"- From the above list, select the **top {top_n} most impactful headlines** for today's trading.\n"
        "- **PAY CLOSE ATTENTION** to themes like **Bitcoin, semiconductors, AI, lithium, stock splits, offering**, etc.\n"
        "- Ignore outdated or irrelevant news. Focus on items with potential to move the stock **today**.\n"
        "- Note: Even seemingly procedural headlines in Japanese markets (e.g. **株式発行**, **資本金変更**, **業務提携**, **剰余金の処分**) may cause large price reactions. Do not dismiss them too quickly.\n"
        "- Use **momentum signal confidence and score** to support or reject the case for a move.\n"
        "- If volume surged, explain **why** — due to strong news, speculative interest, or other factors?\n"
        "- Use technical indicators (RSI, MACD, moving averages, candle patterns) for **secondary confirmation only**.\n"
        "- For each headline, give:\n"
        "   - **Verdict**: One of [Decisive, Great, Good, Neutral, Bad]\n"
        "   - **Reason**: One sentence explaining the expected impact\n"
        "- Conclude with a concise summary and trading view for **today**:\n"
        "   - Investment Recommendation: Buy / Hold / Sell\n"
        "- Promising Score: (0–100) based on **news**, **technical signals**, and **rebound potential**. A high score may still occur if any one factor is particularly strong.\n"
        "- Expected Price Target (in JPY)\n"
        "- Watchlist Recommendation: Yes / No\n\n"
        "### Output Format:\n"
        "Headline List:\n"
        "1. **[Headline text here]**\n"
        "   - **Verdict: ...**\n"
        "   - **Reason: ...**\n"
        "(Repeat for each headline)\n\n"
        "Summary:\n"
        "- 📰 **News Evaluation**: [Short reasoning about news strength and impact]\n"
        "- 📊 **Signal/Technical Analysis**: [Explanation of whether momentum/technicals support move]\n"
        "- 📈 **Trend & Rebound Context**: [Explain if there was a pullback, possible rebound, or continuation]\n"
        "- Final Comment: [Your overall reasoning and sentiment for today]\n\n"
        "- Investment Recommendation: Buy / Hold / Sell\n"
        "- Promising Score: (0–100)\n"
        "- Expected Price Target (in JPY): <target price>\n"
        "- Watchlist Recommendation: Yes / No\n"
    )
    print(f"=====prompt={prompt}")

    try:
        response = openai.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        reply = response.choices[0].message.content.strip()

        recommendation, promising_score = extract_recommendation_and_score(reply)
        impacts = extract_headline_impacts(reply)
        summary_match = re.search(r"Summary:\s*(.*?)\s*(- Investment|$)", reply, re.DOTALL)
        summary = summary_match.group(1).strip() if summary_match else ""

        watchlist_recommendation = None
        for line in reply.splitlines():
            if "Watchlist Recommendation" in line:
                watchlist_recommendation = line.split(":")[-1].strip()
                break

        # Match GPT-picked top N headlines to original news, and keep only those
        headline_texts = [imp["headline"] for imp in impacts]

        # Match by either full headline or stripped version
        top_enriched_news = []
        for item in news_items:
            original = item.get("headline", "")
            full_headline = f"[{item['category']}] {original}"

            # Try fuzzy match
            match = get_close_matches(full_headline, headline_texts, n=1, cutoff=0.6)
            if not match:
                match = get_close_matches(original, headline_texts, n=1, cutoff=0.6)

            if match:
                matched_headline = match[0]
                matched = next((imp for imp in impacts if imp["headline"] == matched_headline), None)
                item["impact_verdict"] = matched.get("verdict") if matched else None
                item["impact_reason"] = matched.get("reason") if matched else None
                top_enriched_news.append(item)

        volume_info.reasoning = summary
        volume_info.recommendation = recommendation
        volume_info.promising_score = promising_score
        volume_info.watchlist_recommendation = watchlist_recommendation
        volume_info.top_news = json.dumps(top_enriched_news, ensure_ascii=False)
        volume_info.momentum_score = momentum_result["momentum_score"]
        volume_info.momentum_confidence = momentum_result["momentum_confidence"]
        volume_info.momentum_signals = momentum_result["momentum_signals"]

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




