from binance.client import Client

from app.core.config import settings

_client: Client | None = None


def get_binance_client() -> Client:
    global _client
    if _client is None:
        _client = Client(
            settings.binance_api_key,
            settings.binance_api_secret,
            testnet=settings.binance_testnet,
        )
    return _client


def get_current_price(symbol: str) -> float:
    client = get_binance_client()
    ticker = client.get_symbol_ticker(symbol=symbol)
    return float(ticker["price"])


def get_klines(symbol: str, interval: str = "1m", limit: int = 50) -> list[dict]:
    client = get_binance_client()
    klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
    return [
        {
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
            "timestamp": k[0],
        }
        for k in klines
    ]
