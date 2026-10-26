import logging
import os
import sys
import time
from datetime import datetime, timedelta

import pandas as pd

from app.core.constants import (
    KRONOS_LOOKBACK_CANDLES,
    KRONOS_MODEL_NAME,
    KRONOS_PRED_CACHE_MINUTES,
    KRONOS_PREDICT_CANDLES,
    KRONOS_TOKENIZER_NAME,
)

logger = logging.getLogger(__name__)

_model = None
_tokenizer = None
_predictor = None
_model_loaded = False

_pred_cache: dict[str, dict] = {}

KRONOS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "Kronos-master", "Kronos-master"
)


def _load_model():
    global _model, _tokenizer, _predictor, _model_loaded
    if _model_loaded:
        return

    try:
        kronos_path = os.path.abspath(KRONOS_PATH)
        if kronos_path not in sys.path:
            sys.path.insert(0, kronos_path)

        from model import Kronos, KronosPredictor, KronosTokenizer

        logger.info("Loading Kronos tokenizer from HuggingFace...")
        _tokenizer = KronosTokenizer.from_pretrained(KRONOS_TOKENIZER_NAME)

        logger.info("Loading Kronos model from HuggingFace...")
        _model = Kronos.from_pretrained(KRONOS_MODEL_NAME)

        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _predictor = KronosPredictor(_model, _tokenizer, device=device, max_context=512)

        _model_loaded = True
        logger.info(f"Kronos model loaded on {device}")
    except Exception as e:
        logger.warning(f"Kronos model load failed: {e}")
        _model_loaded = False


def predict_next_movement(candles: list[dict], symbol: str = "BTCUSDT") -> dict:
    cache_key = symbol
    if cache_key in _pred_cache:
        cached = _pred_cache[cache_key]
        if datetime.utcnow() - cached["timestamp"] < timedelta(minutes=KRONOS_PRED_CACHE_MINUTES):
            return cached["result"]

    _load_model()

    if not _model_loaded or not candles:
        return {"predicted_change_pct": 0.0, "confidence": "no_model", "raw predictions": []}

    try:
        recent = candles[-KRONOS_LOOKBACK_CANDLES:]

        df = pd.DataFrame(recent)
        for col in ["open", "high", "low", "close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        if "volume" in df.columns:
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
        else:
            df["volume"] = 0.0

        if "timestamp" in df.columns:
            x_timestamp = pd.to_datetime(df["timestamp"], unit="ms")
        else:
            x_timestamp = pd.date_range(end=datetime.utcnow(), periods=len(df), freq="1min")

        y_timestamp = pd.date_range(
            start=x_timestamp.iloc[-1] + pd.Timedelta(minutes=1),
            periods=KRONOS_PREDICT_CANDLES,
            freq="1min",
        )

        predictions = _predictor.predict(
            df=df[["open", "high", "low", "close", "volume"]],
            x_timestamp=x_timestamp,
            y_timestamp=y_timestamp,
        )

        current_price = float(df["close"].iloc[-1])

        pred_closes = []
        if isinstance(predictions, pd.DataFrame):
            if "close" in predictions.columns:
                pred_closes = predictions["close"].tolist()
            elif "mean" in predictions.columns:
                pred_closes = predictions["mean"].tolist()
            else:
                pred_closes = predictions.iloc[:, 0].tolist()
        elif isinstance(predictions, dict):
            pred_closes = predictions.get("close", predictions.get("mean", []))
        elif isinstance(predictions, (list, tuple)):
            pred_closes = list(predictions)

        if pred_closes and current_price > 0:
            avg_pred = sum(float(p) for p in pred_closes) / len(pred_closes)
            change_pct = ((avg_pred - current_price) / current_price) * 100
            change_pct = max(min(change_pct, 10.0), -10.0)
        else:
            change_pct = 0.0

        confidence = "high" if abs(change_pct) > 1.0 else "medium" if abs(change_pct) > 0.3 else "low"

        result = {
            "predicted_change_pct": round(change_pct, 4),
            "confidence": confidence,
            "current_price": current_price,
            "predicted_avg": round(sum(float(p) for p in pred_closes) / len(pred_closes), 2) if pred_closes else current_price,
        }

        _pred_cache[cache_key] = {"result": result, "timestamp": datetime.utcnow()}
        return result

    except Exception as e:
        logger.warning(f"Kronos prediction failed for {symbol}: {e}")
        return {"predicted_change_pct": 0.0, "confidence": "error", "error": str(e)}
