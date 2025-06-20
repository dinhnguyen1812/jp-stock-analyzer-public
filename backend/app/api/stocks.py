from fastapi import APIRouter, HTTPException
from app.schemas import Stock

router = APIRouter()

# Dummy in-memory data for testing
dummy_stocks = {
    "5255": {
        "ticker": "5255",
        "name": "Monstarlab",
        "market": "TSE Growth",
        "price": 145.3,
        "per": 15.2,
        "pbr": 0.8,
        "roe": 9.5,
        "eps": 9.6,
        "market_cap": 15000000000,
    },
    "3350": {
        "ticker": "3350",
        "name": "MetaPlanet",
        "market": "TSE Mothers",
        "price": 210.0,
        "per": 12.5,
        "pbr": 0.7,
        "roe": 11.0,
        "eps": 8.5,
        "market_cap": 12000000000,
    }
}

@router.get("/{ticker}", response_model=Stock)
async def get_stock(ticker: str):
    stock = dummy_stocks.get(ticker)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    return stock

