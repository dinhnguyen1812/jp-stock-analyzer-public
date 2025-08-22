import calendar
from bs4 import BeautifulSoup
import httpx
from difflib import get_close_matches
import json
import os
import re
from datetime import date, datetime, time, timedelta, timezone
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
import openai

from app.utils.longterm.jpx_perpbr_industry import update_and_get_industry_indicators
from app.utils.longterm.yahoo_indicators import fetch_current_indicators
from app.utils.shortterm.price_updater import fetch_and_save_price_history
from app.utils.shortterm.save_shortterm_analysis_signal import save_shortterm_analysis_signal
from .calculate_momentum_score import calculate_momentum_score
from .uptrend_detector import get_uptrend_analysis, normalize_uptrend_for_json
from .downtrend_detector import get_downtrend_analysis, normalize_downtrend_for_json
from app.utils.shortterm.moneyflow_history import fetch_daily_money_flow_history, parse_volume, save_daily_money_flows
from app.utils.shortterm.volume_surge_scraper import fetch_intraday_prices
from app.utils.shortterm.volume_5d_average_updater import update_avg_volume_for_ticker
from app.utils.shortterm.moneyflow_5d_average_updater import update_avg_money_flow_for_ticker
from app.models import AverageMoneyFlow, AverageVolume, DailyPrice, VolumeSnapshot, ShortTermAnalysisSignal, DailyVolume
from app.utils.premarket.pre_volume_surge_scraper import analyze_and_snapshot_ticker
from app.utils.shortterm.kabutan_news_ticker import get_volume_info, scrape_kabutan_news
from app.api.shortterm_apis import get_latest_analysis_signal_data
from app.utils.premarket.spike_pattern import get_spike_analysis, normalize_spike_for_json

openai.api_key = os.getenv("OPENAI_API_KEY")

def extract_recommendation_and_score(text: str):
    cleaned = re.sub(r"[*#•\-–—●★▶◆]", "", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    rec_match = re.search(r"investment recommendation\s*[:\-]?\s*(buy|sell|hold|short)", cleaned, re.I)
    recommendation = rec_match.group(1).capitalize() if rec_match else "Unknown"
    score_match = re.search(r"news score\s*[:\-]?\s*(\d{1,3})", cleaned)
    news_score = int(score_match.group(1)) if score_match else -1
    news_score = max(0, min(news_score, 100))
    return recommendation, news_score


def extract_headline_impacts(text: str) -> list[dict]:
    results = []
    lines = text.splitlines()

    current_headline = None
    keyword = None
    rank = None
    verdict = None
    reason = None

    for line in lines:
        line = line.strip()

        # Headline line: number + bold text
        headline_match = re.match(r"^\d+\.\s+\*\*(.+?)\*\*$", line)
        if headline_match:
            # Save previous result if complete
            if current_headline and verdict and reason:
                results.append({
                    "headline": current_headline,
                    "keyword": keyword,
                    "rank": rank,
                    "verdict": verdict,
                    "reason": reason,
                })
            # Reset values for next block
            current_headline = headline_match.group(1).strip()
            keyword = None
            rank = None
            verdict = None
            reason = None
            continue

        # Keyword + Rank line
        keyword_rank_match = re.match(r"- \*\*Keyword:\s*(.+?)\s*-\s*Rank:\s*(.+?)\*\*", line)
        if keyword_rank_match:
            keyword = keyword_rank_match.group(1).strip()
            rank = keyword_rank_match.group(2).strip()
            continue

        # Verdict line
        verdict_match = re.match(r"- \*\*Verdict:\s*(.+?)\*\*", line)
        if verdict_match:
            verdict = verdict_match.group(1).strip()
            continue

        # Reason line
        reason_match = re.match(r"- \*\*Reason:\s*(.+?)\*\*", line)
        if reason_match:
            reason = reason_match.group(1).strip()
            continue

    # Append the last parsed item if complete
    if current_headline and verdict and reason:
        results.append({
            "headline": current_headline,
            "keyword": keyword,
            "rank": rank,
            "verdict": verdict,
            "reason": reason,
        })

    return results

def premarket_analyze_with_gpt(
    db: Session,
    ticker: str,
    news_items: List[Dict],
    volume_info: VolumeSnapshot,
    analyze_intraday: False,
    extra_guidance: str = "",
    top_n: int = 3,
    model: str = "gpt-4o",
) -> Dict:
    fetch_and_save_price_history(db, ticker)
    update_avg_volume_for_ticker(db, ticker)
    update_avg_money_flow_for_ticker(db, ticker)
    now = datetime.now(timezone.utc)

    # if volume_info.reasoning is not None:
    #     detected_at = volume_info.detected_at
    #     if detected_at is not None and (now - detected_at) < timedelta(hours=2):
    #         # Skip processing
    #         print("Skipping because reasoning exists and detected_at < 1 hour ago")
    #         return

    # seven_days_ago = datetime.now() - timedelta(days=7)

    # low_score_exists = (
    #     db.query(VolumeSnapshot)
    #     .filter(
    #         VolumeSnapshot.ticker == volume_info.ticker,
    #         VolumeSnapshot.news_score <= 50,  # or <= 50 if you want to match the print
    #         VolumeSnapshot.detected_at >= seven_days_ago
    #     )
    #     .first()
    # )
    # if low_score_exists:
    #     print("⏩ Skipping: found previous snapshot with news_score <= 50")
    #     return

    # Short term data
    if not news_items:
        return {"ticker": ticker, "volume_info": None, "top_news": [], "gpt_summary": "No recent news available."}
    if not volume_info:
        return {"ticker": ticker, "volume_info": None, "top_news": news_items[:top_n], "gpt_summary": "No volume snapshot."}

    signal = db.query(ShortTermAnalysisSignal).filter_by(ticker=ticker).first()
    if not signal or not signal.updated_at or (datetime.utcnow() - signal.updated_at) > timedelta(hours=1):
        save_shortterm_analysis_signal(db, ticker)
        signal = db.query(ShortTermAnalysisSignal).filter_by(ticker=ticker).first()

    spike_summary = ""
    spike_info = normalize_spike_for_json(get_spike_analysis(db, ticker))
    if spike_info['spike_date']:
        spike_summary = (
            f"First spike: {spike_info['spike_date']}, "
            f"Closed near high: {'Yes' if spike_info['first_day_close_near_high'] else 'No'}, "
            f"Number of respikes: {spike_info['number_of_respikes']}, "
            f"Drop from high: {spike_info['drop_from_high_pct']}%, "
            f"Last day close near low: {'Yes' if spike_info['last_day_close_near_low'] else 'No'}"
            f"Score for spike pattern: {spike_info['score']}"
        )

    jst = timezone(timedelta(hours=9))
    now_jst = now.astimezone(jst)
    date_str = now_jst.date().isoformat()
    latest_trading_day = get_latest_trading_day(db)
    if analyze_intraday:
        intraday_info = get_intraday_volume_info_for_ticker(db, ticker)
        intraday_summary = (
            f"Current Price: {intraday_info['current_price']} JPY\n"
            f"Volume: {intraday_info['current_volume']}\n"
            f"Volume Surge: {intraday_info['volume_rate']:.2f}x\n"
            f"Money Flow: {intraday_info['money_flow_rate']:.2f}x\n"
        )
    volume_summary = (
        f"Ticker: {volume_info.ticker}\n"
        f"Name: {volume_info.name}\n"
        f"Current Price: {volume_info.current_price} JPY\n"
        f"Volume: {volume_info.current_volume} JPY\n"
        f"Volume Surge: {volume_info.volume_rate}x\n"
        f"Money Flow: {volume_info.money_flow_rate}\n"
        # f"Detected At: {volume_info.detected_at.isoformat()}\n"
    )

    # tech_summary = (
    #     f"RSI: {signal.rsi or 'N/A'}\n"
    #     f"MACD: {signal.macd_line}/{signal.macd_signal}\n"
    #     f"Pattern: {signal.candle_pattern or 'N/A'}\n"
    # ) if signal else "N/A"

    # analysis_signal_data = get_latest_analysis_signal_data(db, ticker)

    recent_prices_query = (
        db.query(DailyPrice)
        .filter(DailyPrice.ticker == ticker)
        .order_by(DailyPrice.date.desc())
        .limit(15)
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

    # momentum_result = calculate_momentum_score(volume_info, analysis_signal_data, recent_prices=recent_prices)
    # volume_info.momentum_score = momentum_result["momentum_score"]
    # volume_info.momentum_confidence = momentum_result["momentum_confidence"]
    # volume_info.momentum_signals = momentum_result["momentum_signals"]

    # momentum_summary = (
    #     f"Confidence: {momentum_result['momentum_confidence']}\n"
    #     f"Score: {momentum_result['momentum_score']}/10\n"
    #     f"Signals:\n" +
    #     "\n".join([f"- {signal}" for signal in momentum_result['momentum_signals']]) +
    #     "\n"
    # )

    # ↓↓↓ Apply recency penalty & prepare headline prompt ↓↓↓
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

    reference_summary = ""

    # Fetch the two most recent snapshots for this ticker
    vs_list = (
        db.query(VolumeSnapshot)
        .filter(VolumeSnapshot.ticker == ticker)
        .order_by(VolumeSnapshot.detected_at.desc())
        .limit(2)
        .all()
    )

    latest_vs = vs_list[1] if len(vs_list) == 2 else None

    # Extract latest news headline from Kabutan scrape
    latest_news_headline = news_items[0]["headline"] if news_items else None

    if latest_vs and latest_news_headline == latest_vs.latest_news and latest_vs.model == "gpt-4o":
        print(f"⏩ Skipping: Skip gpt analyze because no new news")

        # Reuse GPT analysis since news hasn't changed
        volume_info.reasoning = latest_vs.reasoning
        volume_info.recommendation = latest_vs.recommendation
        volume_info.news_score = latest_vs.news_score
        volume_info.highest_impact_keyword = latest_vs.highest_impact_keyword
        volume_info.highest_impact_rank = latest_vs.highest_impact_rank
        volume_info.top_news = latest_vs.top_news

        # volume_info.momentum_score = momentum_result["momentum_score"]
        # volume_info.momentum_confidence = momentum_result["momentum_confidence"]
        # volume_info.momentum_signals = momentum_result["momentum_signals"]

        volume_info.latest_news = latest_news_headline
        volume_info.model = "gpt-4o"

        db.commit()

        return {
            "ticker": ticker,
            "recommendation": latest_vs.recommendation,
            "news_score": latest_vs.news_score,
            "headline_impacts": json.loads(latest_vs.top_news) if latest_vs.top_news else [],
            "summary": latest_vs.reasoning,
            # "momentum_score": momentum_result["momentum_score"],
            # "momentum_confidence": momentum_result["momentum_confidence"],
            # "momentum_signals": momentum_result["momentum_signals"],
        }

    prompt = (
        f"You are a Japanese market expert AI providing a **pre-market outlook for stock {ticker}** — to support a trade decision for **tomorrow's trading session**.\n\n"
        f"Today is {date_str}, time: {now_jst}. Latest completed trading day: {latest_trading_day}, time: 15:30:00.\n"
        f"### Volume and Price Activity:\n{volume_summary}\n"
        f"### Spike pattern:\n{spike_summary}\n"
        f"### Intraday: {analyze_intraday}." + f" Summary:\n{intraday_summary}\n" if analyze_intraday else "\n"
        f"### Price History (Past Days):\n{price_history_str}\n"
        f"### Recent News Headlines (past 7 days, timestamp included):\n"
        + "\n".join([f"{i+1}. {hl}" for i, hl in enumerate(headlines)]) +
        "\n\n"

        "### Instructions:\n"
        f"{extra_guidance}"
        "- **Main Goal:** Evaluate if the stock is in **spike continuation** or **re-spike phase**. Secondary: detect strong **new spikes**.\n"
        "- Always identify **wave stage**: haven't spiked yet, first spike, re-spike, pullback, continuation, or exhausted.\n"
        "- Include historical price table for trend/resistance/support context.\n"

        "- News Scoring Guidance:\n"
        "   - Weighting: **News (90%) + Technical/Momentum (10%)**\n"
        "   - News strength & recency. More recent events → higher score.\n"
        "   - Technical/momentum only adjusts score slightly.\n\n"

        "- 🧠 News Impact Ranking:\n"
        "- For each top headline, assign a keyword and rank based on this table:\n"
        "  {\n"
        # S rank - strongest triggers
        "    'TOB / MBO': 'S',\n"

        # A+ rank - very strong positive
        "    '大型受注': 'A+',\n"
        "    '筆頭株主変更': 'A+',\n"

        # A rank - strong positive
        "    '黒字転換': 'A',\n"
        "    '新市場参入': 'A',\n"
        "    '新サービス発表': 'A',\n"
        "    '特許取得': 'A',\n"
        "    '新製品発表': 'A',\n"
        "    '事業拡大': 'A',\n"
        "    '買収': 'A',\n"
        "    '独占契約': 'A',\n"

        # A- rank - technical signals
        "    'ゴールデンクロス': 'A-',\n"
        "    '±３σブレイク': 'A-',\n"
        "    'ボリンジャーバンド上抜け': 'A-',\n"
        "    'fisco注目': 'A-',\n"
        "    'ストップ高': 'A-',\n"
        "    '動意株': 'A-',\n"

        # B rank - moderate positive
        "    '中期経営計画': 'B',\n"
        "    '株式買戻し': 'B',\n"
        "    '特別利益': 'B',\n"
        "    '株主優待増額': 'B',\n"
        "    '配当増額': 'B',\n"
        "    '販売契約': 'B',\n"
        "    '大量保有報告書': 'B',\n"
        "    'サプライズ決算': 'B',\n"
        "    '四半期サプライズ決算': 'B',\n"
        "    '増益': 'B',\n"
        "    '赤字縮小': 'B',\n"
        "    '利益倍増': 'B',\n"
        "    '今期 業績予想 50%増益以上': 'B',\n"
        "    '業績予想 上方修正': 'B',\n"
        "    '月次売上・業績データ': 'B',\n"

        # C rank - negative or neutral
        "    '施設閉鎖': 'C',\n"
        "    '運営終了': 'C',\n"
        "    '事業報告': 'C',\n"
        "    '株式発行': 'C',\n"
        "    '株主総会': 'C',\n"
        "    '一目均衡表・雲抜け': 'C',\n"

        # D rank - negative
        "    '減益': 'D',\n"
        "    '赤字転落': 'D',\n"
        "    '赤字拡大': 'D'\n"
        "    '資本金変更': 'D',\n"
        "    '再掲IR': 'D',\n"
        "    '過去の材料再加熱': 'D'\n"
        "    '上場廃止': 'D'\n"
        "  }\n"
        "\n"
        # "- 🔧 Booster Instruction:\n"
        # "  - **HOT/TRENDING SECTORS**: AI, Web3, semiconductors, space, quantum computing, medical tech, robotics, FinTech, crypto, mobility, biotech, data centers, EV, hydrogen.\n"
        # "  - Boost ranks for these keywords per rules:\n"
        # "    • 'TOB / MBO': S+ if large premium, notable acquirer, or immediate gap-up with strong volume.\n"
        # "    • '大型受注': S if from major client, long-term contract, or in HOT/TRENDING SECTOR.\n"
        # "    • '筆頭株主変更': S if new shareholder is major institution, foreign fund, strategic partner, or HOT/TRENDING SECTOR.\n"
        # "    • '新市場参入': S if entering HOT/TRENDING SECTOR — no exceptions.\n"
        # "    • '新サービス発表': S if service is in HOT/TRENDING SECTOR — no exceptions.\n"
        # "    • '特許取得': S if patent is in HOT/TRENDING SECTOR — no exceptions.\n"
        # "    • '買収': S if in or enabling entry into HOT/TRENDING SECTOR — no exceptions.\n"
        # "    • '事業拡大': S if in HOT/TRENDING SECTOR — no exceptions.\n"
        # "    • '黒字転換': A+ if leads to sustained profitability or strong market reaction.\n"
        # "    • '独占契約': A+ if partner is top-tier or market scale is large.\n"
        # "    • '中期経営計画': A+ if includes aggressive growth, global expansion, or restructuring in promising areas.\n"
        # "    • '特別利益': A if significantly improves EPS or valuation.\n"
        # "    • '今期 業績予想 50%増益以上': A if unexpected or paired with strong catalysts.\n"
        # "    • '業績予想 上方修正': A if unexpected or paired with strong catalysts.\n"
        # "    • 'サプライズ決算': A if far above expectations.\n"
        # "    • '四半期サプライズ決算': A if strong quarterly surprise.\n"
        # "    • '増益': A+ if >50% and unexpected; A if 30–50% with positive sentiment or low float.\n"
        # "    • '利益倍増': S if 2倍+ in HOT/TRENDING SECTOR, else A if backed by strong catalyst.\n"
        # "    • 'fisco注目': A if already trending or with strong catalyst.\n"
        # "    • '大量保有報告書': A if new investor is activist fund, foreign investor, or shows strategic interest.\n"
        "- 🔧 Booster Instruction:\n"
        "  - HOT/TRENDING SECTORS: Data center, AI, Web3, semiconductors, space, quantum computing, medical tech, robotics, FinTech, crypto, mobility, biotech, data centers, EV, hydrogen.\n"
        "  - Boost ranks according to rules (S+, A+, etc.).\n\n"

        "-  Score Instruction"
        "   - News Score = News (mapped D–S+) × recency factor (≤1d=1, <5d=0.9, <10d=0.8, >10d=0.7).\n"
        "   - News rank map score → D:0–19, C:20–39, B:40–59, A-:50–59, A:70–79, A+:80–89, S:90–94, S+:95–100"

        "### Output Format:\n"
        "Headline List:\n"
        "1. **[Headline text here]**\n"
        "   - **Keyword: [as guidance above] - Rank: [as guidance above]**\n"
        "   - **Verdict: Same as Rank, one of [S+, S, A+, A, A-, B, C, D, N/A]**\n"
        "   - **Reason: One sentence explaining the expected impact**\n"
        # "- Choose and analyze the **top 10 most impactful headlines** based on rank and relevance.\n"
        "(Repeat for each headline)\n\n"

        "- Investment Recommendation: Buy / Hold / Sell\n"

        "Summary:\n"
        "- 📰 News Score: (0–100)\n"
        "   - [Overall impact levels of top news]\n"
        "   - [Short reasoning about which headlines matter and how price responded]\n"
        "- 📈 Spike pattern: [Explain any spikes, pullbacks, potential rebound zones, or exhaustion. Also state if re-spike pattern was detected — and if not, why not (e.g. no prior strong spike, new news exists, weak volume, etc).]\n"
        "  [Spike pattern setups: A-S+ ranked news, first spike closed near high, might pullback after spike, last close near low.]\n"
        "- 📅 Tomorrow's Action Expectation: Gap direction, morning behavior, and closing tendency\n"
        "- 📊 Wave Stage: [Wave 1 / Wave 2 / Wave 3 / Overextended / Not started]\n"
        "- 🕒 First Spike Summary: [Did it happen? If it did: when? On what news? How strong?]\n"
        "- ⏳ Entry Guidance: [E.g. 'Wait for second spike', 'Buy dip on rebound', 'Risk of exhaustion — wait']\n"
    )
    # print(f"prompt={prompt}")

    try:
        response = openai.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        reply = response.choices[0].message.content.strip()

        recommendation, news_score = extract_recommendation_and_score(reply)

        # spiked, spike_next = extract_spiked_and_spike_next(reply)

        impacts = extract_headline_impacts(reply)
        # summary_match = re.search(r"Summary:\s*(.*?)\s*(- Investment|$)", reply, re.DOTALL)
        # summary = summary_match.group(1).strip() if summary_match else ""
        summary_match = re.search(
            r"##+ Summary:\s*(.*?)(?=\n##+|\Z)",
            reply,
            re.DOTALL
        )
        summary = summary_match.group(1).strip() if summary_match else ""


        highest_impact_keyword = None
        highest_impact_rank = None
        highest_impact_keyword, highest_impact_rank = extract_highest_ranked_impact(reply)

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
                item["keyword"] = matched.get("keyword") if matched else None
                item["rank"] = matched.get("rank") if matched else None
                top_enriched_news.append(item)

        volume_info.reasoning = summary
        volume_info.recommendation = recommendation
        volume_info.news_score = news_score
        # volume_info.spiked = spiked
        # volume_info.spike_next = spike_next
        volume_info.highest_impact_keyword = highest_impact_keyword
        volume_info.highest_impact_rank = highest_impact_rank
        volume_info.top_news = json.dumps(top_enriched_news, ensure_ascii=False)
        # volume_info.momentum_score = momentum_result["momentum_score"]
        # volume_info.momentum_confidence = momentum_result["momentum_confidence"]
        # volume_info.momentum_signals = momentum_result["momentum_signals"]

        volume_info.latest_news = latest_news_headline
        volume_info.model = model

        db.commit()

        return {
            "ticker": ticker,
            "recommendation": recommendation,
            "news_score": news_score,
            "headline_impacts": impacts,
            "summary": summary,
            "gpt_raw_response": reply,
            # "downtrend": downtrend_info,
            # "uptrend": uptrend_info,
            # "drop_from_high_pct": drop_from_high_pct,
            # "rebound_from_low_pct": rebound_from_low_pct,
            # "highest_price": highest_price,
            # "lowest_price": lowest_price,
            # "momentum_score": momentum_result["momentum_score"],
            # "momentum_confidence": momentum_result["momentum_confidence"],
            # "momentum_signals": momentum_result["momentum_signals"],
        }

    except Exception as e:
        print(f"❌ GPT error for {ticker}: {e}")
        return {"ticker": ticker, "error": str(e)}

def rank_value(rank_str):
    rank_order = ["S+", "S", "A+", "A", "A-", "B", "C", "D", "N/A"]
    try:
        return rank_order.index(rank_str)
    except ValueError:
        return len(rank_order)  # lowest rank if unknown

def extract_highest_ranked_impact(text: str):
    pattern = re.compile(r"\*\*Keyword:\s*(.+?)\s*-\s*Rank:\s*([A-Za-z0-9\s\+\-]+)\*\*", re.IGNORECASE)
    matches = pattern.findall(text)

    best_rank = None
    best_keyword = None

    skip_keywords = {
        "ゴールデンクロス",
        "±３σブレイク",
        "ボリンジャーバンド上抜け",
        "fisco注目",
    }

    for keyword, rank in matches:
        keyword = keyword.strip()
        rank = rank.strip()
        current_rank_value = rank_value(rank)

        # Skip if keyword is in skip list
        if keyword in skip_keywords:
            continue

        # # Prioritize high-confidence "re-spike"
        # Skip if keyword include "re-spike"
        if "re-spike" in keyword.lower() and current_rank_value <= rank_value("B"):
        #     return keyword, rank  # return immediately
            continue

        if best_rank is None or current_rank_value <= rank_value(best_rank):
            best_rank = rank
            best_keyword = keyword

    return best_keyword, best_rank

def get_intraday_volume_info_for_ticker(db: Session, ticker: str) -> Optional[dict]:
    url = f"https://finance.yahoo.co.jp/quote/{ticker}.T"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "ja,en;q=0.9",
    }

    try:
        resp = httpx.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # 1. Extract name
        name_tag = (
            soup.select_one("h2.PriceBoardMain__name__6uDh")
            or soup.select_one("h2.PriceBoard__name__166W")
        )
        name = name_tag.text.strip() if name_tag else ticker

        # 2. Extract 出来高 (current volume)
        current_volume = None
        labels = soup.select("span.DataListItem__name__3RQJ")
        for label in labels:
            if "出来高" in label.text:
                value_span = label.find_next("span", class_="StyledNumber__value__3rXW")
                if value_span:
                    raw_volume = value_span.text.strip()
                    if raw_volume not in {"---", "-", ""}:
                        current_volume = parse_volume(raw_volume)
                break

        if current_volume is None:
            return None

        # 3. Price info
        current_price, _, high, low = fetch_intraday_prices(ticker)
        if not all([current_price, high, low]):
            print(f"⚠️ Skipping {ticker}: could not get high/low/current prices.")
            return None

        # 4. Calculate volume rate
        avg_record = db.query(AverageVolume).filter_by(ticker=ticker).first()
        if not avg_record or not avg_record.avg_5d_volume:
            return None
        avg_volume_5d = avg_record.avg_5d_volume

        now = datetime.now()
        market_open = datetime.combine(now.date(), time(9, 0))
        market_close = datetime.combine(now.date(), time(15, 0))

        if now <= market_open or now >= market_close:
            expected_volume_by_now = avg_volume_5d
        else:
            trading_hours_passed = max(get_trading_hours_passed(now), 0.5)
            expected_volume_by_now = avg_volume_5d * (trading_hours_passed / 5.5)

        volume_rate = current_volume / expected_volume_by_now if expected_volume_by_now > 0 else 0

        # 5. Calculate money flow rate
        typical_price_now = (high + low + current_price) / 3
        raw_money_flow_now = typical_price_now * current_volume

        moneyflow_record = db.query(AverageMoneyFlow).filter_by(ticker=ticker).first()
        if not moneyflow_record or moneyflow_record.avg_5d_money_flow == 0:
            print(f"ℹ️ No avg_5d_money_flow for {ticker}, trying to scrape history and update...")
            flow_data = fetch_daily_money_flow_history(ticker)
            if flow_data:
                save_daily_money_flows(db, ticker, flow_data)
                update_avg_money_flow_for_ticker(db, ticker)
                moneyflow_record = db.query(AverageMoneyFlow).filter_by(ticker=ticker).first()
            else:
                print(f"❌ Failed to fetch money flow history for {ticker}, skipping money flow.")
                moneyflow_record = None

        money_flow_rate = (
            raw_money_flow_now / moneyflow_record.avg_5d_money_flow
            if moneyflow_record and moneyflow_record.avg_5d_money_flow > 0 else None
        )

        return {
            "ticker": ticker,
            "name": name,
            "current_price": current_price,
            "current_volume": current_volume,
            "volume_rate": round(volume_rate, 2),
            "money_flow_rate": round(money_flow_rate, 2) if money_flow_rate is not None else None,
            "timestamp": now.isoformat(),
        }

    except Exception as e:
        print(f"⚠️ Error while scraping {ticker}: {e}")
        return None


def get_trading_hours_passed(now: datetime) -> float:
    open_time = datetime.combine(now.date(), time(9, 0))
    lunch_start = datetime.combine(now.date(), time(11, 30))
    lunch_end = datetime.combine(now.date(), time(12, 30))
    close_time = datetime.combine(now.date(), time(15, 30))

    if now < open_time:
        return 0.0
    elif now <= lunch_start:
        return (now - open_time).total_seconds() / 3600
    elif now <= lunch_end:
        return 2.5  # morning session done, lunch time
    elif now <= close_time:
        return 2.5 + (now - lunch_end).total_seconds() / 3600
    else:
        return 5.5  # full trading day

def get_latest_trading_day(db: Session):
    ticker = '7203'
    fetch_and_save_price_history(db, ticker)

    result = (
        db.query(DailyPrice.date)
        .filter(DailyPrice.ticker == ticker)
        .order_by(DailyPrice.date.desc())
        .first()
    )

    return result[0] if result else None

def check_market_hours(db):
    update_avg_volume_for_ticker(db, '7203')

    latest_record = (
        db.query(DailyVolume)
        .filter_by(ticker='7203')
        .order_by(DailyVolume.date.desc())
        .first()
    )

    url = f"https://finance.yahoo.co.jp/quote/7203.T"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "ja,en;q=0.9",
    }

    try:
        resp = httpx.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # 2. Extract 出来高 (current volume)
        current_volume = None
        labels = soup.select("span.DataListItem__name__3RQJ")
        for label in labels:
            if "出来高" in label.text:
                value_span = label.find_next("span", class_="StyledNumber__value__3rXW")
                if value_span:
                    raw_volume = value_span.text.strip()
                    if raw_volume not in {"---", "-", ""}:
                        current_volume = parse_volume(raw_volume)
                break
        return current_volume != latest_record.volume

    except Exception as e:
        print(f"⚠️ Error while scraping 7203: {e}")
        return False

def analyze_ticker_by_steps(db: Session, ticker: str, top_n: int = 3, model: str = "gpt-4o", analyze_intraday = False, extra_guidance="") -> Dict:
    # Step 1: Get news
    news = scrape_kabutan_news(ticker, limit=30)
    if not news:
        raise ValueError(f"No news found for ticker {ticker}")

    # Step 2: Generate & save snapshot
    snapshot = analyze_and_snapshot_ticker(
        db=db,
        ticker=ticker,
        surge_threshold=0.0,
        price_threshold=0,
    )
    if not snapshot:
        raise ValueError(f"{ticker} does not meet surge/price criteria.")

    # Step 3: Retrieve VolumeSnapshot from DB
    volume_info = get_volume_info(db, ticker=ticker)
    if not volume_info:
        raise ValueError(f"No volume data found for {ticker}")

    # Step 4: Analyze with GPT
    premarket_analyze_with_gpt(
        db=db,
        ticker=ticker,
        news_items=news,
        volume_info=volume_info,
        analyze_intraday=analyze_intraday,
        top_n=top_n,
        model=model,
        extra_guidance=extra_guidance,
    )
    return {"message": f"Analyzing complete. {ticker} analyzed."}