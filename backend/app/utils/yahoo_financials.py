import httpx
from bs4 import BeautifulSoup
import json
import re

def scrape_yahoo_financials(ticker: str):
    url = f"https://finance.yahoo.co.jp/quote/{ticker}.T"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept-Language": "ja,en;q=0.9",
    }

    try:
        resp = httpx.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")

        # Extract title as fallback name
        title_tag = soup.find("title")
        fallback_name = title_tag.get_text(strip=True).split("【")[0].replace("(株)", "").strip() if title_tag else ""

        # Search for embedded JSON (with referenceIndex and mainStocksPriceBoard)
        json_script = next((s for s in soup.find_all("script") if "referenceIndex" in s.text), None)

        if not json_script or not json_script.string:
            print("⚠️ Could not find embedded financial JSON")
            return None

        # Extract only the referenceIndex JSON block
        match = re.search(r'"referenceIndex":({.*?})\s*,\s*"marginTransactionInfo":', json_script.string)
        if not match:
            print("⚠️ Could not extract referenceIndex JSON")
            return None

        data = json.loads(match.group(1))

        return {
            "ticker": ticker,
            "name": fallback_name,
            # "market": data_.get("priceBoard", {}).get("marketName", ""),
            "price": safe_float(data.get("minPurchasePrice")),
            "per": safe_float(data.get("per")),
            "pbr": safe_float(data.get("pbr")),
            "eps": safe_float(data.get("eps")),
            "roe": safe_float(data.get("roe")),
            "market_cap": safe_float(data.get("totalPrice")),
        }

    except Exception as e:
        print(f"❌ Error scraping Yahoo Finance page for {ticker}: {e}")
        return None

def safe_float(val):
    try:
        return float(val.replace(",", "").replace("%", "").strip())
    except (ValueError, AttributeError):
        return 0.0
