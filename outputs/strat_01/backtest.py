"""Fetch Kotak Neo historical candles and run a simple, long-only EMA backtest.

Example: python -m outputs.strat_01.backtest --symbol 'nse_cm|1333' --from 2026-01-01 --to 2026-01-31
"""

from __future__ import annotations

import argparse
import csv
import getpass
import logging
import math
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from neo_api_client import NeoAPI

from .config import Settings
from .strategy import EmaCrossover

logger = logging.getLogger("strat-01.backtest")


@dataclass(frozen=True)
class Trade:
    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    gross_return_pct: float
    net_return_pct: float


def get_candles(response: dict) -> list[tuple[str, float]]:
    try:
        rows = response["data"]["candles"]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"Kotak Neo did not return candle data: {response!r}") from exc
    bars = []
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) < 5:
            continue
        timestamp, close = str(row[0]), float(row[4])
        if math.isfinite(close) and close > 0:
            bars.append((timestamp, close))
    return bars


def simulate(bars: list[tuple[str, float]], fast: int, slow: int, cost_bps: float = 0.0):
    """Enter on BUY, exit on SELL; charge cost_bps on each side of each trade."""
    if cost_bps < 0:
        raise ValueError("cost-bps cannot be negative")
    engine = EmaCrossover("backtest", fast, slow)
    position: tuple[str, float] | None = None
    trades: list[Trade] = []
    cost_fraction = cost_bps / 10_000
    for timestamp, close in bars:
        signal = engine.update(close, timestamp)
        if signal is None:
            continue
        if signal.side == "BUY" and position is None:
            position = (timestamp, close)
        elif signal.side == "SELL" and position is not None:
            entry_time, entry = position
            gross = (close / entry - 1) * 100
            net = ((close * (1 - cost_fraction)) / (entry * (1 + cost_fraction)) - 1) * 100
            trades.append(Trade(entry_time, timestamp, entry, close, gross, net))
            position = None
    # Open positions are not force-closed on the final bar; report them as open.
    return trades, position


def write_trades(path: Path, trades: list[Trade]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(Trade.__dataclass_fields__))
        writer.writeheader()
        writer.writerows(trade.__dict__ for trade in trades)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default=os.getenv("NEO_BACKTEST_SYMBOL"), help="Neo symbol: exchange_segment|token")
    parser.add_argument("--from", dest="from_date", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--to", dest="to_date", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--interval", default="5min", choices=("1min", "3min", "5min", "10min", "15min", "30min", "60min", "D", "W"))
    parser.add_argument("--fast", type=int, default=9)
    parser.add_argument("--slow", type=int, default=11)
    parser.add_argument("--cost-bps", type=float, default=0.0, help="Estimated one-way fees/slippage in basis points")
    parser.add_argument("--output", type=Path, default=Path("outputs/strat-01/backtest_trades.csv"))
    args = parser.parse_args()
    if not args.symbol or "|" not in args.symbol:
        parser.error("--symbol or NEO_BACKTEST_SYMBOL is required (format nse_cm|instrument_token)")
    if args.fast < 1 or args.fast >= args.slow:
        parser.error("Periods must satisfy 1 <= --fast < --slow")
    try:
        start, end = date.fromisoformat(args.from_date), date.fromisoformat(args.to_date)
    except ValueError as exc:
        parser.error(str(exc))
    max_days = 30 if args.interval in {"1min", "3min", "5min"} else 60 if args.interval in {"10min", "15min"} else 90 if args.interval in {"30min", "60min"} else 180
    if start > end or (end - start).days > max_days:
        parser.error(f"Date range must be ordered and no longer than {max_days} days for {args.interval}")

    settings = Settings.from_env()
    client = NeoAPI(consumer_key=settings.consumer_key, environment=settings.environment)
    try:
        # Historical candles require consumer key; login is performed for consistent account access.
        client.totp_login(mobile_number=settings.mobile_number, ucc=settings.ucc, totp=getpass.getpass("Current Kotak Neo TOTP: ").strip())
        client.totp_validate(mpin=settings.mpin)
        response = client.historical_data(args.symbol, args.interval, args.from_date, args.to_date)
    finally:
        try:
            client.logout()
        except Exception:
            logger.debug("Logout failed or session was not established", exc_info=True)

    bars = get_candles(response)
    if not bars:
        raise RuntimeError("No valid candle rows were returned.")
    trades, open_position = simulate(bars, args.fast, args.slow, args.cost_bps)
    write_trades(args.output, trades)
    winners = sum(trade.net_return_pct > 0 for trade in trades)
    net_total = sum(trade.net_return_pct for trade in trades)
    print(f"Bars: {len(bars)} | Closed trades: {len(trades)} | Win rate: {winners / len(trades):.1%}" if trades else f"Bars: {len(bars)} | Closed trades: 0")
    print(f"Sum of net trade returns (not compounded): {net_total:.3f}% | Trades CSV: {args.output}")
    if open_position:
        print(f"Open at end of sample (excluded from results): entry={open_position[1]:.2f} at {open_position[0]}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
