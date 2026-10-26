# models/

DB models / schemas (SQLAlchemy models + Pydantic schemas).

## Planned files aur unka kaam:

### trade.py
- `Trade` DB model: id, pair (e.g. BTCUSDT), side (buy/sell), price, quantity, timestamp, profit_loss
- Pydantic schema for API request/response of a trade

### portfolio.py
- `Portfolio` DB model: current balance, holdings (coin -> quantity), last_updated
- Pydantic schema for portfolio API response
