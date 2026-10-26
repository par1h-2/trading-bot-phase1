from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import bot_control, portfolio, trades, market, backtest, sentiment
from app.core.config import settings
from app.models.database import Base, engine
from app.models.backtest_result import BacktestResult, BacktestTrade
from app.models.portfolio import Portfolio
from app.models.trade import Trade
from app.services.trading_engine import bot_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield
    if bot_engine.scheduler.running:
        bot_engine.scheduler.shutdown(wait=False)


app = FastAPI(
    title=settings.app_name,
    description="Rule-based paper trading bot for crypto",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(trades.router)
app.include_router(portfolio.router)
app.include_router(bot_control.router)
app.include_router(market.router)
app.include_router(backtest.router)
app.include_router(sentiment.router)


@app.get("/")
def root():
    return {"message": "Trading Bot API is running"}
