import json
import math
from collections import deque
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from app.core.constants import (
    FALLBACK_BUY_PCT,
    FALLBACK_SELL_PCT,
    MIN_TICKS_FOR_VOLATILITY,
    PRICE_HISTORY_SIZE,
    STOP_LOSS_PCT,
    VOLATILITY_MULTIPLIER,
)
from app.services.performance_metrics import calculate_metrics


class BacktestEngine:
    def __init__(
        self,
        starting_balance: float = 10000.0,
        buy_pct: float | None = None,
        sell_pct: float | None = None,
        buy_size_pct: float = 10.0,
        sell_size_pct: float = 50.0,
        stop_loss_pct: float = STOP_LOSS_PCT,
    ):
        self.starting_balance = starting_balance
        self.balance = starting_balance
        self.holdings: dict[str, float] = {}
        self.trades: list[dict] = []
        self.equity_curve: list[float] = []

        self.buy_pct_override = buy_pct
        self.sell_pct_override = sell_pct
        self.buy_size_pct = buy_size_pct / 100.0
        self.sell_size_pct = sell_size_pct / 100.0
        self.stop_loss_pct = stop_loss_pct

        self.open_buys: list[dict] = []
        self.price_history: deque = deque(maxlen=PRICE_HISTORY_SIZE)
        self.reference_price: float | None = None
        self.current_buy_threshold = FALLBACK_BUY_PCT
        self.current_sell_threshold = FALLBACK_SELL_PCT

    def _calculate_volatility(self) -> float:
        if len(self.price_history) < MIN_TICKS_FOR_VOLATILITY:
            return 0.0
        prices = np.array(self.price_history)
        std_dev = np.std(prices)
        current_price = prices[-1]
        if current_price == 0:
            return 0.0
        return (std_dev / current_price) * 100

    def _check_stop_loss(self, current_price: float, ts: datetime):
        if not self.open_buys or self.stop_loss_pct >= 0:
            return

        lots_to_remove = []
        for i, lot in enumerate(self.open_buys):
            pct_change = ((current_price - lot["price"]) / lot["price"]) * 100
            if pct_change <= self.stop_loss_pct:
                lots_to_remove.append(i)

        for i in reversed(lots_to_remove):
            lot = self.open_buys.pop(i)
            pnl = (current_price - lot["price"]) * lot["quantity"]
            self.balance += lot["quantity"] * current_price
            self.holdings["BTCUSDT"] = self.holdings.get("BTCUSDT", 0.0) - lot["quantity"]
            if self.holdings.get("BTCUSDT", 0) <= 0:
                self.holdings.pop("BTCUSDT", None)

            self.trades.append({
                "side": "sell",
                "price": current_price,
                "quantity": lot["quantity"],
                "timestamp": ts,
                "profit_loss": round(pnl, 2),
                "reason": "stop_loss",
            })

    def _update_thresholds(self):
        if self.buy_pct_override is not None and self.sell_pct_override is not None:
            self.current_buy_threshold = self.buy_pct_override
            self.current_sell_threshold = self.sell_pct_override
            return

        if len(self.price_history) < MIN_TICKS_FOR_VOLATILITY:
            self.current_buy_threshold = FALLBACK_BUY_PCT
            self.current_sell_threshold = FALLBACK_SELL_PCT
            return

        volatility_pct = self._calculate_volatility()
        threshold = volatility_pct * VOLATILITY_MULTIPLIER
        self.current_buy_threshold = -threshold
        self.current_sell_threshold = threshold

    def run(self, candles: list[dict]) -> dict:
        if not candles:
            return {"trades": [], "equity_curve": [], "metrics": {}}

        df = pd.DataFrame(candles)
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce")

        if self.buy_pct_override is not None and self.sell_pct_override is not None:
            result = self._run_vectorized_fixed_threshold(df)
        else:
            result = self._run_vectorized_adaptive(df)

        return result

    def _run_vectorized_fixed_threshold(self, df: pd.DataFrame) -> dict:
        buy_threshold = self.buy_pct_override
        sell_threshold = self.sell_pct_override

        closes = df["close"].values
        timestamps = df["timestamp"].values
        n = len(closes)

        ref_price = closes[0]
        pct_changes = np.zeros(n)
        buy_signals = np.zeros(n, dtype=bool)
        sell_signals = np.zeros(n, dtype=bool)

        for i in range(1, n):
            pct_changes[i] = ((closes[i] - ref_price) / ref_price) * 100
            if pct_changes[i] <= buy_threshold:
                buy_signals[i] = True
                ref_price = closes[i]
            elif pct_changes[i] >= sell_threshold:
                sell_signals[i] = True
                ref_price = closes[i]

        equity = np.zeros(n)
        equity[0] = self.starting_balance

        for i in range(1, n):
            ts = datetime.fromtimestamp(timestamps[i] / 1000, tz=timezone.utc).replace(tzinfo=None)

            self._check_stop_loss(closes[i], ts)

            if buy_signals[i]:
                self._execute_buy(closes[i], ts)
            elif sell_signals[i]:
                self._execute_sell(closes[i], ts)

            holdings_value = sum(qty * closes[i] for qty in self.holdings.values())
            equity[i] = round(self.balance + holdings_value, 2)

        self._close_remaining_positions(closes[-1], timestamps[-1])

        self.equity_curve = equity.tolist()
        metrics = calculate_metrics(self.trades, self.starting_balance, self.equity_curve)

        return {
            "trades": self.trades,
            "equity_curve": self._downsample_equity_curve(),
            "metrics": metrics,
        }

    def _run_vectorized_adaptive(self, df: pd.DataFrame) -> dict:
        closes = df["close"].values
        timestamps = df["timestamp"].values
        n = len(closes)

        ref_price = closes[0]
        equity = np.zeros(n)
        equity[0] = self.starting_balance

        for i in range(1, n):
            ts = datetime.fromtimestamp(timestamps[i] / 1000, tz=timezone.utc).replace(tzinfo=None)

            self.price_history.append(closes[i])
            self._update_thresholds()

            self._check_stop_loss(closes[i], ts)

            pct_change = ((closes[i] - ref_price) / ref_price) * 100

            if pct_change <= self.current_buy_threshold:
                self._execute_buy(closes[i], ts)
                ref_price = closes[i]
            elif pct_change >= self.current_sell_threshold:
                self._execute_sell(closes[i], ts)
                ref_price = closes[i]

            holdings_value = sum(qty * closes[i] for qty in self.holdings.values())
            equity[i] = round(self.balance + holdings_value, 2)

        self._close_remaining_positions(closes[-1], timestamps[-1])

        self.equity_curve = equity.tolist()
        metrics = calculate_metrics(self.trades, self.starting_balance, self.equity_curve)

        return {
            "trades": self.trades,
            "equity_curve": self._downsample_equity_curve(),
            "metrics": metrics,
        }

    def _downsample_equity_curve(self) -> list[float]:
        if len(self.equity_curve) <= 1000:
            return self.equity_curve
        step = len(self.equity_curve) // 500
        downsampled = self.equity_curve[::step]
        if self.equity_curve[-1] != downsampled[-1]:
            downsampled.append(self.equity_curve[-1])
        return downsampled

    def _execute_buy(self, price: float, ts: datetime):
        qty_to_buy = (self.balance * self.buy_size_pct) / price
        if qty_to_buy * price > self.balance or qty_to_buy <= 0:
            return

        self.balance -= qty_to_buy * price
        self.holdings["BTCUSDT"] = self.holdings.get("BTCUSDT", 0.0) + qty_to_buy

        self.open_buys.append({
            "price": price,
            "quantity": qty_to_buy,
        })

        self.trades.append({
            "side": "buy",
            "price": price,
            "quantity": qty_to_buy,
            "timestamp": ts,
            "profit_loss": 0.0,
        })

    def _execute_sell(self, price: float, ts: datetime):
        held_qty = self.holdings.get("BTCUSDT", 0.0)
        if held_qty <= 0 or not self.open_buys:
            return

        qty_to_sell = held_qty * self.sell_size_pct
        total_pnl = 0.0
        remaining = qty_to_sell

        while remaining > 0 and self.open_buys:
            oldest = self.open_buys[0]
            if oldest["quantity"] <= remaining:
                sell_qty = oldest["quantity"]
                pnl = (price - oldest["price"]) * sell_qty
                total_pnl += pnl
                remaining -= sell_qty
                self.open_buys.pop(0)
            else:
                sell_qty = remaining
                pnl = (price - oldest["price"]) * sell_qty
                total_pnl += pnl
                oldest["quantity"] -= sell_qty
                remaining = 0

        actual_sold = qty_to_sell - remaining
        if actual_sold <= 0:
            return

        self.balance += actual_sold * price
        self.holdings["BTCUSDT"] = held_qty - actual_sold
        if self.holdings["BTCUSDT"] <= 0:
            self.holdings.pop("BTCUSDT", None)

        self.trades.append({
            "side": "sell",
            "price": price,
            "quantity": actual_sold,
            "timestamp": ts,
            "profit_loss": round(total_pnl, 2),
        })

    def _close_remaining_positions(self, last_price: float, last_ts: int):
        if not self.open_buys:
            return
        ts = datetime.fromtimestamp(last_ts / 1000, tz=timezone.utc).replace(tzinfo=None)
        held_qty = self.holdings.get("BTCUSDT", 0.0)
        if held_qty <= 0:
            return

        total_pnl = 0.0
        for buy in self.open_buys:
            total_pnl += (last_price - buy["price"]) * buy["quantity"]

        self.balance += held_qty * last_price
        self.holdings.clear()
        self.open_buys.clear()

        self.trades.append({
            "side": "sell",
            "price": last_price,
            "quantity": held_qty,
            "timestamp": ts,
            "profit_loss": round(total_pnl, 2),
        })
