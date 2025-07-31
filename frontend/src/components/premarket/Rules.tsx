import React, { useState } from "react";
import { Modal, Button, Tabs, Tab } from "react-bootstrap";

const TRADING_RULES = `
📊 Trading Rules

🔍 1. Scan & Analyze Guidance (Night Before or Premarket)
- ❌ Remove all previously ⭐️ starred stocks.
- 📈 Scan Volume Surge (VS):
  - Criteria: surge >= 2, price <= 300
  - Pages: 1–5
- 📰 Scan News:
  - Criteria: price <= 1000
  - Pages: 1–40
- ⭐️ Star the stocks with good or decisive news.
- 🧠 Analyze starred stocks using GPT-based evaluation.
- 👀 Manually inspect chart and volume of each starred stock to pick 3 most promising stocks.
- 👀 Ask ChatGPT for opinion: Is the news fresh? How likely does it impact the certain stocks?

🌊 2. Aim for the Wave 1 (Pre-order if very strong news) else wait for wave 2
- Look for stocks with:
  - 📰 Decisive news released after 3:30pm
  - 📉 Price hasn't yet reacted to the news
  - ✅ Promising score (from news + chart + potential rebound)

🚨 3. Market Open Guidance (09:00)
- Focus on the 3 selected stocks.
- 📈 If price immediately moves upward, buy early.
- ⚠️ Avoid buying if price is shaking/volatile.
- 🕒 Wait until price stabilizes before entering.

💰 4. Sell Guidance
- 🟢 If it's a Wave 1 (news-based spike):
  - OK to wait for peak.
  - 📌 Sell when price meets your expectation.
- 🔴 If it's post-Wave 1 (likely profit-taking phase):
  - 📉 Sell quickly, especially on early spikes.
`;

const PREORDER_GUIDANCE = `
🕒 When to Make Pre-Orders

📅 Night Before (18:00–23:59)
- Place after market close when news is released.
- Useful for reacting to good IR/news ahead of others.

🕗 Early Morning (7:00–8:59)
- Adjust if ranking/sentiment/news changes by morning.
- Ideal for reacting to premarket scans.

🛒 How to Make Pre-Orders

✅ Option 1: Market Order (成行)
- Use if: You must enter at open, regardless of price.
- Risk: High opening price ("寄り天" = open is the day's high).
- Tip: Use only if the stock isn’t expected to gap too much or has room to run.

✅ Option 2: Limit Order (指値)
- Use if: You want to buy only below a set price.
- Tip: Set limit slightly above previous close or technical support.

🧠 Rule: Priority goes to the highest bid.
  • If multiple buyers set the same price, the earlier order gets priority.
  • But a later order with a higher price will always be matched first.

✅ Option 3: Conditional Orders
- Example: 逆指値 (stop order) + 指値 (limit to prevent overpaying)
- Useful to enter only if breakout is confirmed, e.g., price > yesterday’s high.
`;

const WAVE_RULES = `
🔁 First & Second Wave Overview

✅ First Wave (Market Open)
- Often the strongest price spike.
- Driven by retail buyers, preorders, algorithms, and gap-up momentum.
- Fast, big move but can be risky and unpredictable.

📉 Second Wave (After Pullback)
- Usually happens between 9:15–10:30 or midday.
- Requires dip-buying or new buyers entering after confirmation.
- More stable entry but may not always occur.

📊 When is Second Wave Likely Stronger?
- First wave faces strong profit-taking but news remains strong.
- Pullback has high volume and support holds.
- Consolidation with rising volume after dip.
- News or ranking re-circulates, attracting buyers again.

🧠 What to Watch to Predict Second Wave
1. News Quality: Is the news impactful and not fully priced in?
2. Volume Behavior:  
 - High volume in first wave  
 - Healthy (decreasing) volume during pullback  
 - Volume picking up again for second wave  
3. Candlestick Patterns: Bullish flags, support bounces, long wick recovery.
4. News Re-circulation: Stock appears again in rankings/news.

💡 Strategy Tips
- Don’t chase the first wave blindly.
- Watch price action 9:00–9:05; buy on pullback near support (VWAP, EMA).
- Use tight stop-loss.
- Ride the second wave if it forms.
`;

type RulesProps = {
  buttonLabel?: string;
  buttonSize?: "sm" | "lg";
  variant?: string; // react-bootstrap variant
  className?: string;
};

const Rules: React.FC<RulesProps> = ({
  buttonLabel = "📘 View Trading Rules",
  buttonSize = "sm",
  variant = "info",
  className,
}) => {
  const [show, setShow] = useState(false);
  const [key, setKey] = useState<string>("rules");

  return (
    <>
      <Button
        variant={variant}
        size={buttonSize}
        className={className}
        onClick={() => setShow(true)}
      >
        {buttonLabel}
      </Button>

      <Modal show={show} onHide={() => setShow(false)} centered size="xl">
        <Modal.Header closeButton>
          <Modal.Title>Trading Strategy & Guidance</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Tabs activeKey={key} onSelect={(k) => setKey(k || "rules")} id="rules-tabs">
            <Tab eventKey="rules" title="📊 Trading Rules">
              <pre style={{ whiteSpace: "pre-wrap", padding: "1rem", margin: 0 }}>
                {TRADING_RULES}
              </pre>
            </Tab>
            <Tab eventKey="preorder" title="🕒 Pre-Order Guidance">
              <pre style={{ whiteSpace: "pre-wrap", padding: "1rem", margin: 0 }}>
                {PREORDER_GUIDANCE}
              </pre>
            </Tab>
            <Tab eventKey="waves" title="🌊 Wave Insights">
              <pre style={{ whiteSpace: "pre-wrap", padding: "1rem", margin: 0 }}>
                {WAVE_RULES}
              </pre>
            </Tab>
          </Tabs>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShow(false)}>
            Close
          </Button>
        </Modal.Footer>
      </Modal>
    </>
  );
};

export default Rules;
