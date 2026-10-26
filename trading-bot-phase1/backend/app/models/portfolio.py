from datetime import datetime, timezone

from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Float, Integer, String

from app.models.database import Base


# --- DB Model ---
class Portfolio(Base):
    __tablename__ = "portfolio"

    id = Column(Integer, primary_key=True, index=True)
    balance = Column(Float, nullable=False)
    holdings = Column(String, default="{}")  # JSON string: {"BTC": 0.5}
    last_updated = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


# --- Pydantic Schemas ---
class PortfolioResponse(BaseModel):
    balance: float
    holdings: dict[str, float]
    total_value: float
    profit_loss: float
    last_updated: datetime

    model_config = {"from_attributes": True}
