from sqlalchemy import Column, Integer, String, TIMESTAMP, Date, Float, PrimaryKeyConstraint, UniqueConstraint, Text, Boolean, JSON
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
    top_news = Column(Text, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("id"),
        UniqueConstraint("ticker", "detected_at", name="uq_ticker_detected_at"),
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

class DailyPrice(Base):
    __tablename__ = "daily_prices"

    ticker = Column(String, primary_key=True, index=True)
    date = Column(Date, primary_key=True, index=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("ticker", "date"),
    )

class ShortTermAnalysisSignal(Base):
    __tablename__ = "shortterm_analysis_signals"

    ticker = Column(String, primary_key=True)
    date = Column(Date, nullable=False)

    # Candlestick
    candle_pattern = Column(String, nullable=True)

    # Breakout
    breakout_detected = Column(Boolean, default=False)
    resistance_level = Column(Float, nullable=True)
    close_today = Column(Float, nullable=True)

    # Technical indicators
    rsi = Column(Float, nullable=True)
    macd_line = Column(Float, nullable=True)
    macd_signal = Column(Float, nullable=True)
    macd_hist = Column(Float, nullable=True)

    bb_upper = Column(Float, nullable=True)
    bb_middle = Column(Float, nullable=True)
    bb_lower = Column(Float, nullable=True)
    bb_current_price = Column(Float, nullable=True)

    sma_50 = Column(Float, nullable=True)
    sma_200 = Column(Float, nullable=True)
    ema_20 = Column(Float, nullable=True)
    sma_crossover = Column(String, nullable=True)

    # Pattern detection
    w_shape = Column(Boolean, default=False)
    flags_pennants = Column(Boolean, default=False)
    triangle = Column(Boolean, default=False)

    updated_at = Column(TIMESTAMP, default=datetime.datetime.utcnow, nullable=False, onupdate=datetime.datetime.utcnow)

class EntriedStock(Base):
    __tablename__ = "entried_stocks"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)

    detected_at = Column(TIMESTAMP, nullable=False)  # from VolumeSnapshot.detected_at
    updated_at = Column(TIMESTAMP, nullable=False)   # from ShortTermAnalysisSignal.updated_at

    entry_price = Column(Float, nullable=False)
    amount = Column(Integer, nullable=False)  # number of shares
    is_sold = Column(Boolean, default=False, nullable=False)

    created_at = Column(TIMESTAMP, default=datetime.datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("ticker", "detected_at", "updated_at", name="uq_entry_record"),
    )

class SpikeScan(Base):
    __tablename__ = "spike_scans"

    id = Column(Integer, primary_key=True)
    ticker = Column(String, unique=True, index=True)
    volume_rate = Column(Float)
    money_flow_rate = Column(Float)
    current_price = Column(Float)
    detected_at = Column(TIMESTAMP)

    downtrend = Column(JSON, nullable=True)
    downtrend_checked_at = Column(TIMESTAMP, nullable=True)

    top_news = Column(JSON, nullable=True)
    news_checked_at = Column(TIMESTAMP, nullable=True)

    updated_at = Column(TIMESTAMP, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
