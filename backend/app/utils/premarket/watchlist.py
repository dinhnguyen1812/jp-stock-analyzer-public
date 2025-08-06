import os
import csv

WATCHLIST_CSV = "watchlist.csv"

def ensure_watchlist_exists():
    if not os.path.exists(WATCHLIST_CSV):
        with open(WATCHLIST_CSV, mode='w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["ticker"])

def read_watchlist():
    ensure_watchlist_exists()
    with open(WATCHLIST_CSV, mode='r') as f:
        reader = csv.DictReader(f)
        return [row["ticker"] for row in reader]

def append_to_watchlist(ticker: str):
    tickers = read_watchlist()
    if ticker in tickers:
        return False  # Already in list
    with open(WATCHLIST_CSV, mode='a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([ticker])
    return True
