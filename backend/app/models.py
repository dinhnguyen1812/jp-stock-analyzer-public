from sqlalchemy import Column, Integer, String, Numeric, BIGINT, TIMESTAMP, Date, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Stock(Base):
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, unique=True, index=True, nullable=False)
    name = Column(String)
    market = Column(String)
    price = Column(Numeric)
    per = Column(Numeric)
    pbr = Column(Numeric)
    roe = Column(Numeric)
    eps = Column(Numeric)
    market_cap = Column(BIGINT)
    created_at = Column(TIMESTAMP)

class News(Base):
    __tablename__ = "news"

    id = Column(Integer, primary_key=True)
    stock_ticker = Column(String, ForeignKey("stocks.ticker"))
    headline = Column(String, nullable=False)
    url = Column(String)
    published_at = Column(TIMESTAMP)
    created_at = Column(TIMESTAMP)

class Analysis(Base):
    __tablename__ = "analysis"

    id = Column(Integer, primary_key=True)
    stock_ticker = Column(String, ForeignKey("stocks.ticker"))
    source = Column(String)  # e.g., "news", "technical", "combined"
    summary = Column(String)
    sentiment = Column(String)  # e.g., "positive", "neutral", "negative"
    score = Column(Numeric)     # e.g., 0–10
    created_at = Column(TIMESTAMP)

class TechnicalIndicator(Base):
    __tablename__ = "technical_indicators"

    id = Column(Integer, primary_key=True)
    stock_ticker = Column(String, ForeignKey("stocks.ticker"))
    date = Column(Date)
    ma5 = Column(Numeric)
    ma20 = Column(Numeric)
    rsi = Column(Numeric)
    macd = Column(Numeric)
    volume = Column(Integer)
    pattern = Column(String)  # e.g., "breakout", "double bottom"
    created_at = Column(TIMESTAMP)

