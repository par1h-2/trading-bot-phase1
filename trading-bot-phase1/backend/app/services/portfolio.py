import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.constants import STARTING_BALANCE
from app.models.portfolio import Portfolio
from app.services.market_data import get_current_price


def get_portfolio(db: Session) -> Portfolio:
    portfolio = db.query(Portfolio).first()
    if not portfolio:
        portfolio = Portfolio(
            balance=STARTING_BALANCE,
            holdings=json.dumps({}),
            last_updated=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.add(portfolio)
        db.commit()
        db.refresh(portfolio)
    return portfolio


def update_portfolio(
    db: Session, balance: float, holdings: dict[str, float]
) -> Portfolio:
    portfolio = db.query(Portfolio).first()
    if not portfolio:
        portfolio = Portfolio(
            balance=balance,
            holdings=json.dumps(holdings),
            last_updated=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.add(portfolio)
    else:
        portfolio.balance = balance
        portfolio.holdings = json.dumps(holdings)
        portfolio.last_updated = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(portfolio)
    return portfolio


def get_portfolio_value(db: Session, current_price: float) -> dict:
    portfolio = get_portfolio(db)
    holdings = json.loads(portfolio.holdings)

    holdings_value = 0.0
    for symbol, qty in holdings.items():
        try:
            price = get_current_price(symbol)
        except Exception:
            price = current_price
        holdings_value += qty * price

    total_value = portfolio.balance + holdings_value
    profit_loss = total_value - STARTING_BALANCE

    return {
        "balance": portfolio.balance,
        "holdings": holdings,
        "holdings_value": round(holdings_value, 2),
        "total_value": round(total_value, 2),
        "profit_loss": round(profit_loss, 2),
        "last_updated": portfolio.last_updated,
    }
