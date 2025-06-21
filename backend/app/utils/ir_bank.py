# scrapers/irbank.py

import httpx
from bs4 import BeautifulSoup
import re
from typing import Optional

def get_irbank_code(ticker: str) -> Optional[str]:
    """Get IRBank company code (e.g., 'E02144') from ticker."""
    try:
        url = f"https://irbank.net/{ticker}"
        resp = httpx.get(url, follow_redirects=True, timeout=10)
        if resp.status_code != 200:
            print(f"⚠️ Failed to fetch IRBank redirect for {ticker}")
            return None

        # Final URL will be something like https://irbank.net/E02144
        final_url = str(resp.url)
        match = re.search(r"irbank\.net/([A-Z0-9]+)", final_url)
        if match:
            return match.group(1)
        else:
            print("⚠️ IRBank code not found in redirect URL.")
            return None
    except Exception as e:
        print(f"❌ Error getting IRBank code for {ticker}: {e}")
        return None


def fetch_debt_ratio(ticker: str) -> Optional[float]:
    """Fetch 有利子負債比率 (debt ratio) from IRBank."""
    try:
        code = get_irbank_code(ticker)
        print(f"====code={code}")
        if not code:
            return None

        url = f"https://irbank.net/{code}/results"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "ja,en;q=0.9",
        }
        resp = httpx.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        print(f"====soup length={len(soup.prettify())}")
        print(soup.prettify()[:3000])

        # Find the row containing 有利子負債比率
        rows = soup.select("table > tr")
        for row in rows:
            if "有利子負債比率" in row.text:
                cells = row.find_all("td")
                if len(cells) >= 2:
                    value = cells[1].get_text(strip=True)
                    return parse_percentage(value)
        print(f"⚠️ 有利子負債比率 not found for {ticker}")
        return None

    except Exception as e:
        print(f"❌ Error fetching debt ratio for {ticker}: {e}")
        return None


def parse_percentage(text: str) -> float:
    """Convert '123.4%' to 123.4"""
    try:
        return float(text.replace("%", "").replace(",", "").strip())
    except:
        return 0.0
