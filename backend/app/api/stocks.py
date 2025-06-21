from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from sqlalchemy.orm import Session
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError

from app.schemas import Stock as StockSchema
from app.models import Stock as StockModel
from app.models import News as NewsModel
from app.db.db import SessionLocal
from app.utils.news_scraper import scrape_yahoo_news
from app.utils.gpt import analyze_news_with_gpt
from app.utils.yahoo_financials import fetch_yahoo_financials
from app.models import Stock, News

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
    scraped = fetch_yahoo_financials(ticker)
    if not scraped or not scraped["name"]:
        raise HTTPException(status_code=404, detail="Stock not found or not scrappable")
    return scraped

@router.get("/{ticker}/news")
def get_stock_news(ticker: str, db: Session = Depends(get_db)):
    # Ensure stock exists before inserting news
    stock = db.query(Stock).filter(Stock.ticker == ticker).first()
    if not stock:
        # Insert minimal stock row (you can fetch full data elsewhere)
        stock = Stock(ticker=ticker, name="", market="", price=0)
        db.add(stock)
        db.commit()

    news_items = scrape_yahoo_news(ticker)

    for item in news_items:
        exists = db.query(News).filter(News.url == item["url"]).first()
        if not exists:
            try:
                db.add(News(
                    stock_ticker=ticker,
                    headline=item["headline"],
                    url=item["url"],
                    published_at=item["published_at"]
                ))
            except IntegrityError:
                db.rollback()

    db.commit()
    return news_items

@router.get("/{ticker}/analysis")
def analyze_stock_news(ticker: str):
    news_items = scrape_yahoo_news(ticker)
    summary, sentiment = analyze_news_with_gpt(news_items)
    return {
        "summary": summary,
        "sentiment": sentiment,
        "headlines": news_items  # optional: include for display/debug
    }