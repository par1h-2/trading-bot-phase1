from dataclasses import dataclass


@dataclass
class PerformanceMetrics:
    total_pnl: float
    win_rate: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_profit_per_trade: float
    max_drawdown: float
    max_drawdown_pct: float
    starting_balance: float
    final_balance: float


def calculate_metrics(
    trades: list[dict],
    starting_balance: float,
    equity_curve: list[float] | None = None,
) -> PerformanceMetrics:
    if not trades:
        return PerformanceMetrics(
            total_pnl=0.0,
            win_rate=0.0,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            avg_profit_per_trade=0.0,
            max_drawdown=0.0,
            max_drawdown_pct=0.0,
            starting_balance=starting_balance,
            final_balance=starting_balance,
        )

    winning = [t for t in trades if t.get("profit_loss", 0) > 0]
    losing = [t for t in trades if t.get("profit_loss", 0) < 0]
    total_pnl = sum(t.get("profit_loss", 0) for t in trades)
    final_balance = starting_balance + total_pnl

    win_rate = (len(winning) / len(trades)) * 100 if trades else 0.0
    avg_profit = total_pnl / len(trades) if trades else 0.0

    max_dd = 0.0
    max_dd_pct = 0.0
    if equity_curve and len(equity_curve) > 1:
        peak = equity_curve[0]
        for val in equity_curve:
            if val > peak:
                peak = val
            dd = peak - val
            dd_pct = (dd / peak) * 100 if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct

    return PerformanceMetrics(
        total_pnl=round(total_pnl, 2),
        win_rate=round(win_rate, 2),
        total_trades=len(trades),
        winning_trades=len(winning),
        losing_trades=len(losing),
        avg_profit_per_trade=round(avg_profit, 2),
        max_drawdown=round(max_dd, 2),
        max_drawdown_pct=round(max_dd_pct, 2),
        starting_balance=starting_balance,
        final_balance=round(final_balance, 2),
    )
