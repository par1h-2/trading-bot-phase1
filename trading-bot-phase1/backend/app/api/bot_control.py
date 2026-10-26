from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.services.trading_engine import bot_engine
from app.services.multi_asset_engine import multi_engine

router = APIRouter(prefix="/bot", tags=["bot"])


@router.post("/start")
def start_bot(mode: str = Query("single", description="Trading mode: single or multi")):
    bot_engine.start(mode=mode)
    return {"status": "started", "mode": mode, **bot_engine.get_status()}


@router.post("/stop")
def stop_bot():
    bot_engine.stop()
    return {"status": "stopped", **bot_engine.get_status()}


@router.get("/status")
def bot_status():
    return bot_engine.get_status()


@router.post("/tick")
def manual_tick(db: Session = Depends(get_db)):
    if bot_engine.mode == "multi":
        results = multi_engine.tick(db)
        return {"tick_results": results, **bot_engine.get_status()}
    else:
        result = bot_engine.tick(db)
        return {"tick_result": result, **bot_engine.get_status()}
