from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Float, Integer, String

from app.models.database import Base


# --- DB Model ---
class BacktestResult(Base):
    __tablename__ = "backtest_results"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    run_date = Column(DateTime, default=lambda: datetime.utcnow())
    symbol = Column(String, nullable=False)
    interval = Column(String, nullable=False)
    start_date = Column(String, nullable=False)
    end_date = Column(String, nullable=False)
    starting_balance = Column(Float, nullable=False)
    final_balance = Column(Float, nullable=False)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    total_profit_loss = Column(Float, default=0.0)
    avg_profit_per_trade = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    max_drawdown_pct = Column(Float, default=0.0)
    parameters_used = Column(String, default="{}")


class BacktestTrade(Base):
    __tablename__ = "backtest_trades"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    backtest_id = Column(Integer, nullable=False)
    side = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    profit_loss = Column(Float, default=0.0)


# --- Pydantic Schemas ---
class BacktestRunRequest(BaseModel):
    symbol: str = "BTCUSDT"
    interval: str = "1d"
    start_date: str = "1 Jan, 2023"
    end_date: str = "1 Jan, 2025"
    starting_balance: float = 10000.0
    buy_pct: float | None = None
    sell_pct: float | None = None
    buy_size_pct: float = 10.0
    sell_size_pct: float = 50.0
    stop_loss_pct: float = -5.0


class BacktestResultResponse(BaseModel):
    id: int
    run_date: datetime
    symbol: str
    interval: str
    start_date: str
    end_date: str
    starting_balance: float
    final_balance: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_profit_loss: float
    avg_profit_per_trade: float
    max_drawdown: float
    max_drawdown_pct: float
    parameters_used: str

    model_config = {"from_attributes": True}


class BacktestTradeResponse(BaseModel):
    id: int
    backtest_id: int
    side: str
    price: float
    quantity: float
    timestamp: datetime
    profit_loss: float

    model_config = {"from_attributes": True}


class BacktestDetailResponse(BaseModel):
    result: BacktestResultResponse
    trades: list[BacktestTradeResponse]
    equity_curve: list[float] = []
