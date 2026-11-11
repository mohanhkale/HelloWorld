"""Tick-based EMA crossover signal logic. This module never places orders."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Signal:
    instrument: str
    direction: str
    price: float
    fast_ema: float
    slow_ema: float
    samples: int


class EmaCrossover:
    """Detect fast/slow EMA crosses from distinct live price updates.

    This is deliberately a tick EMA (not a candle/timeframe EMA). It waits for
    ``slow_period`` distinct prices before emitting any crossover signals.
    """

    def __init__(self, instrument: str, fast_period: int = 9, slow_period: int = 11):
        if fast_period < 1 or slow_period < 2 or fast_period >= slow_period:
            raise ValueError("EMA periods must satisfy 1 <= fast < slow.")
        self.instrument = instrument
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.fast_alpha = 2.0 / (fast_period + 1)
        self.slow_alpha = 2.0 / (slow_period + 1)
        self.fast_ema: float | None = None
        self.slow_ema: float | None = None
        self.previous_fast: float | None = None
        self.previous_slow: float | None = None
        self.samples = 0
        self._last_price: float | None = None

    def update(self, price: float) -> Signal | None:
        price = float(price)
        if price <= 0:
            return None
        if self._last_price == price:
            return None
        self._last_price = price
        self.samples += 1

        self.previous_fast, self.previous_slow = self.fast_ema, self.slow_ema
        if self.fast_ema is None:
            self.fast_ema = self.slow_ema = price
            return None
        self.fast_ema += self.fast_alpha * (price - self.fast_ema)
        self.slow_ema += self.slow_alpha * (price - self.slow_ema)

        if self.samples <= self.slow_period:
            return None
        if self.previous_fast is None or self.previous_slow is None:
            return None

        if self.previous_fast <= self.previous_slow and self.fast_ema > self.slow_ema:
            direction = "BULLISH_CROSS"
        elif self.previous_fast >= self.previous_slow and self.fast_ema < self.slow_ema:
            direction = "BEARISH_CROSS"
        else:
            return None

        return Signal(
            instrument=self.instrument,
            direction=direction,
            price=price,
            fast_ema=self.fast_ema,
            slow_ema=self.slow_ema,
            samples=self.samples,
        )
