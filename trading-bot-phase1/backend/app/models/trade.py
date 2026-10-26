from datetime import datetime, timezone

from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Float, Integer, String

from app.models.database import Base


# --- DB Model ---
class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    pair = Column(String, nullable=False)
    side = Column(String, nullable=False)  # "buy" or "sell"
    price = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    profit_loss = Column(Float, default=0.0)


# --- Pydantic Schemas ---
class TradeResponse(BaseModel):
    id: int
    pair: str
    side: str
    price: float
    quantity: float
    timestamp: datetime
    profit_loss: float

    model_config = {"from_attributes": True}
