from sqlalchemy import Column, Integer, String, TIMESTAMP, Date, Float, PrimaryKeyConstraint, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
import datetime

Base = declarative_base()

class IndustryIndicator(Base):
    __tablename__ = "industry_indicators"

    industry = Column(String, index=True)
    section = Column(String, index=True)  # Add this field
    per = Column(Float)
    pbr = Column(Float)
    roe = Column(Float)
    fetched_at = Column(TIMESTAMP, default=datetime.datetime.utcnow)

    __table_args__ = (
        PrimaryKeyConstraint("industry", "section"),  # Composite primary key
    )

class HistoricalIndicator(Base):
    __tablename__ = "historical_indicators"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)
    date = Column(Date, index=True)
    per = Column(Float)
    pbr = Column(Float)
    # Optionally:
    # roe = Column(Float)

    __table_args__ = (
        UniqueConstraint("ticker", "date", name="unique_ticker_date"),
    )