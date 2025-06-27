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
- Add endpoint to analyze a stocks (even not with volume surge)
- Add a column that mark (Buy-Hold-Sell) - Decide by GPT, a Promising score (0-100) - Decide by GPT, a column for Star - Mark by user
  - When scan: also analyze the stocks: reasoning, extract Buy-Hold-Sell from GPT advise, Promising score from GPT analysis, save to DB, shows them to UI
  - Show the last analysis (reasoning for volume surge and advise) if clicking "Show last analysis"
  - A seperate DB for Star (is there better approach): just ticker and star