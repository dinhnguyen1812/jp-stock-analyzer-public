from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models import DailyMoneyFlow, AverageMoneyFlow

def update_avg_money_flow_for_ticker(db: Session, ticker: str):
    # Fetch the 5 most recent money flow records for the ticker
    flows = (
        db.query(DailyMoneyFlow)
        .filter(DailyMoneyFlow.ticker == ticker)
        .order_by(desc(DailyMoneyFlow.date))
        .limit(5)
        .all()
    )

    if len(flows) < 5:
        print(f"⏳ Not enough money flow data for {ticker}. Need 5 days, found {len(flows)}.")
        return

    # Calculate average money flow
    avg_flow = sum(flow.money_flow for flow in flows) / 5

    # Upsert into AverageMoneyFlow table
    existing = db.query(AverageMoneyFlow).filter_by(ticker=ticker).first()
    if existing:
        existing.avg_5d_money_flow = avg_flow
        existing.updated_at = datetime.utcnow()
        print(f"🔄 Updated 5-day average money flow for {ticker}: {avg_flow:.2f}")
    else:
        record = AverageMoneyFlow(
            ticker=ticker,
            avg_5d_money_flow=avg_flow,
            updated_at=datetime.utcnow(),
        )
        db.add(record)
        print(f"✅ Inserted 5-day average money flow for {ticker}: {avg_flow:.2f}")

    db.commit()
