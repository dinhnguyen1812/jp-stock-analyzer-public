from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from sqlalchemy.orm import Session
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError

from app.schemas import Stock as StockSchema
from app.models import IndustryIndicator, HistoricalIndicator
from app.db.db import SessionLocal

from app.utils.news_scraper import get_relevant_news
from app.utils.yahoo_indicators import fetch_current_indicators
from app.utils.jpx_perpbr_industry import update_and_get_industry_indicators
from app.utils.jpx_perpbr_history import update_and_get_historical_indicators
from app.utils.analyze_stock_with_gpt import analyze_stock_with_gpt

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
    return get_relevant_news(ticker)


@router.get("/{industry}")
def get_industry_indicators(industry: str, db: Session = Depends(get_db)):
    results = update_and_get_industry_indicators(industry, db)
    if not results:
        raise HTTPException(status_code=404, detail="Industry not found")
    return results


@router.get("/{ticker}/historical_indicators")
def get_historical_indicators(ticker: str, db: Session = Depends(get_db)):
    try:
        results = update_and_get_historical_indicators(ticker, db)
        if not results:
            raise HTTPException(status_code=404, detail="Historical indicators not found")
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ticker}/analysis")
def get_stock_analysis(ticker: str, db: Session = Depends(get_db)):
    try:
        result = analyze_stock_with_gpt(ticker, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Industry fetch failed: {e}")
    return result
