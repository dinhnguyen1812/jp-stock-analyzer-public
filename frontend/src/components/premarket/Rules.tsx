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
📌 Do
Strong news → Multiple spikes
Pattern: 連続 S高 → then S安 → goes flat (not near S安) → spikes again.
All MA go flat.
Lower high -> bearish
Higher low -> bullish
Look at volume surge
✔ Trade normally for 1–3 days during the flat phase.
Ex: Marusho Hotta, Applink (drop → S高), Kimono (drop → +20%), CAICAD, Defconsulting, Wilson

Strong news → End of parabolic run, then flat 2–3 days
✔ Often still has energy for another move.
Ex: Brightpath Biotech

Strong news → Likely continuation in coming days
✔ Momentum usually carries.
Ex: Anges, Temona, Astra Group

Strong news → Ends day near high
✔ Can go higher next day, but only enter if news is very strong.
Ex: Appbank

Strong news → Pullback → Rise
✔ Possible entry, but small size.
⚠ Risky: can drop hard if momentum fails.

Big Drop Today → Possible Spike Tomorrow
⚠ Often short-lived, drops again after rebound.

📌 Don’t
Chase the first spike
Entering at the top of the initial move usually = instant loss.
Ex: S Science, Quantum Solution, Kidwell

Never use Market Order (成行)
⚠ Too risky → rarely get good entry price → usually falls right after you buy.
`;

const MANUAL = `
Scan news once → Analyze those with good news (gpt-4o)
Scan flat stocks → Check watchlist → Remove bad ones → Analyze watchlist (gpt-3.5) - to see more information like volume,...
Fetch → Analyze further (gpt-4o)
Star promising ones to keep them pinned
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

const REFERENCES = `
3541: 農業総合研究所 x2: Buy the rumor, sell the news. Rised 90% before the actual news (actually quite good: Q3 earnings showing profit up 2.4–2.5x)
2134: 北浜ＣＰ x5: Funding usage, Multiple technical signals, reduction in stakes
6731: Pixela x3: 主要株主及び主要株主である筆頭株主の異動に関するお知らせpdf
6029: Artra group x1.5
7603: Mac house x6: 暗号資産
5985: Suncall x2.5: Data center
7111: INEST x2: new mid-term business plan + technical
3664: mobcast x2: technical
5255: monstarlab x3.5: strong fundamental: AI
8105: Horita Marusho x9: foreign investor entry
7615: 京都友禅ＨＤ x3.5: 黒転 -26.5％→6.8％
2743: pixel x2: technical, after that data center news did not affect because priced in?
2586: fruta fruta x2.5: new products
3777: 環境フレンド x2: new products + partnership
5721: S Science x4: 
6573: Agail x2.5: business expansion Tiktok + bitcoin
3624: Axel M x2: technical
7571: Yamano holding x2: technical
9973: Kozo HD x2.5: UK franchise partnership
2330: Forside x2: 今期経常を2.4倍上方修正
3845: アイフリークモバイルx1.5: 黒字浮上+technical
8746: unbanked x2: Acquisition 子会社
3350: メタプラネット x4.5: Bitcoin
2158: Fronteo x2.5: Cancer drug research
3936: Globalway x3: technical
2321: ソフトフロン x2.5: AI data center
6659: Medialinks x2: technical
4586: メドレックス x2: technical (赤字拡大？)
4594: ブライトパス・バイオ x2: orphan drug
6993: 大黒屋ホールディングス x4.5: technical
3671: ソフトマックス x2: AI
6786: RVH x2: technical
1844: 大盛工業 x2: technical
288A: ラクサス x2: technical
7694: いつも x2.5: Tiktok shop
3077: ホリイフードサービス x3: 黒字浮上 + 業務連携
5618: ナイル x2: technical
155A: 情報戦略テクノロジー x2: AI
3985: Temona S高: bitcoin mining machine
3823: TWHD S高: partner with Rakuten
x 4563: Anges: did not react with news: HGF 製造開始
6177: Appbank x4: AI service
8783: GFA x1.5: Stablecoin
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
            <Tab eventKey="rules" title="📊 EXP">
              <pre style={{ whiteSpace: "pre-wrap", padding: "1rem", margin: 0 }}>
                {TRADING_RULES}
              </pre>
            </Tab>
            <Tab eventKey="preorder" title="🕒 Manual">
              <pre style={{ whiteSpace: "pre-wrap", padding: "1rem", margin: 0 }}>
                {MANUAL}
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
                {REFERENCES}
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
