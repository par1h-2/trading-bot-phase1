from fastapi import APIRouter, HTTPException, Query

from app.services.market_data import get_klines
from app.services.market_scanner import scan_top_gainers

router = APIRouter(prefix="/market", tags=["Market Data"])


@router.get("/klines/{symbol}")
def fetch_klines(
    symbol: str,
    interval: str = Query("1m", description="Kline interval (e.g., 1m, 5m, 1h, 1d)"),
    limit: int = Query(50, description="Number of klines to fetch (max 1000)"),
):
    try:
        klines = get_klines(symbol=symbol, interval=interval, limit=limit)
        return klines
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scanner")
def get_scanner():
    try:
        top_gainers = scan_top_gainers()
        return {
            "top_gainers": top_gainers,
            "count": len(top_gainers),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
