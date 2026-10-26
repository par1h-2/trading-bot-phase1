import json
import os
import time

import requests

from app.core.config import settings
from app.core.constants import NEWS_CACHE_MINUTES

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "cache")

COIN_NAME_MAP = {
    "BTCUSDT": "Bitcoin",
    "ETHUSDT": "Ethereum",
    "SOLUSDT": "Solana",
    "BNBUSDT": "BNB",
    "XRPUSDT": "XRP",
    "ADAUSDT": "Cardano",
    "DOGEUSDT": "Dogecoin",
    "AVAXUSDT": "Avalanche",
}


def _ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)


def _cache_path(source: str, coin: str) -> str:
    _ensure_cache_dir()
    return os.path.join(CACHE_DIR, f"{source}_{coin}_cache.json")


def _is_cache_valid(path: str) -> bool:
    if not os.path.exists(path):
        return False
    try:
        with open(path, "r") as f:
            cached = json.load(f)
        age_minutes = (time.time() - cached.get("timestamp", 0)) / 60
        return age_minutes < NEWS_CACHE_MINUTES
    except (json.JSONDecodeError, KeyError):
        return False


def _load_cache(path: str) -> list[dict] | None:
    if not _is_cache_valid(path):
        return None
    try:
        with open(path, "r") as f:
            cached = json.load(f)
        return cached.get("articles", [])
    except (json.JSONDecodeError, KeyError):
        return None


def _save_cache(path: str, articles: list[dict]):
    _ensure_cache_dir()
    with open(path, "w") as f:
        json.dump({"timestamp": time.time(), "articles": articles}, f)


def _normalize_article(title: str, description: str, source: str, published_at: str) -> dict:
    return {
        "title": title or "",
        "description": description or "",
        "source": source,
        "published_at": published_at or "",
    }


def _coin_to_name(symbol: str) -> str:
    return COIN_NAME_MAP.get(symbol, symbol.replace("USDT", ""))


def fetch_newsapi_articles(coin_symbol: str = "BTCUSDT") -> list[dict]:
    coin_name = _coin_to_name(coin_symbol)
    cache = _load_cache(_cache_path("newsapi", coin_symbol))
    if cache is not None:
        return cache

    api_key = settings.newsapi_key
    if not api_key:
        return []

    try:
        query = f'"{coin_name}" OR "{coin_name} price" OR "{coin_name} news"'
        params = {
            "q": query,
            "domains": "coindesk.com,cointelegraph.com,decrypt.co,bitcoinist.com,newsbtc.com",
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 20,
            "apiKey": api_key,
        }
        resp = requests.get("https://newsapi.org/v2/everything", params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        articles = []
        for item in data.get("articles", []):
            articles.append(_normalize_article(
                title=item.get("title", ""),
                description=item.get("description", ""),
                source="newsapi",
                published_at=item.get("publishedAt", ""),
            ))

        _save_cache(_cache_path("newsapi", coin_symbol), articles)
        return articles
    except Exception:
        return _load_cache(_cache_path("newsapi", coin_symbol)) or []


def fetch_cryptopanic_articles(coin_symbol: str = "BTCUSDT") -> list[dict]:
    cache = _load_cache(_cache_path("cryptopanic", coin_symbol))
    if cache is not None:
        return cache

    api_key = settings.cryptopanic_key
    if not api_key:
        return []

    coin_code = coin_symbol.replace("USDT", "")
    try:
        params = {
            "auth_token": api_key,
            "currencies": coin_code,
            "filter": "hot",
            "kind": "news",
        }
        resp = requests.get("https://cryptopanic.com/api/v1/posts/", params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        articles = []
        for item in data.get("results", []):
            articles.append(_normalize_article(
                title=item.get("title", ""),
                description=item.get("body", "")[:300],
                source="cryptopanic",
                published_at=item.get("published_at", ""),
            ))

        _save_cache(_cache_path("cryptopanic", coin_symbol), articles)
        return articles
    except Exception:
        return _load_cache(_cache_path("cryptopanic", coin_symbol)) or []


def fetch_all_news(coin_symbol: str = "BTCUSDT") -> list[dict]:
    newsapi_articles = fetch_newsapi_articles(coin_symbol)
    cryptopanic_articles = fetch_cryptopanic_articles(coin_symbol)
    return newsapi_articles + cryptopanic_articles
