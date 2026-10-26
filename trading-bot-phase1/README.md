# Trading Bot - Phase 1 (Basic Paper Trading)

## Goal
Build a simple rule-based paper trading bot for crypto (Binance API).
No AI/ML yet - just get the core loop working:
fetch price -> apply rule -> execute fake trade -> track portfolio.

## Scope (what THIS phase includes)
- Connect to Binance API, pull live price data
- Simple rule-based buy/sell logic (e.g. % change threshold)
- Virtual wallet/balance tracking
- Save every trade to DB (price, time, qty, P/L)

## NOT in this phase (later phases)
- Historical backtesting (Phase 2)
- News/sentiment analysis (Phase 3)
- Multi-asset comparison (Phase 4)
- ML/Reinforcement Learning (Phase 5)

## Structure
```
backend/
  app/
    api/         -> API endpoints (e.g. get trades, get portfolio, start/stop bot)
    core/        -> config, settings, constants
    services/    -> business logic (market data fetch, trading engine, portfolio mgmt)
    models/      -> DB models / schemas
    main.py      -> FastAPI app entrypoint
  requirements.txt
```

## How to run (once implemented)
```
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```
