from app.core.constants import COIN_UNIVERSE, TOP_GAINERS_COUNT
from app.services.market_data import get_binance_client


def scan_top_gainers() -> list[dict]:
    client = get_binance_client()
    tickers = client.get_ticker()

    coin_set = set(COIN_UNIVERSE)
    results = []

    for ticker in tickers:
        symbol = ticker["symbol"]
        if symbol not in coin_set:
            continue

        pct_change = float(ticker.get("priceChangePercent", 0))
        results.append({
            "symbol": symbol,
            "price": float(ticker.get("lastPrice", 0)),
            "pct_change_24h": round(pct_change, 2),
            "volume_24h": float(ticker.get("quoteVolume", 0)),
        })

    results.sort(key=lambda x: x["pct_change_24h"], reverse=True)
    return results[:TOP_GAINERS_COUNT]


def get_all_coin_prices() -> dict[str, float]:
    client = get_binance_client()
    tickers = client.get_ticker()
    coin_set = set(COIN_UNIVERSE)
    prices = {}

    for ticker in tickers:
        symbol = ticker["symbol"]
        if symbol in coin_set:
            prices[symbol] = float(ticker.get("lastPrice", 0))

    return prices
