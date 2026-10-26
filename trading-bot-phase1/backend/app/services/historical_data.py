import csv
import os
import time
from binance.client import Client
from app.core.config import settings

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "cache")
CACHE_EXPIRY_HOURS = 24

_real_client: Client | None = None


def _get_real_binance_client() -> Client:
    global _real_client
    if _real_client is None:
        _real_client = Client(
            settings.binance_api_key,
            settings.binance_api_secret,
            testnet=False,
        )
    return _real_client


def _cache_path(symbol: str, interval: str, start: str, end: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    safe_start = start.replace(" ", "_").replace(",", "")
    safe_end = end.replace(" ", "_").replace(",", "")
    return os.path.join(CACHE_DIR, f"{symbol}_{interval}_{safe_start}_{safe_end}.csv")


def _is_cache_valid(path: str) -> bool:
    if not os.path.exists(path):
        return False
    file_age_hours = (time.time() - os.path.getmtime(path)) / 3600
    return file_age_hours < CACHE_EXPIRY_HOURS


def _load_cached(path: str) -> list[dict] | None:
    if not _is_cache_valid(path):
        return None
    candles = []
    with open(path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            candles.append({
                "timestamp": int(row["timestamp"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
            })
    return candles if candles else None


def _save_cached(path: str, candles: list[dict]):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "open", "high", "low", "close", "volume"])
        writer.writeheader()
        writer.writerows(candles)


def fetch_historical_data(
    symbol: str,
    interval: str,
    start_date: str,
    end_date: str,
) -> list[dict]:
    cache_file = _cache_path(symbol, interval, start_date, end_date)
    cached = _load_cached(cache_file)
    if cached is not None:
        return cached

    client = _get_real_binance_client()
    klines = client.get_historical_klines(
        symbol,
        interval,
        start_date,
        end_date,
    )

    candles = [
        {
            "timestamp": k[0],
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
        }
        for k in klines
    ]

    _save_cached(cache_file, candles)
    return candles
