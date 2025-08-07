import csv
import os

WATCHLIST_CSV = os.path.join(os.path.dirname(__file__), "watchlist.csv")

def ensure_watchlist_exists():
    if not os.path.exists(WATCHLIST_CSV):
        with open(WATCHLIST_CSV, mode='w') as f:
            f.write("")  # create empty file

def read_watchlist():
    ensure_watchlist_exists()
    with open(WATCHLIST_CSV, mode='r') as f:
        content = f.read().strip()
        if not content:
            return []
        return [ticker.strip() for ticker in content.split(",") if ticker.strip()]

def append_batch_to_watchlist(tickers_str: str):
    existing = set(read_watchlist())
    added = []
    new_tickers = [ticker.strip() for ticker in tickers_str.split(",") if ticker.strip()]
    for t in new_tickers:
        t = t.strip().upper()
        if t and t not in existing:
            existing.add(t)
            added.append(t)
    if added:
        with open(WATCHLIST_CSV, mode='w') as f:
            f.write(",".join(sorted(existing)))  # sort optional
    return added  # return list of added tickers

def remove_from_watchlist_csv(ticker: str):
    if not os.path.exists(WATCHLIST_CSV):
        return

    with open(WATCHLIST_CSV, "r", encoding="utf-8") as f:
        content = f.read().strip()

    tickers = content.split(",") if content else []
    tickers = [t for t in tickers if t != ticker]

    with open(WATCHLIST_CSV, "w", encoding="utf-8") as f:
        f.write(",".join(tickers))

def add_to_watchlist_csv(ticker: str):
    ticker = ticker.strip().upper()
    
    # Read existing tickers
    if os.path.exists(WATCHLIST_CSV):
        with open(WATCHLIST_CSV, "r", encoding="utf-8") as f:
            content = f.read().strip()
        tickers = content.split(",") if content else []
    else:
        tickers = []

    # Avoid duplicates
    if ticker not in tickers:
        tickers.append(ticker)

        with open(WATCHLIST_CSV, "w", encoding="utf-8") as f:
            f.write(",".join(tickers))