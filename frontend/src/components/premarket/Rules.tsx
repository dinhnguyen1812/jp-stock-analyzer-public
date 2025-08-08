import React, { useState } from "react";
import { Modal, Button, Tabs, Tab, Table } from "react-bootstrap";

const CORE_RULES = `
📈 Spike Entry Rule (Low-cap Hot Stocks)

1. Ideal Conditions:
🔥 Hot Theme or Good Catalyst (e.g. AI, biotech, M&A, etc.)
💰 High Trading Volume (≥ 10M)
🧢 Low Market Cap (≤ 300億円)
🚀 Recent Spike (strong upward move in last 1–2 days)

2. Strategy:
✅ Entry Timing:
📉 Wait for Pullback Completion, then enter on rebound.
📈 Or, buy early if price continues rising with strong volume (especially in first spike phase).

3. 📊 Position Sizing:
Buy in portions (e.g., scale in 1/3–1/2–full depending on confirmation).
Avoid overexposing to a single volatile stock.

4. Optional Filters:
🧠 Positive GPT news verdict or institutional interest
📅 Spike linked to same-day or next-day news
🐳 Presence of large volume at low prices (support zone)
`

const TRADING_RULES = `
📊 Trading Rules

🔍 1. Scan & Analyze Guidance (Night Before or Premarket)
- ❌ Remove all previously ⭐️ starred stocks.
- 📈 Scan Volume Surge (VS):
  - Criteria: surge >= 1, price <= 300
  - Pages: 1–10
- 📰 Scan News:
  - Criteria: price <= 500
  - Pages: 1–40
- ⭐️ Star the stocks with good or decisive news.
- 🧠 Analyze starred stocks using GPT-based evaluation.
- 👀 Manually inspect chart and volume of each starred stock to pick 3 most promising stocks.
- 👀 Ask ChatGPT for opinion: Is the news fresh? How likely does it impact the certain stocks?
- All-in stocks: 

🌊 2. Aim for the Wave 1 (Pre-order if very strong news) else wait for wave 2
- Look for stocks with:
  - 📰 Decisive news released after 3:30pm
  - 📉 Price hasn't yet reacted to the news
  - ✅ Promising score (from news + chart + potential rebound) > 70

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

const ALLIN_GUIDANCE = `
🚀 All-In Stock Criteria & Guidance

🧠 Ideal All-In Setup:
- 🔻 Stock has been down / quiet for some time (no recent hype).
- 💰 黒字転換 (Turn to Profit): from big loss to solid profit.
  • Example: -8億 → +0.6億 modest, -7億 → +2億 = strong.
- 📈 業績上方修正 (Earnings Forecast Raised): large %, record level.
- 🆕 Good news is FRESH and not yet priced in (IR release after 15:30).
- 💹 High trading volume early, confirming market reaction.
- 📊 Clean chart: breakout from resistance or long base.
- 🔍 No dilution risk (no CB, 増資, or toxic debt).
- ⚡ Sector theme is hot or related news moving similar stocks.

🎯 Checklist Before Going All-In:
1. ✅ Strong surprise news (S/A+ rank).
2. ✅ No heavy resistance above.
3. ✅ No dilution risk.
4. ✅ Clean IR timing (not recycled).
5. ✅ Volume confirmation on spike.
6. ✅ Similar stocks moved (sector sympathy).
7. ✅ News + chart + volume = alignment.

❌ Don’t All-In If:
- 🚨 Already up 50%+ on low volume.
- ❓ Dilution risk / CB noted in docs.
- 📉 Weak breakout / fake spike pattern.
- 🧊 Market sentiment weak (broad drop).
- 😵 Overcrowded stock with FOMO jump-ins.

💡 Tip:
Use GPT to validate news freshness, technical strength, and dilution risks.
`;

const NewsImpactRankingTable = () => {
  const data = [
    {
      rank: "S",
      newsType: "黒字転換 (Turn to Profit)",
      details: "From deep loss? Clean profit? Margin?",
      impact: "+10–40% spike if surprise or large",
      example: "-8% → +0.6% modest; -700M → +200M = big spike",
    },
    {
      rank: "S",
      newsType: "業績予想 上方修正 (Earnings Up)",
      details: "% gain? EPS vs prior? Record profit?",
      impact: "+10–50% if large and unexpected",
      example: "OP doubled → record high = huge spike",
    },
    {
      rank: "S",
      newsType: "四半期サプライズ決算 (Earnings Surprise)",
      details: "2x/3x YoY/QoQ? Margin jump? New high?",
      impact: "+10–40%",
      example: "3Q OP 2.4x YoY = strong",
    },
    {
      rank: "S",
      newsType: "中期経営計画 + 上方修正",
      details: "Ambitious, clear numbers? EPS upgrades?",
      impact: "+10–30%",
      example: "Vision + guidance raise = catalyst",
    },
    {
      rank: "A+",
      newsType: "今期 業績予想 +50%↑ YoY",
      details: "Big YoY%? From good base? EPS revision too?",
      impact: "+5–25%",
      example: "今期91%増益へ = decent spike",
    },
    {
      rank: "A",
      newsType: "新市場参入 / 独占契約",
      details: "Sector hot? Realistic growth? Not priced in?",
      impact: "+5–20%",
      example: "New business in AI or crypto",
    },
    {
      rank: "A",
      newsType: "大型受注・契約発表",
      details: "With major partner? Value disclosed? Recurring?",
      impact: "+5–25%",
      example: "$100M deal with major firm",
    },
    {
      rank: "A-",
      newsType: "特許取得 (Patent)",
      details: "Useful? Sector hot? Market reaction?",
      impact: "+3–15%",
      example: "3D printing tech patent",
    },
    {
      rank: "B",
      newsType: "新製品・新サービス発表",
      details: "Market size? Pricing power? PR coverage?",
      impact: "+3–10%",
      example: "Smart device release",
    },
    {
      rank: "B",
      newsType: "株主優待・配当増額",
      details: "Regular or special? High yield?",
      impact: "+2–8%",
      example: "5% dividend hike",
    },
    {
      rank: "B",
      newsType: "新ホテル・新店舗展開",
      details: "Location? Brand strength? Expansion plan?",
      impact: "+2–7%",
      example: "Hotel opening in Sendai",
    },
    {
      rank: "C",
      newsType: "IR without earnings impact (事業報告)",
      details: "No number? No surprise?",
      impact: "~0–3%, fade possible",
      example: "New office, no big change",
    },
    {
      rank: "D",
      newsType: "再掲IR / 過去の材料再加熱",
      details: "Already known? Market priced in?",
      impact: "0% or drop",
      example: "“Reconfirming” past plan",
    },
  ];

  return (
    <Table striped bordered hover responsive>
      <thead>
        <tr>
          <th>Rank</th>
          <th>News Type</th>
          <th>Details to Check</th>
          <th>Likely Impact (Positive)</th>
          <th>Example</th>
        </tr>
      </thead>
      <tbody>
        {data.map(({ rank, newsType, details, impact, example }) => (
          <tr key={newsType}>
            <td><strong>{rank}</strong></td>
            <td>{newsType}</td>
            <td>{details}</td>
            <td>{impact}</td>
            <td>{example}</td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
};

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
            <Tab eventKey="core_rules" title="📊 Core Rules">
              <pre style={{ whiteSpace: "pre-wrap", padding: "1rem", margin: 0 }}>
                {CORE_RULES}
              </pre>
            </Tab>
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
            <Tab eventKey="newsranking" title="📈 News Impact Ranking">
              <NewsImpactRankingTable />
            </Tab>
            <Tab eventKey="allin" title="🚀 All-In Guidance">
              <pre style={{ whiteSpace: "pre-wrap", padding: "1rem", margin: 0 }}>
                {ALLIN_GUIDANCE}
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
