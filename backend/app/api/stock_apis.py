from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from sqlalchemy.orm import Session
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError

from app.schemas import Stock as StockSchema
from app.models import IndustryIndicator, HistoricalIndicator
from app.db.db import SessionLocal

from app.utils.news_scraper import get_relevant_news
# from app.utils.gpt import analyze_news_with_gpt
from app.utils.yahoo_indicators import fetch_current_indicators
from app.utils.jpx_perpbr_industry import update_industry_indicators
from app.utils.jpx_perpbr_history import save_historical_to_csv, fetch_historical_indicators_irbank

router = APIRouter()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/{ticker}/indicators", response_model=StockSchema)
def get_stock_realtime(ticker: str):
    scraped = fetch_current_indicators(ticker)
    if not scraped or not scraped["name"]:
        raise HTTPException(status_code=404, detail="Stock not found or not scrappable")
    return scraped

@router.get("/{ticker}/news")
def get_stock_news(ticker: str):
    ranked_news = get_relevant_news(ticker)

    return ranked_news

# @router.get("/{ticker}/analysis")
# def analyze_stock_news(ticker: str):
#     news_items = scrape_yahoo_news(ticker)
#     summary, sentiment = analyze_news_with_gpt(news_items)
#     return {
#         "summary": summary,
#         "sentiment": sentiment,
#         "headlines": news_items  # optional: include for display/debug
#     }

@router.get("/{industry}")
def get_industry_indicators(industry: str, db: Session = Depends(get_db)):
    # Only update if needed (already checked inside)
    update_industry_indicators(db)

    # Fetch all matching records
    results = db.query(IndustryIndicator).filter(
        IndustryIndicator.industry.like(f"%{industry}%")
    ).all()

    if not results:
        raise HTTPException(status_code=404, detail="Industry not found")

    return [
        {
            "industry": rec.industry,
            "section": rec.section,
            "per": rec.per,
            "pbr": rec.pbr,
            "roe": rec.roe,
            "fetched_at": rec.fetched_at,
        }
        for rec in results
    ]

@router.get("/{ticker}/historical_indicators")
def get_historical_indicators(ticker: str, db: Session = Depends(get_db)):
    # 1. Scrape and update CSV
    scraped = fetch_historical_indicators_irbank(ticker)
    save_historical_to_csv(ticker, scraped)

    # 2. Sync new records to DB
    inserted = 0
    for row in scraped:
        date = row["date"]
        existing = db.query(HistoricalIndicator).filter_by(ticker=ticker, date=date).first()
        if existing:
            continue
        db.add(HistoricalIndicator(
            ticker=ticker,
            date=date,
            per=row.get("per"),
            pbr=row.get("pbr")
        ))
        inserted += 1
    db.commit()

    # 3. Return last 12 months (or all)
    results = db.query(HistoricalIndicator)\
        .filter(HistoricalIndicator.ticker == ticker)\
        .order_by(HistoricalIndicator.date.desc())\
        .limit(12)\
        .all()

    return results[::-1]  # return oldest first