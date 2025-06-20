from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.schemas import Stock as StockSchema
from app.models import Stock as StockModel
from app.db.db import SessionLocal

from app.utils.news_scraper import scrape_yahoo_news
from sqlalchemy import insert
from app.models import News as NewsModel
from fastapi.responses import JSONResponse

from sqlalchemy.exc import IntegrityError
from app.models import Stock, News

router = APIRouter()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/{ticker}", response_model=StockSchema)
def get_stock(ticker: str, db: Session = Depends(get_db)):
    stock = db.query(StockModel).filter(StockModel.ticker == ticker).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    return stock

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
