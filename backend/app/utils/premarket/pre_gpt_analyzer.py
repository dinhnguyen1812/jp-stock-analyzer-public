import json
import os
import re
import difflib
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
import openai
from app.utils.shortterm.kabutan_news_ticker import scrape_kabutan_news, get_volume_info
from app.utils.shortterm.save_shortterm_analysis_signal import save_shortterm_analysis_signal
from app.models import VolumeSnapshot, ShortTermAnalysisSignal, StockNewsImpact

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

def extract_headline_impacts(text: str, top_n: int = 5):
    verdicts = ["Decisive", "Great", "Good", "Neutral", "Bad", "Irrelevant"]
    results = []

    lines = text.splitlines()
    for line in lines:
        if any(v.lower() in line.lower() for v in verdicts):
            verdict_match = next((v for v in verdicts if v.lower() in line.lower()), None)
            if not verdict_match:
                continue
            reason_match = re.sub(rf"[^:]+[:\-]\s*", "", line).strip()
            headline_match = re.sub(r"\s*\([^)]+\)$", "", line.strip())  # Remove verdict in parentheses
            results.append({
                "headline": headline_match,
                "verdict": verdict_match,
                "reason": reason_match,
            })
            if len(results) >= top_n:
                break
    return results

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

    headlines = [f"[{item['category']}] {item['headline']}" for item in news_items[:top_n]]
    prompt = (
        f"You are a pre-market analyst.\n\n"
        f"### Volume:\n{volume_summary}\n"
        f"### Technicals (less important):\n{tech_summary}\n"
        f"### News:\n" + "\n".join([f"{i+1}. {hl}" for i, hl in enumerate(headlines)]) + "\n\n"
        f"### Tasks:\n"
        f"- Predict if this stock will likely move up/down tomorrow and why.\n"
        f"- Give:\n"
        f"  - Investment Recommendation (Buy/Hold/Sell/Short)\n"
        f"  - Promising Score (0–100)\n"
        f"  - Price Target\n"
        f"- Return a **ranked list of {top_n} impactful headlines**. For each:\n"
        f"  - Verdict (Neutral, Good, Great, Decisive, Bad)\n"
        f"  - 1-line reason\n"
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

        summary = reply.split("Summary:")[-1].split("- Investment")[0].strip()

        # Save to VolumeSnapshot
        volume_info.reasoning = summary
        volume_info.recommendation = recommendation
        volume_info.promising_score = promising_score
        volume_info.top_news = json.dumps(news_items[:top_n], ensure_ascii=False)
        db.commit()

        # Save impacts
        db.query(StockNewsImpact).filter_by(ticker=ticker).delete()
        for item in impacts:
            impact = StockNewsImpact(
                ticker=ticker,
                headline=item["headline"],
                verdict=item["verdict"],
                reason=item["reason"],
                created_at=datetime.utcnow()
            )
            db.add(impact)
        db.commit()

        return {
            "ticker": ticker,
            "recommendation": recommendation,
            "score": promising_score,
            "headline_impacts": impacts,
            "summary": summary,
            "gpt_raw_response": reply
        }

    except Exception as e:
        print(f"❌ GPT error for {ticker}: {e}")
        return {"ticker": ticker, "error": str(e)}
