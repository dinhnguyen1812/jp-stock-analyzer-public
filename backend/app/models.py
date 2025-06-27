from sqlalchemy import Column, Integer, String, TIMESTAMP, Date, Float, PrimaryKeyConstraint, UniqueConstraint, Text
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

class VolumeSnapshot(Base):
    __tablename__ = "volume_snapshots"

    id = Column(Integer, primary_key=True)
    ticker = Column(String, index=True)
    name = Column(String)
    current_price = Column(Float)
    price_change = Column(Float)
    current_volume = Column(Integer)
    avg_volume_5d = Column(Integer)
    volume_rate = Column(Float)
    money_flow_rate = Column(Float, nullable=True)
    detected_at = Column(TIMESTAMP, default=datetime.datetime.utcnow)
    reasoning = Column(Text, nullable=True)
    recommendation = Column(String, nullable=True)  # "Buy", "Hold", "Sell"
    promising_score = Column(Integer, nullable=True)  # 0-100
    top_news_json = Column(Text, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("id"),
    )

class StarredStock(Base):
    __tablename__ = "starred_stocks"
    id = Column(Integer, primary_key=True)
    ticker = Column(String, unique=True, index=True)

class DailyVolume(Base):
    __tablename__ = "daily_volumes"

    ticker = Column(String, primary_key=True, index=True)
    date = Column(Date, primary_key=True, index=True)
    volume = Column(Integer, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("ticker", "date"),
    )

class AverageVolume(Base):
    __tablename__ = "average_volumes"

    ticker = Column(String, primary_key=True, index=True)
    avg_5d_volume = Column(Integer, nullable=False)
    updated_at = Column(TIMESTAMP, default=datetime.datetime.utcnow, nullable=False)

class DailyMoneyFlow(Base):
    __tablename__ = "daily_money_flows"

    ticker = Column(String, primary_key=True, index=True)
    date = Column(Date, primary_key=True, index=True)
    typical_price = Column(Float, nullable=False)
    volume = Column(Integer, nullable=False)
    money_flow = Column(Float, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("ticker", "date"),
    )

class AverageMoneyFlow(Base):
    __tablename__ = "average_money_flows"

    ticker = Column(String, primary_key=True, index=True)
    avg_5d_money_flow = Column(Float, nullable=False)
    updated_at = Column(TIMESTAMP, default=datetime.datetime.utcnow, nullable=False)
