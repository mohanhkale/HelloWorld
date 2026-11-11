"""EMA crossover calculation shared by live signals and historical backtests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Signal:
    timestamp: str
    instrument: str
    side: str
    price: float
    fast_ema: float
    slow_ema: float
    samples: int


class EmaCrossover:
    """Detect bullish/bearish crosses; timestamps and prices are supplied by caller."""

    def __init__(self, instrument: str, fast_period: int = 9, slow_period: int = 11):
        if fast_period < 1 or slow_period < 2 or fast_period >= slow_period:
            raise ValueError("EMA periods must satisfy 1 <= fast < slow.")
        self.instrument = instrument
        self.fast_period = fast_period
        self.slow_period = slow_period
        self._fast_alpha = 2.0 / (fast_period + 1)
        self._slow_alpha = 2.0 / (slow_period + 1)
        self.fast_ema: float | None = None
        self.slow_ema: float | None = None
        self._previous_fast: float | None = None
        self._previous_slow: float | None = None
        self.samples = 0
        self._last_price: float | None = None

    def update(self, price: float, timestamp: str = "") -> Signal | None:
        price = float(price)
        if price <= 0:
            return None
        if self._last_price == price:
            return None
        self._last_price = price
        self.samples += 1
        self._previous_fast, self._previous_slow = self.fast_ema, self.slow_ema
        if self.fast_ema is None:
            self.fast_ema = self.slow_ema = price
            return None
        self.fast_ema += self._fast_alpha * (price - self.fast_ema)
        self.slow_ema += self._slow_alpha * (price - self.slow_ema)
        if self.samples <= self.slow_period or self._previous_fast is None or self._previous_slow is None:
            return None
        if self._previous_fast <= self._previous_slow and self.fast_ema > self.slow_ema:
            side = "BUY"
        elif self._previous_fast >= self._previous_slow and self.fast_ema < self.slow_ema:
            side = "SELL"
        else:
            return None
        return Signal(timestamp, self.instrument, side, price, self.fast_ema, self.slow_ema, self.samples)


def signals_from_closes(
    instrument: str,
    bars: Iterable[tuple[str, float]],
    fast_period: int = 9,
    slow_period: int = 11,
) -> list[Signal]:
    """Calculate one signal per completed candle close; no look-ahead is used."""
    engine = EmaCrossover(instrument, fast_period, slow_period)
    results = []
    for timestamp, close in bars:
        signal = engine.update(close, timestamp)
        if signal is not None:
            results.append(signal)
    return results
