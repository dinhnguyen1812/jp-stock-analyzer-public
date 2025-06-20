from sqlalchemy import text
from .db import engine

def init_db():
    with engine.begin() as conn:
        # Create table to store basic stock info
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS stocks (
                id SERIAL PRIMARY KEY,
                ticker TEXT UNIQUE NOT NULL,
                name TEXT,
                market TEXT,
                price NUMERIC,
                per NUMERIC,
                pbr NUMERIC,
                roe NUMERIC,
                eps NUMERIC,
                market_cap BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))

        # Create table to store news articles related to stocks
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS news (
                id SERIAL PRIMARY KEY,
                stock_ticker TEXT REFERENCES stocks(ticker),
                headline TEXT NOT NULL,
                url TEXT,
                published_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))

        # Store GPT analysis results
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS analysis (
                id SERIAL PRIMARY KEY,
                stock_ticker TEXT REFERENCES stocks(ticker),
                source TEXT,  -- e.g. "news", "technical", "combined"
                summary TEXT,
                sentiment TEXT,  -- e.g. "positive", "neutral", "negative"
                score NUMERIC,  -- e.g. 0–10
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))

        # Optional: store technical indicators
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS technical_indicators (
                id SERIAL PRIMARY KEY,
                stock_ticker TEXT REFERENCES stocks(ticker),
                date DATE,
                ma5 NUMERIC,
                ma20 NUMERIC,
                rsi NUMERIC,
                macd NUMERIC,
                volume BIGINT,
                pattern TEXT,  -- e.g. "breakout", "double bottom"
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
