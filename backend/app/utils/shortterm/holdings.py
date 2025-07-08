from sqlalchemy.orm import Session
from app.models import EntriedStock, VolumeSnapshot
from .volume_surge_scraper import fetch_intraday_prices

def get_current_holdings(db: Session):
    entries = db.query(EntriedStock).filter(EntriedStock.is_sold == False).all()
    result = []

    total_invested = 0
    total_current_value = 0

    for entry in entries:
        ticker = entry.ticker

        # Always fetch latest price from Yahoo
        current_price, _, _ = fetch_intraday_prices(ticker)
        if current_price is None:
            continue  # skip if price can't be fetched

        invested = entry.entry_price * entry.amount
        current_value = current_price * entry.amount

        profit_amount = round(current_value - invested)
        profit_percent = round(((current_value - invested) / invested) * 100, 2)

        total_invested += invested
        total_current_value += current_value

        result.append({
            "ticker": entry.ticker,
            "entry_price": entry.entry_price,
            "current_price": current_price,
            "amount": entry.amount,
            "entry_time": entry.created_at.isoformat(),
            "profit_amount": profit_amount,
            "profit_percent": profit_percent,
        })

    total_profit = round(total_current_value - total_invested)
    total_profit_percent = round(((total_current_value - total_invested) / total_invested) * 100, 2) if total_invested > 0 else 0.0

    return {
        "entries": result,
        "summary": {
            "total_invested": round(total_invested),
            "total_current_value": round(total_current_value),
            "total_profit": total_profit,
            "total_profit_percent": total_profit_percent
        }
    }

# Placeholder for future GPT helper functions for holdings
def ask_gpt_holding_advice(tickers_info: list):
    """
    Implement GPT interaction here to advise hold/sell based on input tickers_info.
    tickers_info is a list of dicts with holding info + current price + profit/loss.
    """
    pass
