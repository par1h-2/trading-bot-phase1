import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.backtest_result import (
    BacktestResult,
    BacktestResultResponse,
    BacktestRunRequest,
    BacktestTrade,
    BacktestTradeResponse,
    BacktestDetailResponse,
)
from app.models.database import get_db
from app.services.backtest_engine import BacktestEngine
from app.services.historical_data import fetch_historical_data

router = APIRouter(prefix="/backtest", tags=["backtest"])


@router.post("/run", response_model=BacktestDetailResponse)
def run_backtest(req: BacktestRunRequest, db: Session = Depends(get_db)):
    candles = fetch_historical_data(
        symbol=req.symbol,
        interval=req.interval,
        start_date=req.start_date,
        end_date=req.end_date,
    )

    if not candles:
        raise HTTPException(status_code=400, detail="No historical data found for given parameters")

    engine = BacktestEngine(
        starting_balance=req.starting_balance,
        buy_pct=req.buy_pct,
        sell_pct=req.sell_pct,
        buy_size_pct=req.buy_size_pct,
        sell_size_pct=req.sell_size_pct,
        stop_loss_pct=req.stop_loss_pct,
    )
    result = engine.run(candles)
    metrics = result["metrics"]

    params = {}
    if req.buy_pct is not None:
        params["buy_pct"] = req.buy_pct
    if req.sell_pct is not None:
        params["sell_pct"] = req.sell_pct
    params["buy_size_pct"] = req.buy_size_pct
    params["sell_size_pct"] = req.sell_size_pct
    params["stop_loss_pct"] = req.stop_loss_pct

    bt_result = BacktestResult(
        symbol=req.symbol,
        interval=req.interval,
        start_date=req.start_date,
        end_date=req.end_date,
        starting_balance=req.starting_balance,
        final_balance=metrics.final_balance,
        total_trades=metrics.total_trades,
        winning_trades=metrics.winning_trades,
        losing_trades=metrics.losing_trades,
        win_rate=metrics.win_rate,
        total_profit_loss=metrics.total_pnl,
        avg_profit_per_trade=metrics.avg_profit_per_trade,
        max_drawdown=metrics.max_drawdown,
        max_drawdown_pct=metrics.max_drawdown_pct,
        parameters_used=json.dumps(params),
    )
    db.add(bt_result)
    db.commit()
    db.refresh(bt_result)

    for t in result["trades"]:
        db_trade = BacktestTrade(
            backtest_id=bt_result.id,
            side=t["side"],
            price=t["price"],
            quantity=t["quantity"],
            timestamp=t["timestamp"],
            profit_loss=t["profit_loss"],
        )
        db.add(db_trade)
    db.commit()

    db_trades = (
        db.query(BacktestTrade)
        .filter(BacktestTrade.backtest_id == bt_result.id)
        .all()
    )

    return BacktestDetailResponse(
        result=BacktestResultResponse.model_validate(bt_result),
        trades=[BacktestTradeResponse.model_validate(t) for t in db_trades],
        equity_curve=result["equity_curve"],
    )


@router.get("/results", response_model=list[BacktestResultResponse])
def list_results(db: Session = Depends(get_db)):
    return db.query(BacktestResult).order_by(BacktestResult.run_date.desc()).all()


@router.get("/results/{backtest_id}", response_model=BacktestDetailResponse)
def get_result(backtest_id: int, db: Session = Depends(get_db)):
    bt_result = db.query(BacktestResult).filter(BacktestResult.id == backtest_id).first()
    if not bt_result:
        raise HTTPException(status_code=404, detail="Backtest not found")

    trades = (
        db.query(BacktestTrade)
        .filter(BacktestTrade.backtest_id == backtest_id)
        .all()
    )

    return BacktestDetailResponse(
        result=BacktestResultResponse.model_validate(bt_result),
        trades=[BacktestTradeResponse.model_validate(t) for t in trades],
    )
