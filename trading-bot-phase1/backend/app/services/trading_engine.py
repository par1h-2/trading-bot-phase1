import json
import math
from collections import deque

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app.core.constants import (
    DEFAULT_SYMBOL,
    FALLBACK_BUY_PCT,
    FALLBACK_SELL_PCT,
    MIN_TICKS_FOR_VOLATILITY,
    PRICE_HISTORY_SIZE,
    PRICE_POLL_INTERVAL,
    SCAN_INTERVAL,
    SENTIMENT_WEIGHT,
    STOP_LOSS_PCT,
    VOLATILITY_MULTIPLIER,
)
from app.models.database import SessionLocal
from app.models.portfolio import Portfolio
from app.models.trade import Trade
from app.services.market_data import get_current_price
from app.services.multi_asset_engine import multi_engine
from app.services.portfolio import get_portfolio, update_portfolio
from app.services.sentiment_analyzer import analyze_sentiment
from app.services.news_fetcher import fetch_all_news


class TradingEngine:
    def __init__(self):
        self.running = False
        self.mode: str = "single"
        self.last_price: float | None = None
        self.reference_price: float | None = None
        self.price_history: deque = deque(maxlen=PRICE_HISTORY_SIZE)
        self.current_buy_threshold: float = FALLBACK_BUY_PCT
        self.current_sell_threshold: float = FALLBACK_SELL_PCT
        self.scheduler = BackgroundScheduler()
        self.open_lots: list[dict] = []
        self.sentiment_score: float = 0.0
        self.sentiment_data: dict = {}

    def start(self, mode: str = "single"):
        if self.running:
            return
        self.running = True
        self.mode = mode

        if mode == "multi":
            multi_engine.start()
        else:
            if not self.scheduler.running:
                self.scheduler.add_job(
                    self._auto_tick,
                    "interval",
                    seconds=PRICE_POLL_INTERVAL,
                    id="auto_tick",
                    replace_existing=True,
                )
                self.scheduler.start()
            else:
                self.scheduler.resume_job("auto_tick")

        if not self.scheduler.running:
            self.scheduler.add_job(
                self._auto_scan,
                "interval",
                seconds=SCAN_INTERVAL,
                id="auto_scan",
                replace_existing=True,
            )
            self.scheduler.start()
        else:
            try:
                self.scheduler.resume_job("auto_scan")
            except Exception:
                self.scheduler.add_job(
                    self._auto_scan,
                    "interval",
                    seconds=SCAN_INTERVAL,
                    id="auto_scan",
                    replace_existing=True,
                )

    def stop(self):
        self.running = False
        multi_engine.stop()
        if self.scheduler.running:
            try:
                self.scheduler.pause_job("auto_tick")
            except Exception:
                pass
            try:
                self.scheduler.pause_job("auto_scan")
            except Exception:
                pass

    def _auto_tick(self):
        if not self.running or self.mode != "single":
            return
        db = SessionLocal()
        try:
            self.tick(db)
        finally:
            db.close()

    def _auto_scan(self):
        if not self.running or self.mode != "multi":
            return
        db = SessionLocal()
        try:
            multi_engine.tick(db)
        finally:
            db.close()

    def get_status(self) -> dict:
        status = {
            "running": self.running,
            "mode": self.mode,
            "last_price": self.last_price,
            "reference_price": self.reference_price,
            "current_buy_threshold": round(self.current_buy_threshold, 4),
            "current_sell_threshold": round(self.current_sell_threshold, 4),
            "price_history_count": len(self.price_history),
            "sentiment_score": round(self.sentiment_score, 3),
        }
        if self.mode == "multi":
            status.update(multi_engine.get_status())
        return status

    def _calculate_volatility(self) -> float:
        if len(self.price_history) < MIN_TICKS_FOR_VOLATILITY:
            return 0.0
        prices = list(self.price_history)
        mean = sum(prices) / len(prices)
        variance = sum((p - mean) ** 2 for p in prices) / len(prices)
        std_dev = math.sqrt(variance)
        current_price = prices[-1]
        if current_price == 0:
            return 0.0
        return (std_dev / current_price) * 100

    def _update_thresholds(self):
        if len(self.price_history) < MIN_TICKS_FOR_VOLATILITY:
            self.current_buy_threshold = FALLBACK_BUY_PCT
            self.current_sell_threshold = FALLBACK_SELL_PCT
            return
        volatility_pct = self._calculate_volatility()
        threshold = volatility_pct * VOLATILITY_MULTIPLIER
        self.current_buy_threshold = -threshold
        self.current_sell_threshold = threshold

    def _check_stop_loss(self, db: Session, current_price: float):
        if not self.open_lots:
            return

        portfolio = get_portfolio(db)
        holdings = json.loads(portfolio.holdings)
        held_qty = holdings.get(DEFAULT_SYMBOL, 0.0)

        lots_to_remove = []
        for i, lot in enumerate(self.open_lots):
            pct_change = ((current_price - lot["price"]) / lot["price"]) * 100
            if pct_change <= STOP_LOSS_PCT:
                lots_to_remove.append(i)

        for i in reversed(lots_to_remove):
            lot = self.open_lots.pop(i)
            pnl = (current_price - lot["price"]) * lot["quantity"]

            trade = Trade(
                pair=DEFAULT_SYMBOL,
                side="sell",
                price=current_price,
                quantity=lot["quantity"],
                profit_loss=round(pnl, 2),
            )
            db.add(trade)
            db.commit()

            held_qty -= lot["quantity"]
            if held_qty <= 0:
                holdings.pop(DEFAULT_SYMBOL, None)
            else:
                holdings[DEFAULT_SYMBOL] = held_qty

        if lots_to_remove:
            new_balance = portfolio.balance + held_qty * current_price
            update_portfolio(db, balance=new_balance, holdings=holdings)

    def _update_sentiment(self):
        try:
            articles = fetch_all_news(DEFAULT_SYMBOL)
            result = analyze_sentiment(articles)
            self.sentiment_score = result["score"]
            self.sentiment_data = result
        except Exception:
            self.sentiment_score = 0.0

    def tick(self, db: Session) -> dict | None:
        if not self.running or self.mode != "single":
            return None

        current_price = get_current_price(DEFAULT_SYMBOL)
        self.last_price = current_price
        self.price_history.append(current_price)

        self._update_thresholds()
        self._update_sentiment()
        self._check_stop_loss(db, current_price)

        if self.reference_price is None:
            self.reference_price = current_price
            return None

        pct_change = ((current_price - self.reference_price) / self.reference_price) * 100

        adjusted_buy = self.current_buy_threshold * (1 - self.sentiment_score * SENTIMENT_WEIGHT)
        adjusted_sell = self.current_sell_threshold * (1 + self.sentiment_score * SENTIMENT_WEIGHT)

        result = None
        if pct_change <= adjusted_buy:
            result = self._execute_buy(db, current_price)
            self.reference_price = current_price
        elif pct_change >= adjusted_sell:
            result = self._execute_sell(db, current_price)
            self.reference_price = current_price

        return result

    def _execute_buy(self, db: Session, price: float) -> dict:
        portfolio = get_portfolio(db)
        qty_to_buy = (portfolio.balance * 0.1) / price

        if qty_to_buy * price > portfolio.balance or qty_to_buy <= 0:
            return {"action": "buy_skipped", "reason": "insufficient_balance"}

        trade = Trade(
            pair=DEFAULT_SYMBOL,
            side="buy",
            price=price,
            quantity=qty_to_buy,
            profit_loss=0.0,
        )
        db.add(trade)
        db.commit()
        db.refresh(trade)

        self.open_lots.append({"price": price, "quantity": qty_to_buy})

        holdings = json.loads(portfolio.holdings)
        holdings[DEFAULT_SYMBOL] = holdings.get(DEFAULT_SYMBOL, 0.0) + qty_to_buy
        new_balance = portfolio.balance - (qty_to_buy * price)
        update_portfolio(db, balance=new_balance, holdings=holdings)

        return {
            "action": "buy",
            "trade_id": trade.id,
            "price": price,
            "quantity": qty_to_buy,
            "threshold_used": round(self.current_buy_threshold, 4),
        }

    def _execute_sell(self, db: Session, price: float) -> dict:
        portfolio = get_portfolio(db)
        holdings = json.loads(portfolio.holdings)
        held_qty = holdings.get(DEFAULT_SYMBOL, 0.0)

        if held_qty <= 0 or not self.open_lots:
            return {"action": "sell_skipped", "reason": "no_holdings"}

        qty_to_sell = held_qty * 0.5
        total_pnl = 0.0
        remaining = qty_to_sell

        while remaining > 0 and self.open_lots:
            oldest = self.open_lots[0]
            if oldest["quantity"] <= remaining:
                sell_qty = oldest["quantity"]
                total_pnl += (price - oldest["price"]) * sell_qty
                remaining -= sell_qty
                self.open_lots.pop(0)
            else:
                sell_qty = remaining
                total_pnl += (price - oldest["price"]) * sell_qty
                oldest["quantity"] -= sell_qty
                remaining = 0

        actual_sold = qty_to_sell - remaining
        if actual_sold <= 0:
            return {"action": "sell_skipped", "reason": "no_qty"}

        trade = Trade(
            pair=DEFAULT_SYMBOL,
            side="sell",
            price=price,
            quantity=actual_sold,
            profit_loss=round(total_pnl, 2),
        )
        db.add(trade)
        db.commit()
        db.refresh(trade)

        holdings[DEFAULT_SYMBOL] = held_qty - actual_sold
        if holdings[DEFAULT_SYMBOL] <= 0:
            holdings.pop(DEFAULT_SYMBOL, None)

        new_balance = portfolio.balance + (actual_sold * price)
        update_portfolio(db, balance=new_balance, holdings=holdings)

        return {
            "action": "sell",
            "trade_id": trade.id,
            "price": price,
            "quantity": actual_sold,
            "profit_loss": round(total_pnl, 2),
            "threshold_used": round(self.current_sell_threshold, 4),
        }


bot_engine = TradingEngine()
