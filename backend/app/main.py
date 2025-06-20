from fastapi import FastAPI
from app.api import stocks

app = FastAPI()

app.include_router(stocks.router, prefix="/stocks", tags=["stocks"])

@app.get("/")
def read_root():
    return {"message": "Welcome to JP Stock Analyzer API!"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

