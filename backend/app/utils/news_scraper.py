import httpx
from bs4 import BeautifulSoup
from datetime import datetime

def scrape_yahoo_news(ticker: str):
    url = f"https://finance.yahoo.co.jp/quote/{ticker}.T/news"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept-Language": "ja,en;q=0.9"
    }

    try:
        resp = httpx.get(url, headers=headers, timeout=10)

        soup = BeautifulSoup(resp.text, "html.parser")
        a_tags = soup.find_all("a")

        # Filter relevant news links
        article_links = [
            a for a in a_tags
            if "/news/" in a.get("href", "") and a.get_text(strip=True)
        ]

        news_items = []
        seen_urls = set()

        for a_tag in article_links:
            headline = a_tag.get_text(strip=True)
            url = a_tag["href"]
            if not url.startswith("http"):
                url = f"https://finance.yahoo.co.jp{url}"

            if url in seen_urls:
                continue
            seen_urls.add(url)

            news_items.append({
                "headline": headline,
                "url": url,
                "published_at": datetime.now().isoformat()  # Yahoo doesn't provide exact time
            })

            if len(news_items) >= 5:
                break

        return news_items

    except Exception as e:
        print(f"Error scraping Yahoo Finance News: {e}")
        return []

