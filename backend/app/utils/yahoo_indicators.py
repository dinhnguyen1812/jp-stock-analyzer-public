import httpx
from bs4 import BeautifulSoup
import json
import re
from app.utils.jpx_debt_ratio import fetch_debt_ratio_ir_bank

def fetch_current_indicators(ticker: str):
    debt_ratio = fetch_debt_ratio_ir_bank(ticker)

    url = f"https://finance.yahoo.co.jp/quote/{ticker}.T"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept-Language": "ja,en;q=0.9",
    }

    try:
        response = httpx.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        # Extract current real-time price from visible <span>
        current_price_span = soup.select_one("span.StyledNumber__value__3rXW")
        current_price = to_float(current_price_span.text if current_price_span else None)


        # Find the <script> tag containing embedded financial JSON
        script_tag = next((s for s in soup.find_all("script") if "referenceIndex" in s.text), None)
        if not script_tag or not script_tag.string:
            print("⚠️ Embedded financial JSON not found.")
            return None

        # Extract `referenceIndex` section
        ref_match = re.search(
            r'"referenceIndex"\s*:\s*({.*?})\s*,\s*"marginTransactionInfo"', script_tag.string
        )
        if not ref_match:
            print("⚠️ Could not parse referenceIndex JSON block.")
            return None
        reference_index = json.loads(ref_match.group(1))

        # Extract `mainStocksPriceBoard` section
        board_match = re.search(
            r'"mainStocksPriceBoard"\s*:\s*({.*?})\s*,\s*"mainIndicatorDetail"', script_tag.string
        )
        if not board_match:
            print("⚠️ Could not parse mainStocksPriceBoard JSON block.")
            return None
        stock_board = json.loads(board_match.group(1))

        price_board = stock_board.get("priceBoard", {})
        industry_board = price_board.get("industry", {})

        return {
            "ticker": ticker,
            "name": price_board.get("name", ""),
            "current_price": current_price,
            "market": price_board.get("marketName", ""),
            "industry": industry_board.get("industryName", ""),
            "min_price": to_float(reference_index.get("minPurchasePrice")),
            "dividend_yield": to_float(reference_index.get("shareDividendYield")),
            "per": to_float(reference_index.get("per")),
            "pbr": to_float(reference_index.get("pbr")),
            "eps": to_float(reference_index.get("eps")),
            "bps": to_float(reference_index.get("bps")),
            "roe": to_float(reference_index.get("roe")),
            "market_cap": to_float(reference_index.get("totalPrice")),
            "debt_ratio": debt_ratio,
        }

    except Exception as e:
        print(f"❌ Error fetching Yahoo Finance data for {ticker}: {e}")
        return None

def to_float(val):
    try:
        return float(str(val).replace(",", "").replace("%", "").strip())
    except (ValueError, AttributeError):
        return 0.0
