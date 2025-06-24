import os
import httpx
import datetime
from fastapi import HTTPException
from bs4 import BeautifulSoup
import pandas as pd

from sqlalchemy.orm import Session

from app.models import IndustryIndicator
from app.db.db import SessionLocal

DOWNLOAD_DIR = "app/db/industries"
BASE_URL = "https://www.jpx.co.jp"
TARGET_URL = f"{BASE_URL}/markets/statistics-equities/misc/04.html"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def download_latest_excel() -> str:
    resp = httpx.get(TARGET_URL, timeout=10)
    soup = BeautifulSoup(resp.text, "html.parser")

    # Find the .xlsx link
    link_tag = next((a for a in soup.find_all("a", href=True) if a["href"].endswith(".xlsx")), None)
    if not link_tag:
        raise Exception("❌ No .xlsx download link found.")

    file_url = BASE_URL + link_tag["href"]
    filename = os.path.basename(file_url)
    local_path = os.path.join(DOWNLOAD_DIR, filename)

    # ✅ Check if this file already exists
    if os.path.exists(local_path):
        print(f"✅ File already exists: {filename}, skipping download.")
        return local_path

    # 📥 Download the new file
    print(f"⬇️ Downloading {file_url} ...")
    with httpx.stream("GET", file_url, timeout=30) as r:
        with open(local_path, "wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)

    # 🧹 Clean up older files (except the one we just downloaded)
    for f in os.listdir(DOWNLOAD_DIR):
        if f.endswith(".xlsx") and f != filename:
            os.remove(os.path.join(DOWNLOAD_DIR, f))

    return local_path


def parse_excel(filepath: str) -> list[dict]:

    # Read the file while skipping metadata and extra headers
    df = pd.read_excel(filepath, skiprows=8)

    # Set correct column headers manually (based on actual JPX layout)
    df.columns = [
        "year_month", "market", "section", "industry_jp", "industry_en", "num_companies",
        "per", "pbr", "eps", "net_assets", "weighted_per", "weighted_pbr",
        "total_net_income", "total_net_assets"
    ]

    results = []

    for _, row in df.iterrows():
        industry_raw = str(row["industry_jp"]).strip()
        section = str(row["section"]).strip()
        per = row["per"]
        pbr = row["pbr"]

        # Normalize industry name (e.g., "1 水産・農林業" → "水産・農林業")
        if not industry_raw or not isinstance(per, (int, float)) or not isinstance(pbr, (int, float)):
            continue
        industry = industry_raw.split(maxsplit=1)[-1]

        results.append({
            "industry": industry,
            "section": section,
            "per": float(per),
            "pbr": float(pbr),
            "roe": None,
            "fetched_at": datetime.datetime.utcnow()
        })

    return results

# File to persist last loaded filename
LAST_LOADED_FILE = "app/utils/longterm/.last_loaded_filename"

def load_last_loaded_filename():
    if os.path.exists(LAST_LOADED_FILE):
        with open(LAST_LOADED_FILE, "r") as f:
            return f.read().strip()
    return None

def save_last_loaded_filename(filename: str):
    with open(LAST_LOADED_FILE, "w") as f:
        f.write(filename)

def update_industry_indicators(db: Session):
    filepath = download_latest_excel()
    filename = os.path.basename(filepath)

    last_loaded_filename = load_last_loaded_filename()

    # Skip update if this file was already processed
    if last_loaded_filename == filename:
        print(f"⏩ Skipping update — already processed {filename}")
        return

    print(f"📊 Updating industry indicators using: {filename}")
    records = parse_excel(filepath)

    # 🚨 Delete all existing rows (full replace)
    db.query(IndustryIndicator).delete()
    db.commit()

    # Insert new records
    for rec in records:
        db.add(IndustryIndicator(**rec))
    db.commit()

    # Persist filename to disk
    save_last_loaded_filename(filename)
    print(f"✅ Replaced all rows with {len(records)} new industry indicators.")

def update_and_get_industry_indicators(industry: str, db: Session):
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