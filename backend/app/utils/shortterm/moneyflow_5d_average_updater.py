from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models import DailyMoneyFlow, AverageMoneyFlow
from app.utils.shortterm.moneyflow_history import fetch_daily_money_flow_history, save_daily_money_flows

def update_avg_money_flow_for_ticker(db: Session, ticker: str):
    today = datetime.utcnow().date()

    # Step 1: Check latest available record
    latest = (
        db.query(DailyMoneyFlow)
        .filter_by(ticker=ticker)
        .order_by(DailyMoneyFlow.date.desc())
        .first()
    )

    if not latest or (today - latest.date).days >= 1:
        print(f"🔄 Money flow data outdated or missing for {ticker}, scraping...")
        flow_data = fetch_daily_money_flow_history(ticker)
        if flow_data:
            save_daily_money_flows(db, ticker, flow_data)
        else:
            print(f"❌ Failed to scrape money flow data for {ticker}")
            return

    # Step 2: Retrieve the 5 latest entries
    flows = (
        db.query(DailyMoneyFlow)
        .filter(DailyMoneyFlow.ticker == ticker)
        .order_by(desc(DailyMoneyFlow.date))
        .limit(5)
        .all()
    )

    if len(flows) < 5:
        print(f"⏳ Not enough money flow data for {ticker}. Found {len(flows)}.")
        return

    if (flows[0].date - flows[-1].date).days > 10:
        print(f"⚠️ Sparse data: 5 money flow records span more than 10 days for {ticker}")
        return

    avg_flow = sum(f.money_flow for f in flows) / 5

    # Upsert logic
    existing = db.query(AverageMoneyFlow).filter_by(ticker=ticker).first()
    if existing:
        existing.avg_5d_money_flow = avg_flow
        existing.updated_at = datetime.utcnow()
        print(f"🔄 Updated 5-day average money flow for {ticker}: {avg_flow:.2f}")
    else:
        db.add(AverageMoneyFlow(
            ticker=ticker,
            avg_5d_money_flow=avg_flow,
            updated_at=datetime.utcnow()
        ))
        print(f"✅ Inserted 5-day average money flow for {ticker}: {avg_flow:.2f}")

    db.commit()
