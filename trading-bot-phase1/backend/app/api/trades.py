from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.trade import Trade, TradeResponse

router = APIRouter(prefix="/trades", tags=["trades"])


@router.get("/", response_model=list[TradeResponse])
def list_trades(db: Session = Depends(get_db)):
    return db.query(Trade).order_by(Trade.timestamp.desc()).all()


@router.get("/{trade_id}", response_model=TradeResponse)
def get_trade(trade_id: int, db: Session = Depends(get_db)):
    trade = db.query(Trade).filter(Trade.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade
