from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.constants import DEFAULT_SYMBOL
from app.models.database import get_db
from app.services.market_data import get_current_price
from app.services.portfolio import get_portfolio_value

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/")
def get_portfolio(db: Session = Depends(get_db)):
    current_price = get_current_price(DEFAULT_SYMBOL)
    return get_portfolio_value(db, current_price)
