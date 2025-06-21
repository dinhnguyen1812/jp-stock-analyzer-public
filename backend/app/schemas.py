from pydantic import BaseModel
from typing import Optional

class Stock(BaseModel):
    ticker: str
    name: Optional[str] = None
    market: Optional[str] = None
    industry: Optional[str] = None
    price: Optional[float] = None
    dividend_yield: Optional[float] = None
    per: Optional[float] = None
    pbr: Optional[float] = None
    roe: Optional[float] = None
    eps: Optional[float] = None
    market_cap: Optional[int] = None

    class Config:
        orm_mode = True