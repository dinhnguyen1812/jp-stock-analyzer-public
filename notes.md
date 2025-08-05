<!-- - Fix historical chart -->
<!-- - Fix component positioning -->
- Add "give expected price" function
- Scan to get undervalued stocks
Scan -> Save to db -> Query
```
🧰 Smart strategy
Start with a screener (like Yahoo! Finance Japan, TradingView, or your own script) and apply filters that match your investment thesis. For example:
> “Show me all TSE Prime stocks in the Retail sector with PER < 12 and ROE > 10%.”
That’ll shrink your universe from thousands to maybe a few dozen high-potential candidates.
```
```
Instead of focusing on all newly listed stocks, consider filtering for:
Strong earnings forecasts or ROE
Reasonable PER/PBR vs. industry
Sectors you understand well
Post-IPO stability (e.g. 1–3 months after listing)
You can track new listings on the JPX New Listings page, which includes market segment, offering price, and listing date.
```
- Add progress bar
- Add indicator explanation
<!-- - No price in real time indicator -->
<!-- - Add numbers to right vertical axis of chart -->

# Short term
## 6/26:
- Add ticker info (volume surge...) for GPT to decide relevant news
- Add endpoint where GPT provide explanation for volume surge
- Use the news with the info to ask GPT to verdict if it's time for make a move (still needs some extra information)

### UI
<!-- - Scan volume surge (options: surge_threshold, price_threshold, pages) => Get volume surge stocks (a list with information)
- Each row has a button: "Analyze" => Call the kabutan_news_analysis endpoint for that ticker -->
<!-- - Add endpoint to analyze a stocks (even not with volume surge)
- Add a column that mark (Buy-Hold-Sell) - Decide by GPT, a Promising score (0-100) - Decide by GPT, a column for Star - Mark by user
  - When scan: also analyze the stocks: reasoning, extract Buy-Hold-Sell from GPT advise, Promising score from GPT analysis, save to DB, shows them to UI
  - Show the last analysis (reasoning for volume surge and advise) if clicking "Show last analysis"
  - A seperate DB for Star (is there better approach): just ticker and star -->

<!-- - Add analysis signals to UI -->

<!-- - Add expected price based on current situation.
- Add endpoint to follow a ticker -> when input a number of stocks bought -> Save the info to db (price, number of stocks, date, relevant indicators and signals) -> when input this ticker (or something like "Ask about bought stocks") -> Get current situation, ask GPT if it's time to Buy more/Hold/Sell. Also add expected price based on current situation. -->

<!-- - Check database:
  - Daily price OK
  - Volume history (for average) OK
  - Moneyflow history (for average) OK -->
<!-- - Get news (from multiple categories), take those with more impacts -->
<!-- - Add Analyze starred stocks - button
- Add star option to Fetch -->
<!-- - Change breakout to using current price (not close price)
- Check breakout -->
<!-- - General yahoo news scan: add evaluate effect of the news to starred stocks -->
<!-- - Analyze　to be listed stocks?
- Add star option to Analyze a certain stock display
- Add trading journal
- Add buying feature -->

<!-- - Add table (SpikeScan) for spike 
  - keep one row for one ticker
  - ticker
    - if it's in VolumeSnapshot and VolumeSnapshot.detected_at >= open market time and volume_rate < 2x VolumeSnapshot.volume_rate -> skip
    - if it's already in SpikeScan and volume_rate <= 2x SpikeScan.volume_rate -> skip update
  - downtrend - update after one day
  - news - update after one hour
- Add fetch spike -->
<!-- - Highlight words in analyze -->
<!-- - Modify display in fetch spike -->
<!-- - Auto scan each 10 min with sound alert
- Include current price, current price / lowest and / highest -->
- Change auto scan from frontend to backend
- Reset some tables after 2 days
- Include industry in fetch VS and fetch Spike
- Enable analyze when there is not volume yet
<!-- - Auto gpt-4o analyze for ones with >60 score -->
<!-- - Add advice for Short Sell -->
- Pre-market:
  <!-- - Add analyze one ticker
  - Add analyze starred ticker -->
  <!-- - Show watchlist recommendation to Action / GPT -->
  <!-- - Fetch starred ticker -->
  <!-- - Show starred status if starred -->
  - Starred list in a csv file
  - Holdings list in a csv file
  - Accurate news
  <!-- - Add column: Is there good news -->
  - Scan news even with stocks that have not surged in volume
    - Add each component to the Scan Form
      - Add scan news for one ticker
    <!-- - Fix return for scan_news_for_ticker -->
  <!-- - Bring Holdings List here -->
  <!-- - Fix downtrend: 
    - 2743: there is no recent downtrend, but system says yes
    - include from_day and to_day in the model
    - get info from db
    - include from_day and to_day in the prompt -->
  <!-- - Ask GPT about decisive news -->
  <!-- - Show starred in fetch news -->
  <!-- - Add detect_recent_uptrend -->
    <!-- - Scan news:
      - Pass those repeat news -->
    <!-- - Pass calculated signals to gpt for analyzing -->
    - Scan news: If news has a similar news in the past -> Show both? Show the old one? Add description
- Analyze holdings list stocks:
  - Scan news (all kind)
  - Info when buying and now
  - Show volume rate, money flow rate to holdings list modal
- News:
  - 第三者割当による新株式の発行、業務提携、定款の一部変更、資本金及び資本準備金の額の減少、剰余金の処分、主要株主等の異動のお知らせ
  - 臨時株主総会の開催日時、開催場所及び付議議案に関するお知らせ
  - アドバンスクリエイト---2025年6月度の業績概要
  - GPT give bad/neutral but it actually made 30% rise
  - Should focus especially on today/yesterday/or weekend (if today is monday) news instead of all current news
  - ＦＤＫは商い伴い急騰、水素貯蔵タンク用の新材料を開発 => gpt give good, but it rise 22%
- Check volume spike + news
- Add today + yesterday high low close for analyzing
- Check if promising score is based on both technical signals and news (sometimes news alone could be great?)
- Add detect second spike

- Add PER/PBR... indicators to analyzer
- Add technical scanner:
- Add watchlist table