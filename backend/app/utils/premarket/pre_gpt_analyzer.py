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

# def extract_spike_info(text: str) -> Optional[Dict[str, str]]:
#     pattern = re.compile(
#         r"\*\*Spiked\*\*:\s*\[?(Yes|No)\]?\s*—\s*\*\*Spike next\*\*:\s*\(?(\d{1,3})\)?",
#         re.IGNORECASE
#     )

#     for line in text.splitlines():
#         line = line.strip()
#         m = pattern.search(line)
#         if m:
#             return {
#                 "spiked": m.group(1).capitalize(),
#                 "spike_next": m.group(2)
#             }

#     return None

def extract_spiked_and_spike_next(text: str):
    cleaned = re.sub(r"[*#•\-–—●★▶◆]", "", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()

    spiked_match = re.search(r"\bspiked\s*[:\-]?\s*(yes|no)", cleaned)
    spiked = spiked_match.group(1).capitalize() if spiked_match else "Unknown"

    spike_next_match = re.search(r"\bspike next\s*[:\-]?\s*(\d{1,3})", cleaned)
    spike_next = int(spike_next_match.group(1)) if spike_next_match else -1
    spike_next = max(0, min(spike_next, 100))

    return spiked, spike_next

def premarket_analyze_with_gpt(
    db: Session,
    ticker: str,
    news_items: List[Dict],
    volume_info: VolumeSnapshot,
    is_market_hours: False,
    extra_guidance: str = "",
    top_n: int = 3,
    model: str = "gpt-4o"
) -> Dict:
    fetch_and_save_price_history(db, ticker)
    update_avg_volume_for_ticker(db, ticker)
    update_avg_money_flow_for_ticker(db, ticker)
    now = datetime.now(timezone.utc)

    if volume_info.reasoning is not None:
        detected_at = volume_info.detected_at
        if detected_at is not None and (now - detected_at) < timedelta(hours=1):
            # Skip processing
            print("Skipping because reasoning exists and detected_at < 1 hour ago")
            return

    low_score_exists = (
        db.query(VolumeSnapshot)
        .filter(
            VolumeSnapshot.ticker == volume_info.ticker,
            VolumeSnapshot.promising_score <= 30
        )
        .first()
    )
    if low_score_exists:
        print("⏩ Skipping: found previous snapshot with promising_score <= 50")
        return

    # Long-term data
    # stock_data = fetch_current_indicators(ticker)
    # if not stock_data:
    #     raise ValueError(f"Could not fetch indicators for {ticker}")

    # industry_name = stock_data.get("industry", "")
    # industry_data = update_and_get_industry_indicators(industry_name, db)
    # if industry_data:
    #     industry_info = industry_data[0]
    #     industry_name = industry_info.get("industry", "N/A")
    #     industry_per = industry_info.get("per", "N/A")
    #     industry_pbr = industry_info.get("pbr", "N/A")
    #     industry_roe = industry_info.get("roe", "N/A")
    # else:
    #     industry_name = industry_per = industry_pbr = industry_roe = "N/A"
    
    # longterm_summary = (
    #     f"- PER: {stock_data.get('per', 'N/A')} vs Industry Avg: {industry_per}\n"
    #     f"- PBR: {stock_data.get('pbr', 'N/A')} vs Industry Avg: {industry_pbr}\n"
    #     f"- ROE: {stock_data.get('roe', 'N/A')}% vs Industry Avg: {industry_roe}%\n"
    #     f"- EPS: {stock_data.get('eps', 'N/A')} / BPS: {stock_data.get('bps', 'N/A')}\n"
    #     f"- Dividend Yield: {stock_data.get('dividend_yield', 'N/A')}%\n"
    #     f"- Debt Ratio: {stock_data.get('debt_ratio', 'N/A')}%\n"
    #     f"- Market Cap: ¥{stock_data.get('market_cap', 'N/A')}\n"
    #     f"\nOnly use these if they are **material to interpreting recent price movement or news**. For example:\n"
    #     f"- A low PER and high ROE might justify strong recent buying.\n"
    #     f"- A high PER with weak EPS may indicate **speculative overreaction**.\n"
    #     f"- A strong dividend yield could attract defensive flows.\n"
    # )
    # print(f"====ticker={ticker}, longterm_summary={longterm_summary}")

    # Short term data
    if not news_items:
        return {"ticker": ticker, "volume_info": None, "top_news": [], "gpt_summary": "No recent news available."}
    if not volume_info:
        return {"ticker": ticker, "volume_info": None, "top_news": news_items[:top_n], "gpt_summary": "No volume snapshot."}

    signal = db.query(ShortTermAnalysisSignal).filter_by(ticker=ticker).first()
    if not signal or not signal.updated_at or (datetime.utcnow() - signal.updated_at) > timedelta(hours=1):
        save_shortterm_analysis_signal(db, ticker)
        signal = db.query(ShortTermAnalysisSignal).filter_by(ticker=ticker).first()

    # uptrend_info = normalize_uptrend_for_json(get_uptrend_analysis(db, ticker))
    # downtrend_info = normalize_downtrend_for_json(get_downtrend_analysis(db, ticker))

    # # Extract key trend data
    # drop_pct = downtrend_info.get("drop_pct", 0)
    # rise_pct = uptrend_info.get("rise_pct", 0)
    # down_from = downtrend_info.get("from_date", "?")
    # down_to = downtrend_info.get("to_date", "?")
    # up_from = uptrend_info.get("from_date", "?")
    # up_to = uptrend_info.get("to_date", "?")

    # drop_from_high_pct = downtrend_info.get("drop_from_high_pct")
    # rebound_from_low_pct = downtrend_info.get("rebound_from_low_pct")
    # highest_price = downtrend_info.get("highest_price")
    # lowest_price = downtrend_info.get("lowest_price")

    # # 📉 Downtrend after uptrend check
    # downtrend_after_up = (
    #     uptrend_info.get("had_uptrend") and
    #     downtrend_info.get("had_downtrend") and
    #     up_to and down_from and down_from >= up_to
    # )

    # 🧾 Trend Summary Construction
    # trend_summary = ""

    # # ⬆️ Uptrend Section
    # if uptrend_info.get("had_uptrend"):
    #     uptrend_section = (
    #         f"📈 Uptrend: Rose {rise_pct:.2f}% from {up_from} to {up_to}.\n"
    #         f"- Starting price: {uptrend_info.get('start_price')} JPY\n"
    #         f"- Ending price: {uptrend_info.get('end_price')} JPY\n"
    #         f"- Duration: {uptrend_info.get('duration_days')} days\n"
    #     )
    # else:
    #     uptrend_section = f"📉 No strong uptrend in the recent 10 days. Last low-to-high range: {up_from} to {up_to}.\n"

    # # ⬇️ Downtrend Section
    # if downtrend_info.get("had_downtrend"):
    #     downtrend_section = (
    #         f"📉 Downtrend: Dropped {drop_pct:.2f}% from {down_from} to {down_to}.\n"
    #         f"- Starting price: {downtrend_info.get('start_price')} JPY\n"
    #         f"- Ending price: {downtrend_info.get('end_price')} JPY\n"
    #         f"- Duration: {downtrend_info.get('duration_days')} days\n"
    #     )
    # else:
    #     downtrend_section = f"📈 No major downtrend in the recent 10 days. Latest range: {down_from} to {down_to}.\n"

    # # 📊 Price Stats
    # price_stats_str = ""
    # if drop_from_high_pct is not None:
    #     price_stats_str += f"📊 Drop from 10-day high: {drop_from_high_pct}%\n"
    # if rebound_from_low_pct is not None:
    #     price_stats_str += f"📈 Rebound from 10-day low: {rebound_from_low_pct}%\n"

    # # ⚠️ Pattern Alert
    # pattern_str = ""
    # if downtrend_after_up:
    #     pattern_str += (
    #         "⚠️ The stock has pulled back after a prior uptrend (possibly news-based).\n"
    #         "📈 Watch for potential 2nd/3rd wave rebound opportunities.\n"
    #     )

    # # Combine trend sections
    # trend_summary = uptrend_section + downtrend_section + price_stats_str + pattern_str

    jst = timezone(timedelta(hours=9))
    now_jst = now.astimezone(jst)
    date_str = now_jst.date().isoformat()
    latest_trading_day = get_latest_trading_day(db)
    if is_market_hours:
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
    # print(f"====headlines={headlines}")

    price_history_str = "\n".join(
        [
            f"- {p['date']}: Open: {p['open']}, High: {p['high']}, Low: {p['low']}, Close: {p['close']}"
            for p in reversed(recent_prices)  # reversed to show oldest to newest
        ]
    )

    prompt = (
        f"You are a Japanese market expert AI providing a **pre-market outlook for stock {ticker}** — to support a trade decision for **tomorrow's trading session**.\n\n"
        f"Today is {date_str}, time: {now_jst}. Latest completed trading day: {latest_trading_day}, time: 15:30:00.\n"
        # f"### Fundamental Snapshot (for context only):\n{longterm_summary}\n"
        f"### Volume and Price Activity:\n{volume_summary}\n"
        f"### Intraday: {is_market_hours}. Intraday summary:\n{intraday_summary if is_market_hours else None}\n"
        f"### Price History (Past Days):\n{price_history_str}\n"
        # f"### Trend Summary (Up/Down Movements):\n{trend_summary}\n"
        f"### Momentum Signals Summary:\n{momentum_summary}\n"
        f"### Technical Indicators (for reference only):\n{tech_summary}\n"
        f"### Recent News Headlines (past 7 days, timestamp included):\n"
        + "\n".join([f"{i+1}. {hl}" for i, hl in enumerate(headlines)]) +
        "\n\n"

        "### Instructions:\n"
        f"{extra_guidance}"
        # "- Only use **fundamental data** if it clearly explains the price move (e.g. PER far from industry avg, ROE strong, speculative excess).\n"
        # "- Do **not** perform full valuation; use it only to support short-term momentum/sentiment judgment.\n"
        "- Focus primarily on **recent impactful news**, especially **today** and within the **past 7 days**.\n"
        "- Pay close attention to whether there was a **strong initial reaction** to any recent headline — and whether the move is continuing, pulling back, or setting up again.\n"
        "- The user is preparing to trade **tomorrow**, aiming for a **5–7% intraday profit**. The user usually sells same-day **unless strong continuation is expected**.\n"
        "- For each recent news headline, check if the price **already reacted**:\n"
        "   - When did the **first spike** occur?\n"
        "   - Was the reaction full or partial?\n"
        "   - Is a **second wave** or continuation setup likely tomorrow?\n"
        "- If the news was released **before the most recent trading day’s close (15:30)**, assume it likely influenced the price already.\n"
        "- Be precise: say whether the move is already **priced in** or if there’s still potential.\n"
        "- For **A to S+ ranked news**, check if similar headlines came out earlier. If so, the market may have already priced it in.\n"
        "- Predict how the stock will behave **tomorrow**:\n"
        "   - Will it gap up/down?\n"
        "   - Will it surge in the morning or fade?\n"
        "   - What is the likely closing price range?\n"
        "- Clearly assess **wave timing and trading potential**:\n"
        "   - Is this Wave 1 (initial spike), Wave 2 (pullback), Wave 3 (continuation), or post-spike exhaustion?\n"
        "   - When was the first spike? What triggered it? How strong was it?\n"
        "   - Is price currently pulling back, consolidating, or resetting for a new move?\n"
        "   - Give guidance such as:\n"
        "     - 'The first spike occurred on [date]. Tomorrow may offer a second wave breakout.'\n"
        "     - 'No major reaction yet. Tomorrow may be the initial move.'\n"
        "     - 'Looks overextended. Watch for reversal or deeper pullback.'\n"

        "- Use technical indicators (RSI, MACD, MAs, candlesticks) to support or reject further upside.\n"
        "- Check if today’s close is near high/low to gauge momentum carryover.\n"
        "- Be alert to hot market themes (e.g. **Bitcoin, AI, semiconductors, lithium, etc**).\n"
        "- Explain **why volume surged**, if applicable: strong news? speculation? sympathy move?\n"
        "- Include **historical price table** for context on trend, resistance, and support zones.\n"

        "- For each headline, give:\n"
        "   - **Keyword: as guidance below - Rank: as guidance below**\n"
        "   - **Verdict**: Same as Rank, one of [S+, S, A+, A, A-, B, C, D, N/A]\n"
        "   - **Reason**: One sentence explaining the expected impact\n"
        "- Choose and analyze the **top 10 most impactful headlines** based on rank and relevance.\n"

        "- Conclude with a **concise summary and forecast for tomorrow**:\n"
        "   - Investment Recommendation: Buy / Hold / Sell\n"
        "   - Promising Score: (0–100) — based on news, technicals, and rebound potential\n"

        "- 🧠 News Impact Ranking:\n"
        "- For each top headline, assign a keyword and rank based on this table:\n"
        "  {\n"
        # S rank - strongest triggers
        "    'TOB / MBO': 'S',\n"

        # A+ rank - very strong positive
        "    '独占契約': 'A+',\n"
        "    '大型受注': 'A+',\n"
        "    '業績予想 上方修正': 'A+',\n"

        # A rank - strong positive
        "    '筆頭株主変更': 'A',\n"
        "    '黒字転換': 'A',\n"
        "    '新市場参入': 'A',\n"
        "    '新サービス発表': 'A',\n"
        "    '特許取得': 'A',\n"
        "    '新製品発表': 'A',\n"
        "    '事業拡大': 'A',\n"
        "    '買収': 'A',\n"

        # A- rank - technical signals
        "    'ゴールデンクロス': 'A-',\n"
        "    '±３σブレイク': 'A-',\n"
        "    'ボリンジャーバンド上抜け': 'A-',\n"
        "    'fisco注目': 'A-',\n"

        # B rank - moderate positive
        "    '中期経営計画': 'B',\n"
        "    '株式買戻し': 'B',\n"
        "    '特別利益': 'B',\n"
        "    '特別利益計上': 'B',\n"
        "    '株主優待増額': 'B',\n"
        "    '配当増額': 'B',\n"
        "    '販売契約': 'B',\n"
        "    '大量保有報告書': 'B',\n"
        "    'サプライズ決算': 'B',\n"
        "    '四半期サプライズ決算': 'B',\n"
        "    '増益': 'B',\n"
        "    '利益倍増': 'B',\n"
        "    '今期 業績予想 50%増益以上': 'B',\n"

        # C rank - negative or neutral
        "    '施設閉鎖': 'C',\n"
        "    '運営終了': 'C',\n"
        "    '事業報告': 'C',\n"
        "    '株式発行': 'C',\n"
        "    '赤字縮小': 'C',\n"

        # D rank - negative
        "    '減益': 'D',\n"
        "    '赤字転落': 'D',\n"
        "    '資本金変更': 'D',\n"
        "    '再掲IR': 'D',\n"
        "    '過去の材料再加熱': 'D'\n"
        "  }\n"
        "\n"
        "- 🔧 Booster Instruction:\n"
        "  - Define **hot/trending sectors**: AI, Web3, semiconductors, space, quantum computing, medical tech, robotics, FinTech, crypto, mobility, biotech, data centers, EV, hydrogen.\n"
        "  - For certain keywords, **boost to 'S' or 'A+' only if strong value is clear**:\n"
        "    • 'TOB / MBO': Boost to S+ if offer has a large premium, from a notable acquirer, or leads to immediate price gap-up with strong volume.\n"
        "    • '筆頭株主変更': Boost to S if new shareholder is a large institutional investor, foreign fund, or strategic partner.\n"
        "    • '新市場参入': Boost to S only if into a **hot/trending sector** with exclusivity or growth potential.\n"
        "    • '特許取得': Boost to S only if it enables a **monopoly or first-mover advantage in hot/trending fields**.\n"
        "    • '新サービス発表': Boost to S only if it’s a **game-changer or disruptor in hot/trending sectors**.\n"
        "    • '買収': Boost to S only if it’s **accretive, cross-border, or synergistic in hot/trending markets**.\n"
        "    • '中期経営計画': Boost to A+ or S only if plan includes **aggressive growth, global expansion, or restructuring in promising areas**.\n"
        "    • '特別利益': Boost to A+ only if it **significantly improves EPS or changes valuation metrics**.\n"
        "    • '事業拡大': Boost to A+ or S only if it’s into **large-scale, strategic, or hot/trending sectors**.\n"
        "    • '今期 業績予想 50%増益以上': Boost to A+ if forecast is **unexpected, from a low-float/small-cap stock, or paired with strong catalysts**\n"
        "    • '独占契約': Boost to S only if partner is **top-tier or market scale is large**.\n"
        "    • '大型受注': Boost to S only if it’s from a **major client or long-term contract**.\n"
        "    • '黒字転換': Boost to S only if it leads to **sustained profitability or likely leads to strong market reaction**.\n"
        "    • 'サプライズ決算': Boost to S only if it's confirmed that results **exceed expectations significantly**.\n"
        "    • '四半期サプライズ決算': Boost to S only if it's confirmed that **quarterly results strongly surprise**.\n"
        "    • '増益': Boost to S if **profit growth exceeds 50% and is unexpected**, A if **between 30–50% with positive sentiment or low float**.\n"
        "    • '利益倍増': Boost to A if **2倍以上** and supported by **strong catalyst** (e.g. restructuring, new business, or entry into hot/trending sectors).\n"
        "    • 'fisco注目': Boost to A+ if stock already trending or backed by strong catalyst.\n"
        "    • '大量保有報告書': Boost to A if new investor is a known activist fund, foreign investor, or signals strategic interest.\n"

        "- 🚨 **KEY PATTERN: Re-Spike After Pullback**\n"
        "- Detect this setup:\n"
        "   - A **spike (one or multiple)** triggered by a **strong catalyst** (e.g. news/IR)\n"
        "   - Followed by a **pullback** (price decline or consolidation)\n"
        "   - Later, watch for a **second/third spike** — which may occur *without* new material news\n"
        "- Always **highlight in the summary** and explain:\n"
        "   - What is the current pattern stage? (e.g. initial spike → pullback → re-spike, or not spike yet)\n"
        "   - Is it a **momentum reset**, **technical rebound**, or **speculative move**?\n"
        "   - Is it **safe to re-enter**, or **too volatile/exhausted**?\n"
        "   - Confirm whether the original spike was based on a **strong catalyst**\n"
        "- Assign a keyword in headline evaluation:\n"
        "   - **Keyword: Likely Re-spike — Rank: S**\n"
        "- This is a **high-priority pattern** — always include it in the final recommendation if present.\n"

        "- If a move is likely, briefly describe:\n"
        "  - Expected gap direction\n"
        "  - Morning reaction\n"
        "  - Likely closing range\n"
        "- Comment explicitly on wave stage and wave timing.\n"

        "### Output Format:\n"
        "Headline List:\n"
        "1. **[Headline text here]**\n"
        "   - **Keyword: ... - Rank: ...**\n"
        "   - **Verdict: ...**\n"
        "   - **Reason: ...**\n"
        "(Repeat for each headline)\n\n"

        "Summary:\n"
        "- 📰 **News Evaluation**: [Short reasoning about which headlines matter and how price responded]\n"
        "- 📊 **Signal/Technical Analysis**: [Do indicators support continuation or exhaustion?]\n"
        "- 📈 **Trend & Rebound Context**: [Explain any pullbacks, potential rebound zones, or exhaustion. Also state if re-spike pattern was detected — and if not, why not (e.g. no prior strong spike, new news exists, weak volume, etc).]\n"
        "- Final Comment: [Your overall sentiment for tomorrow's trade setup]\n\n"
        "- Investment Recommendation: Buy / Hold / Sell\n"
        "- Promising Score: (0–100) [estimates how likely the stock will spike in the coming days, based on **how strong and recent the news are**, the **most impactful keyword**, its **ranking**, and any **supporting signals**]\n"
        "- **Spiked**: [Yes / No] — indicates whether a recent spike has occurred.\n"
        "- **Spike next**: (0–100) — estimates the likelihood of a near-term spike or re-spike, based on recent price action, volume patterns, and catalyst strength.\n"
        "- News Rank Summary: [Overall impact levels of top news]\n"
        "- 📅 **Tomorrow's Action Expectation**: Gap direction, morning behavior, and closing tendency\n"
        "- 📊 **Wave Stage**: [Wave 1 / Wave 2 / Wave 3 / Overextended / Not started]\n"
        "- 🕒 **First Spike Summary**: [Did it happen? If it did: when? On what news? How strong?]\n"
        "- ⏳ **Entry Guidance**: [E.g. 'Wait for second spike', 'Buy dip on rebound', 'Risk of exhaustion — wait']\n"
    )
    # print(f"prompt={prompt}")

    try:
        response = openai.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        reply = response.choices[0].message.content.strip()
        print(f"====ticker={ticker}, reply={reply}")

        recommendation, promising_score = extract_recommendation_and_score(reply)

        spiked, spike_next = extract_spiked_and_spike_next(reply)

        impacts = extract_headline_impacts(reply)
        # print(f"====impacts={impacts}")
        summary_match = re.search(r"Summary:\s*(.*?)\s*(- Investment|$)", reply, re.DOTALL)
        summary = summary_match.group(1).strip() if summary_match else ""

        highest_impact_keyword = None
        highest_impact_rank = None
        highest_impact_keyword, highest_impact_rank = extract_highest_ranked_impact(reply)
        # print(f"====highest_impact_keyword, highest_impact_rank={highest_impact_keyword, highest_impact_rank}")

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
        # print(f"====top_enriched_news={top_enriched_news}")

        volume_info.reasoning = summary
        volume_info.recommendation = recommendation
        volume_info.promising_score = promising_score
        volume_info.spiked = spiked
        volume_info.spike_next = spike_next
        volume_info.highest_impact_keyword = highest_impact_keyword
        volume_info.highest_impact_rank = highest_impact_rank
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
            # "downtrend": downtrend_info,
            # "uptrend": uptrend_info,
            # "drop_from_high_pct": drop_from_high_pct,
            # "rebound_from_low_pct": rebound_from_low_pct,
            # "highest_price": highest_price,
            # "lowest_price": lowest_price,
            "momentum_score": momentum_result["momentum_score"],
            "momentum_confidence": momentum_result["momentum_confidence"],
            "momentum_signals": momentum_result["momentum_signals"],
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
        "fisco注目"
    }

    for keyword, rank in matches:
        keyword = keyword.strip()
        rank = rank.strip()
        current_rank_value = rank_value(rank)

        # Skip if keyword is in skip list
        if keyword in skip_keywords:
            continue

        # Prioritize high-confidence "re-spike"
        if "re-spike" in keyword.lower() and current_rank_value <= rank_value("B"):
            return keyword, rank  # return immediately

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
        current_price, high, low = fetch_intraday_prices(ticker)
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