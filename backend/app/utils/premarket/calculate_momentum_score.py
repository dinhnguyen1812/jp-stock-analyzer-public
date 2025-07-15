def calculate_momentum_score(
    volume_snapshot,
    signal_data: dict,
    downtrend_info: dict,
    recent_prices: list[dict] = None  # optional for low-lows check
) -> dict:
    """
    Calculate momentum score, confidence level, and per-signal UI-friendly result.
    Returns:
        {
            "momentum_score": int,
            "momentum_confidence": str,
            "momentum_signals": List[Dict]  # for UI
        }
    """
    score = 0
    signals = []
    price = volume_snapshot.current_price
    sma50 = signal_data.get("sma_50")
    macd_line = signal_data.get("macd_line")
    macd_signal = signal_data.get("macd_signal")
    macd_hist = signal_data.get("macd_hist", 0)
    rsi = signal_data.get("rsi", 0)
    bb_upper = signal_data.get("bb_upper")
    bb_price = signal_data.get("bb_current_price")

    # 1. Volume Rate
    vol_score = 0
    meaning = "High volume shows strong market interest"
    if volume_snapshot.volume_rate > 10:
        vol_score = 5
    elif volume_snapshot.volume_rate > 5:
        vol_score = 4
    elif volume_snapshot.volume_rate > 3:
        vol_score = 3
    signals.append({
        "label": "Volume Rate > 3 / 5 / 10",
        "score": vol_score,
        "passed": vol_score > 0,
        "meaning": meaning
    })
    score += vol_score

    # 2. Price vs SMA50
    sma_score = 0
    sma_label = "Price vs SMA50"
    if sma50:
        ratio = (price - sma50) / sma50
        if 0 < ratio <= 0.10:
            sma_score = 2
            meaning = "Breakout slightly above SMA50 – ideal zone"
        elif 0.10 < ratio <= 0.15:
            sma_score = 1
            meaning = "Breakout moderately above SMA50 – still acceptable"
        elif 0.15 < ratio <= 0.20:
            sma_score = 0
            meaning = "Breakout extended – may consolidate or pull back"
        elif ratio > 0.20:
            sma_score = -1
            meaning = "Overextended from trend – may pull back"
        else:
            meaning = "Below or at SMA50"
    else:
        meaning = "No SMA50 data"
    score += sma_score
    signals.append({
        "label": sma_label,
        "score": sma_score,
        "passed": sma_score > 0,
        "meaning": meaning
    })

    # 3. Money Flow Rate
    mfr_score = 0
    mfr = volume_snapshot.money_flow_rate
    if mfr > 5:
        mfr_score = 2
        passed = True
        meaning = "Strong money inflow supporting the move"
    else:
        passed = False
        meaning = "Money flow not high"
    score += mfr_score
    signals.append({
        "label": "Money Flow Rate > 5",
        "score": mfr_score,
        "passed": passed,
        "meaning": meaning
    })

    # 4. MACD Histogram rising
    macd_hist_score = 1 if macd_hist > 0 else 0
    score += macd_hist_score
    signals.append({
        "label": "MACD Histogram > 0 and rising",
        "score": macd_hist_score,
        "passed": macd_hist > 0,
        "meaning": "Momentum is building up"
    })

    # 5. MACD Bullish Crossover
    macd_cross_score = 0
    if macd_line is not None and macd_signal is not None:
        if macd_line > macd_signal:
            macd_cross_score = 2
            passed = True
            meaning = "MACD line crossed above signal – bullish momentum"
        else:
            passed = False
            meaning = "No bullish crossover"
    else:
        passed = False
        meaning = "No MACD data"
    score += macd_cross_score
    signals.append({
        "label": "MACD Bullish Crossover",
        "score": macd_cross_score,
        "passed": passed,
        "meaning": meaning
    })

    # 6. RSI
    rsi_score = 0
    if 60 <= rsi <= 70:
        rsi_score = 1
        meaning = "RSI rising into strength zone"
    elif rsi > 70:
        # You can later check for falling via trend if needed
        rsi_score = 2
        meaning = "RSI in overbought zone and rising"
    elif rsi < 40:
        rsi_score = -1
        meaning = "Bearish pressure likely"
    else:
        meaning = "Neutral RSI"
    score += rsi_score
    signals.append({
        "label": "RSI",
        "score": rsi_score,
        "passed": rsi_score > 0,
        "meaning": meaning
    })

    # 7. Bollinger Band breakout
    bb_score = 0
    if bb_upper and bb_price and bb_price > bb_upper:
        # Optional: check candle body size for big green candle in frontend
        bb_score = 1
        passed = True
        meaning = "Price broke above BB – possible breakout"
    else:
        passed = False
        meaning = "Price still inside Bollinger Bands"
    score += bb_score
    signals.append({
        "label": "BB Breakout",
        "score": bb_score,
        "passed": passed,
        "meaning": meaning
    })

    # 8. No lower lows in last 5 days
    lows_score = 0
    passed = False
    meaning = "Insufficient data to check lower lows"
    if recent_prices and len(recent_prices) >= 5:
        last_5_lows = [p["low"] for p in reversed(recent_prices[:5])]
        if all(last_5_lows[i] >= last_5_lows[i - 1] for i in range(1, 5)):
            lows_score = 1
            passed = True
            meaning = "No lower lows – price structure improving"
        else:
            meaning = "Price made lower lows recently"
    score += lows_score
    signals.append({
        "label": "No Lower Lows (5d)",
        "score": lows_score,
        "passed": passed,
        "meaning": meaning
    })

    # Confidence
    if score >= 13:
        confidence = "🔥 Very strong setup"
    elif score >= 9:
        confidence = "✅ Good setup"
    elif score >= 6:
        confidence = "⚠️ Medium-risk"
    else:
        confidence = "❌ Weak / No trade"


    return {
        "momentum_score": score,
        "momentum_confidence": confidence,
        "momentum_signals": signals
    }
