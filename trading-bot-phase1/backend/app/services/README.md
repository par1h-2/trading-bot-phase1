# services/

Yahan actual business logic aayegi (API routes sirf ye services call karenge).

## Planned files aur unka kaam:

### market_data.py
- Binance API se connect karna
- Live price fetch karna (e.g. BTCUSDT ka current price)
- Price history/candles fetch karna (agar chahiye ho)

### trading_engine.py
- Trading rule ka logic (e.g. "price X% gira to buy, Y% badha to sell")
- Buy/sell decision lena based on current price vs rule
- Trade execute karna (virtual - matlab sirf DB update karna, real order nahi)

### portfolio.py
- Virtual wallet/balance manage karna
- Current holdings track karna (kitna crypto hold kar rahe hain)
- Total profit/loss calculate karna
