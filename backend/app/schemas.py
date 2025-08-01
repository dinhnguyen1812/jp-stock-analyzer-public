from pydantic import BaseModel
from typing import Optional

class Stock(BaseModel):
    ticker: str
    name: Optional[str] = None
    market: Optional[str] = None
    current_price: Optional[float] = None
    industry: Optional[str] = None
    min_price: Optional[float] = None
    dividend_yield: Optional[float] = None
    per: Optional[float] = None
    pbr: Optional[float] = None
    roe: Optional[float] = None
    eps: Optional[float] = None
    bps: Optional[float] = None
    market_cap: Optional[int] = None
    debt_ratio: Optional[float] = None

    class Config:
        orm_mode = True

class EntryRequest(BaseModel):
    ticker: str
    amount: int
    entry_price: float

class ScanParams(BaseModel):
    surge_threshold: float = 2.0
    price_threshold: float = 300.0
    from_page: int = 1
    to_page: int = 3
    days_threshold: int = 1