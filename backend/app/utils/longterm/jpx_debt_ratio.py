from typing import Optional
from bs4 import BeautifulSoup
# from playwright.sync_api import sync_playwright

def fetch_debt_ratio_ir_bank(ticker: str) -> Optional[float]:
    pass
    # try:
    #     with sync_playwright() as p:
    #         browser = p.chromium.launch(headless=True)
    #         page = browser.new_page()

    #         # Step 1: Resolve code (e.g., E02144)
    #         page.goto(f"https://irbank.net/{ticker}", timeout=10000)
    #         code = page.url.split("/")[-1]

    #         # Step 2: Go to results page
    #         page.goto(f"https://irbank.net/{code}/results", timeout=10000)
    #         html = page.content()
    #         browser.close()

    #         # Step 3: Parse HTML with BeautifulSoup
    #         soup = BeautifulSoup(html, "html.parser")

    #         # Locate the section with heading 有利子負債比率
    #         debt_div = soup.find("div", {"id": "c_14"})
    #         if not debt_div:
    #             print(f"⚠️ Debt ratio section not found for {ticker}")
    #             return None

    #         # Get all <dd> elements under that section
    #         dd_tags = debt_div.find_all("dd")
    #         if not dd_tags:
    #             print(f"⚠️ No debt ratio values found for {ticker}")
    #             return None

    #         # Use the last value (latest year)
    #         latest_text = dd_tags[-1].get_text(strip=True)
    #         return parse_percentage(latest_text)

    # except Exception as e:
    #     print(f"❌ Playwright failed for {ticker}: {e}")
    #     return None


def parse_percentage(text: str) -> float:
    """Convert '107.98%' to 107.98"""
    try:
        return float(text.replace("%", "").replace(",", "").strip())
    except:
        return "-"

