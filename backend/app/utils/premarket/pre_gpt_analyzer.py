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

from app.utils.shortterm.price_updater import fetch_and_save_price_history
from app.utils.shortterm.save_shortterm_analysis_signal import save_shortterm_analysis_signal
from .calculate_momentum_score import calculate_momentum_score
from .uptrend_detector import get_uptrend_analysis, normalize_uptrend_for_json
from .downtrend_detector import get_downtrend_analysis, normalize_downtrend_for_json
from app.utils.shortterm.moneyflow_history import fetch_daily_money_flow_history, parse_volume, save_daily_money_flows
from app.utils.shortterm.volume_surge_scraper import fetch_intraday_prices
from app.utils.shortterm.volume_5d_average_updater import update_avg_volume_for_ticker
from app.utils.shortterm.moneyflow_5d_average_updater import update_avg_money_flow_for_ticker
from app.models import AverageMoneyFlow, AverageVolume, DailyPrice, VolumeSnapshot, ShortTermAnalysisSignal
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
    now = datetime.now(timezone.utc)

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

    jst = timezone(timedelta(hours=9))
    now_jst = now.astimezone(jst)
    date_str = now_jst.date().isoformat()
    latest_trading_day = get_latest_trading_day(db)
    if is_market_hours(now_jst, latest_trading_day):
        volume_info_ = get_intraday_volume_info_for_ticker(db, ticker)
        volume_summary = (
            f"📊 [Intraday]\n"
            f"Ticker: {volume_info_['ticker']}\n"
            f"Name: {volume_info_['name']}\n"
            f"Current Price: {volume_info_['current_price']} JPY\n"
            f"Volume Surge: {volume_info_['volume_rate']:.2f}x\n"
            f"Money Flow: {volume_info_['money_flow_rate']:.2f}x\n"
            f"Detected At: {now_jst.isoformat()}\n"
        )
    else:
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
        f"You are a Japanese market expert AI providing a **pre-market outlook for stock {ticker}** — to support a trade decision for **tomorrow's trading session**.\n\n"
        f"Today is {date_str}, time: {now_jst}. Latest trading day: {latest_trading_day}, time: 15:30:00.\n"
        f"### Volume and Price Activity:\n{volume_summary}\n"
        f"### Price History (Past Days):\n{price_history_str}\n"
        f"### Trend Summary (Up/Down Movements):\n{trend_summary}\n"
        f"### Momentum Signals Summary:\n{momentum_summary}\n"
        f"### Technical Indicators (for reference only):\n{tech_summary}\n"
        f"### Recent News Headlines (past 7 days, timestamp included):\n"
        + "\n".join([f"{i+1}. {hl}" for i, hl in enumerate(headlines)]) +
        "\n\n"

        "### Instructions:\n"
        "- Focus primarily on **recent impactful news**, including **today and the past 7 days**.\n"
        "- Pay special attention to whether there was a **strong initial reaction** to any recent headline — and whether the move is still continuing, pulling back, or setting up again.\n"
        "- The user is preparing to trade **tomorrow**, aiming to capture a **5–7% intraday profit**. The user usually sells same-day **unless very strong continuation is likely**.\n"
        "- Check if price has already reacted to **any recent news**. If yes, evaluate:\n"
        "   - When did the first spike occur?\n"
        "   - Was the reaction full or partial?\n"
        "   - Is a **second wave** or continuation setup likely tomorrow?\n"
        "- If news was released **between 9:00 AM and 3:20 PM JST on weekdays (Monday–Friday)**, assume it has likely impacted the price already. Be precise about **whether the price move is already priced in or not**.\n"
        "- For **decisive news items**, check if similar news appeared earlier; if so, consider that the market might have priced it in.\n"
        "- Predict **how the stock will behave tomorrow**: gap up/down, morning surge/pullback, and **likely closing price range**.\n"
        "- Clearly assess **wave timing and trading potential**:\n"
        "   - Is the stock in Wave 1 (initial spike), Wave 2 (pullback), Wave 3 (continuation), or post-spike exhaustion?\n"
        "   - When was the **first spike**, what triggered it, and how strong was it?\n"
        "   - Is price **pulling back, consolidating, or resetting** for a new move?\n"
        "   - Comment clearly on entry potential, such as:\n"
        "     - 'The first spike occurred on [date]. Tomorrow may offer a second wave breakout.'\n"
        "     - 'No major reaction yet. Tomorrow may be the initial move.'\n"
        "     - 'This looks overextended. Watch for reversal or deeper pullback.'\n"
        "- Use technical indicators (RSI, MACD, moving averages, candle patterns) to support or reject further continuation.\n"
        "- Check if today's price closed near high/low to infer momentum carryover.\n"
        "- Be alert to **popular market themes** (e.g. Bitcoin, AI, semiconductors, lithium, stock splits, 株式発行, 資本金変更, 剰余金の処分, 業務提携).\n"
        "- Explain **why volume surged** if applicable — strong news? speculative interest? sector sympathy?\n"
        f"- From the headline list, pick the **top {top_n} news items most likely to influence tomorrow’s trade**.\n"
        "- Include historical price table to help reason about trend & support/resistance zones.\n"
        "- For each headline, give:\n"
        "   - **Verdict**: One of [Decisive, Great, Good, Neutral, Bad]\n"
        "   - **Reason**: One sentence explaining the expected impact\n"
        "- Conclude with a concise summary and forecast for **tomorrow**:\n"
        "- Investment Recommendation: Buy / Hold / Sell\n"
        "- Promising Score: (0–100) based on **news**, **technical signals**, and **rebound potential**\n"
        "- News Impact Ranking: For each top news headline, assign a keyword and ranking from this ranking dictionary:\n"
        "  {\n"
        "    '黒字転換': 'S', 'Turn to profit': 'S', 'Profitability turnaround': 'S',\n"
        "    '業績予想 上方修正': 'S', 'Earnings forecast upward revision': 'S',\n"
        "    '四半期サプライズ決算': 'S', 'Quarterly earnings surprise': 'S',\n"
        "    '中期経営計画': 'S', 'Mid-term management plan': 'S', '上方修正': 'S',\n"
        "    'サプライズ決算': 'S', 'Surprise earnings report': 'S',\n"
        "    '今期 業績予想 50%増益以上': 'A to S', 'This fiscal year earnings forecast +50% or more': 'A to S',\n"
        "    '買収': 'A to S', 'Acquisition': 'A to S',\n"
        "    '新市場参入': 'A to A+', 'New market entry': 'A to A+',\n"
        "    '独占契約': 'A to A+', 'Exclusive contract': 'A to A+',\n"
        "    '大型受注': 'A to A+', 'Large order': 'A to A+', 'Large contract': 'A to A+',\n"
        "    '特許取得': 'A to A+', 'Patent acquisition': 'A to A+',\n"
        "    '株式買戻し': 'B to A', 'Share buyback': 'B to A',\n"
        "    '新製品発表': 'B to A', 'New product announcement': 'B to A',\n"
        "    '新サービス発表': 'B to A', 'New service launch': 'B to A',\n"
        "    '事業拡大': 'B to A+', 'Business expansion': 'B to A+',\n"
        "    '新ホテル開業': 'B', 'New hotel opening': 'B',\n"
        "    '株主優待増額': 'B', 'Increased shareholder benefit': 'B',\n"
        "    '配当増額': 'B', 'Dividend increase': 'B',\n"
        "    '事業報告': 'C', 'Business report': 'C',\n"
        "    '株式発行': 'C to D', 'Capital increase': 'C to D',\n"
        "    '資本金変更': 'C to D', 'Capital change': 'C to D',\n"
        "    '再掲IR': 'D', 'Reposted IR': 'D',\n"
        "    '過去の材料再加熱': 'D', 'Reheating old news': 'D'\n"
        "  }\n"
        "  Provide this as a list of headline text with its corresponding impact keyword and rank.\n"
        "- If expecting a move: describe **gap**, **morning action**, and **closing behavior** expected\n"
        "- Comment on **entry setup and wave timing explicitly**\n\n"

        "### Output Format:\n"
        "Headline List:\n"
        "1. **[Headline text here]**\n"
        "   - **Keyword: ... - Rank: ...**"
        "   - **Verdict: ...**\n"
        "   - **Reason: ...**\n"
        "(Repeat for each headline)\n\n"

        "Summary:\n"
        "- 📰 **News Evaluation**: [Short reasoning about which headlines matter and how price responded]\n"
        "- 📊 **Signal/Technical Analysis**: [Do indicators support continuation or exhaustion?]\n"
        "- 📈 **Trend & Rebound Context**: [Explain any pullbacks, potential rebound zones, or exhaustion]\n"
        "- Final Comment: [Your overall sentiment for tomorrow's trade setup]\n\n"
        "- Investment Recommendation: Buy / Hold / Sell\n"
        "- Promising Score: (0–100)\n"
        "- News Impact Ranking Summary: [Summarize the impact levels of the top news]\n"
        "- 📅 **Expected behavior tomorrow**: Gap direction, likely morning action, and closing range\n"
        "- 📊 **Wave Timing**: [Wave 1 / Wave 2 / Wave 3 / Overextended / Not started yet]\n"
        "- 🕒 **First Spike Summary**: [Did it happen? When? On what news? How strong?]\n"
        "- ⏳ **Tomorrow Entry Guidance**: [E.g. 'Wait for second spike', 'Buy dip on rebound', 'Risk of exhaustion — wait']\n"
    )
    # print(f"prompt={prompt}")

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
                top_enriched_news.append(item)

        volume_info.reasoning = summary
        volume_info.recommendation = recommendation
        volume_info.promising_score = promising_score
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

def rank_value(rank_str):
    rank_order = ["S", "A to S", "A to A+", "B to A", "B", "C", "C to D", "D", "Good", "Neutral", "Bad", "N/A"]
    # Return an index for rank, lower index means higher rank
    try:
        return rank_order.index(rank_str)
    except ValueError:
        return len(rank_order)  # lowest rank if unknown

def extract_highest_ranked_impact(text: str):
    # Pattern to match lines like:
    # - **Keyword: Quarterly earnings surprise - Rank: S**
    pattern = re.compile(r"\*\*Keyword:\s*(.+?)\s*-\s*Rank:\s*([A-Za-z0-9\s\+\-]+)\*\*", re.IGNORECASE)
    matches = pattern.findall(text)

    best_rank = None
    best_keyword = None

    for keyword, rank in matches:
        keyword = keyword.strip()
        rank = rank.strip()
        current_rank_value = rank_value(rank)
        if best_rank is None or current_rank_value < rank_value(best_rank):
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

def is_market_hours(now_jst: datetime, latest_trading_day: datetime.date) -> bool:
    # Market open: 09:00, close: 15:30
    market_close_time = datetime.combine(latest_trading_day, time(15, 30), tzinfo=now_jst.tzinfo)
    return now_jst.date() == latest_trading_day and now_jst <= market_close_time

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