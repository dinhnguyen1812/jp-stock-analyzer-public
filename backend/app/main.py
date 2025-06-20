from fastapi import FastAPI
from app.db import init_db

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Welcome to JP Stock Analyzer API!"}

@app.get("/health")
def health_check():
    return {"status": "ok"}
