import json
import math
import time
import threading
from collections import deque

from sqlalchemy.orm import Session

from app.core.constants import (
    FALLBACK_BUY_PCT,
    FALLBACK_SELL_PCT,
    KRONOS_WEIGHT,
    MIN_TICKS_FOR_VOLATILITY,
    PRICE_HISTORY_SIZE,
    SENTIMENT_WEIGHT,
    STOP_LOSS_PCT,
    TRADE_TOP_N,
    VOLATILITY_MULTIPLIER,
)
from app.models.database import SessionLocal
from app.models.portfolio import Portfolio
from app.models.trade import Trade
from app.services.kronos_predictor import predict_next_movement
from app.services.market_data import get_current_price
from app.services.market_scanner import scan_top_gainers
from app.services.news_fetcher import fetch_all_news
from app.services.portfolio import get_portfolio, update_portfolio
from app.services.sentiment_analyzer import analyze_sentiment


class CoinState:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.price_history: deque = deque(maxlen=PRICE_HISTORY_SIZE)
        self.reference_price: float | None = None
        self.current_buy_threshold = FALLBACK_BUY_PCT
        self.current_sell_threshold = FALLBACK_SELL_PCT
        self.sentiment_score: float = 0.0
        self.open_lots: list[dict] = []
        self.momentum_score: float = 0.0
        self.kronos_score: float = 0.0
        self.final_score: float = 0.0
        self._kronos_thread: threading.Thread | None = None
        self._kronos_lock = threading.Lock()


class MultiAssetEngine:
    def __init__(self):
        self.running = False
        self.coins: dict[str, CoinState] = {}
        self.scan_results: list[dict] = []
        self.traded_symbols: list[str] = []

    def start(self):
        self.running = True

    def stop(self):
        self.running = False

    def get_status(self) -> dict:
        return {
            "running": self.running,
            "traded_symbols": self.traded_symbols,
            "scan_results": self.scan_results,
            "coin_scores": {
                sym: {
                    "momentum": round(cs.momentum_score, 3),
                    "sentiment": round(cs.sentiment_score, 3),
                    "kronos": round(cs.kronos_score, 3),
                    "final": round(cs.final_score, 3),
                    "price_history_count": len(cs.price_history),
                }
                for sym, cs in self.coins.items()
            },
        }

    def _calculate_volatility(self, price_history: deque) -> float:
        if len(price_history) < MIN_TICKS_FOR_VOLATILITY:
            return 0.0
        prices = list(price_history)
        mean = sum(prices) / len(prices)
        variance = sum((p - mean) ** 2 for p in prices) / len(prices)
        std_dev = math.sqrt(variance)
        current_price = prices[-1]
        if current_price == 0:
            return 0.0
        return (std_dev / current_price) * 100

    def _update_thresholds(self, state: CoinState):
        if len(state.price_history) < MIN_TICKS_FOR_VOLATILITY:
            state.current_buy_threshold = FALLBACK_BUY_PCT
            state.current_sell_threshold = FALLBACK_SELL_PCT
            return
        volatility_pct = self._calculate_volatility(state.price_history)
        threshold = volatility_pct * VOLATILITY_MULTIPLIER
        state.current_buy_threshold = -threshold
        state.current_sell_threshold = threshold

    def _calculate_momentum(self, state: CoinState) -> float:
        if len(state.price_history) < 5:
            return 0.0
        prices = list(state.price_history)
        recent = prices[-5:]
        change = (recent[-1] - recent[0]) / recent[0] * 100
        return max(min(change / 5.0, 1.0), -1.0)

    def _update_sentiment(self, state: CoinState):
        try:
            articles = fetch_all_news(state.symbol)
            result = analyze_sentiment(articles)
            state.sentiment_score = result["score"]
        except Exception:
            state.sentiment_score = 0.0

    def _update_kronos(self, state: CoinState):
        with state._kronos_lock:
            if state._kronos_thread and state._kronos_thread.is_alive():
                return

        if len(state.price_history) < 10:
            state.kronos_score = 0.0
            return

        candles = []
        prices = list(state.price_history)
        now_ms = int(time.time() * 1000)
        for i, p in enumerate(prices):
            candles.append({
                "open": p,
                "high": p * 1.001,
                "low": p * 0.999,
                "close": p,
                "volume": 1000.0,
                "timestamp": now_ms - (len(prices) - i) * 60000,
            })

        def _run_prediction():
            try:
                result = predict_next_movement(candles, state.symbol)
                raw_pct = result.get("predicted_change_pct", 0.0)
                with state._kronos_lock:
                    state.kronos_score = max(min(raw_pct / 5.0, 1.0), -1.0)
            except Exception:
                with state._kronos_lock:
                    state.kronos_score = 0.0

        thread = threading.Thread(target=_run_prediction, daemon=True)
        with state._kronos_lock:
            state._kronos_thread = thread
        thread.start()

    def _update_scores(self, state: CoinState):
        state.momentum_score = self._calculate_momentum(state)
        state.final_score = (
            state.momentum_score * (1.0 - SENTIMENT_WEIGHT - KRONOS_WEIGHT)
            + state.sentiment_score * SENTIMENT_WEIGHT
            + state.kronos_score * KRONOS_WEIGHT
        )

    def _check_stop_loss(self, db: Session, symbol: str, current_price: float, state: CoinState):
        if not state.open_lots:
            return

        portfolio = get_portfolio(db)
        holdings = json.loads(portfolio.holdings)
        held_qty = holdings.get(symbol, 0.0)

        lots_to_remove = []
        for i, lot in enumerate(state.open_lots):
            pct_change = ((current_price - lot["price"]) / lot["price"]) * 100
            if pct_change <= STOP_LOSS_PCT:
                lots_to_remove.append(i)

        for i in reversed(lots_to_remove):
            lot = state.open_lots.pop(i)
            pnl = (current_price - lot["price"]) * lot["quantity"]

            trade = Trade(
                pair=symbol,
                side="sell",
                price=current_price,
                quantity=lot["quantity"],
                profit_loss=round(pnl, 2),
            )
            db.add(trade)
            db.commit()

            held_qty -= lot["quantity"]
            if held_qty <= 0:
                holdings.pop(symbol, None)
            else:
                holdings[symbol] = held_qty

        if lots_to_remove:
            new_balance = portfolio.balance + held_qty * current_price
            update_portfolio(db, balance=new_balance, holdings=holdings)

    def tick(self, db: Session) -> list[dict]:
        if not self.running:
            return []

        self.scan_results = scan_top_gainers()
        top_symbols = [s["symbol"] for s in self.scan_results[:TRADE_TOP_N]]
        self.traded_symbols = top_symbols

        portfolio = get_portfolio(db)
        held_symbols = list(json.loads(portfolio.holdings).keys())

        symbols_to_tick = list(set(top_symbols + held_symbols))

        for symbol in symbols_to_tick:
            if symbol not in self.coins:
                self.coins[symbol] = CoinState(symbol)

        all_results = []
        for symbol in symbols_to_tick:
            result = self._tick_coin(db, symbol, is_top_gainer=symbol in top_symbols)
            if result:
                all_results.append(result)

        return all_results

    def _tick_coin(self, db: Session, symbol: str, is_top_gainer: bool = True) -> dict | None:
        state = self.coins[symbol]
        current_price = get_current_price(symbol)
        state.price_history.append(current_price)

        self._update_thresholds(state)
        self._update_sentiment(state)
        self._update_kronos(state)
        self._update_scores(state)
        self._check_stop_loss(db, symbol, current_price, state)

        if state.reference_price is None:
            state.reference_price = current_price
            return None

        pct_change = ((current_price - state.reference_price) / state.reference_price) * 100

        combined_signal = state.sentiment_score * SENTIMENT_WEIGHT + state.kronos_score * KRONOS_WEIGHT
        adjusted_buy = state.current_buy_threshold * (1 - combined_signal)
        adjusted_sell = state.current_sell_threshold * (1 + combined_signal)

        result = None
        if pct_change <= adjusted_buy and is_top_gainer:
            result = self._execute_buy(db, symbol, current_price, state)
            state.reference_price = current_price
        elif pct_change >= adjusted_sell:
            result = self._execute_sell(db, symbol, current_price, state)
            state.reference_price = current_price

        return result

    def _execute_buy(self, db: Session, symbol: str, price: float, state: CoinState) -> dict:
        portfolio = get_portfolio(db)
        trade_count = max(TRADE_TOP_N, 1)
        position_pct = 0.1 / trade_count
        qty_to_buy = (portfolio.balance * position_pct) / price

        if qty_to_buy * price > portfolio.balance or qty_to_buy <= 0:
            return {"action": "buy_skipped", "symbol": symbol, "reason": "insufficient_balance"}

        trade = Trade(
            pair=symbol,
            side="buy",
            price=price,
            quantity=qty_to_buy,
            profit_loss=0.0,
        )
        db.add(trade)
        db.commit()
        db.refresh(trade)

        state.open_lots.append({"price": price, "quantity": qty_to_buy})

        holdings = json.loads(portfolio.holdings)
        holdings[symbol] = holdings.get(symbol, 0.0) + qty_to_buy
        new_balance = portfolio.balance - (qty_to_buy * price)
        update_portfolio(db, balance=new_balance, holdings=holdings)

        return {
            "action": "buy",
            "symbol": symbol,
            "trade_id": trade.id,
            "price": price,
            "quantity": qty_to_buy,
            "momentum": round(state.momentum_score, 3),
            "sentiment": round(state.sentiment_score, 3),
            "kronos": round(state.kronos_score, 3),
        }

    def _execute_sell(self, db: Session, symbol: str, price: float, state: CoinState) -> dict:
        portfolio = get_portfolio(db)
        holdings = json.loads(portfolio.holdings)
        held_qty = holdings.get(symbol, 0.0)

        if held_qty <= 0 or not state.open_lots:
            return {"action": "sell_skipped", "symbol": symbol, "reason": "no_holdings"}

        qty_to_sell = held_qty * 0.5
        total_pnl = 0.0
        remaining = qty_to_sell

        while remaining > 0 and state.open_lots:
            oldest = state.open_lots[0]
            if oldest["quantity"] <= remaining:
                sell_qty = oldest["quantity"]
                total_pnl += (price - oldest["price"]) * sell_qty
                remaining -= sell_qty
                state.open_lots.pop(0)
            else:
                sell_qty = remaining
                total_pnl += (price - oldest["price"]) * sell_qty
                oldest["quantity"] -= sell_qty
                remaining = 0

        actual_sold = qty_to_sell - remaining
        if actual_sold <= 0:
            return {"action": "sell_skipped", "symbol": symbol, "reason": "no_qty"}

        trade = Trade(
            pair=symbol,
            side="sell",
            price=price,
            quantity=actual_sold,
            profit_loss=round(total_pnl, 2),
        )
        db.add(trade)
        db.commit()
        db.refresh(trade)

        holdings[symbol] = held_qty - actual_sold
        if holdings[symbol] <= 0:
            holdings.pop(symbol, None)

        new_balance = portfolio.balance + (actual_sold * price)
        update_portfolio(db, balance=new_balance, holdings=holdings)

        return {
            "action": "sell",
            "symbol": symbol,
            "trade_id": trade.id,
            "price": price,
            "quantity": actual_sold,
            "profit_loss": round(total_pnl, 2),
        }


multi_engine = MultiAssetEngine()
