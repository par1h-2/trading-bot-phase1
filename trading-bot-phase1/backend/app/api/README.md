# api/

API route handlers (FastAPI routers). One file per resource.

Planned files:
- `trades.py` -> GET /trades (list past trades), GET /trades/{id}
- `portfolio.py` -> GET /portfolio (current balance, holdings, P/L)
- `bot_control.py` -> POST /bot/start, POST /bot/stop, GET /bot/status

Keep these thin - just request/response handling.
Actual logic should live in `services/`.
