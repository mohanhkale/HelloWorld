"""Tests for EMA strategy and historical backtest simulation."""

import unittest

from outputs.strat_01.backtest import simulate
from outputs.strat_01.strategy import EmaCrossover


class EmaTests(unittest.TestCase):
    def test_requires_warmup_and_detects_crossover(self):
        engine = EmaCrossover("TEST", 2, 3)
        values = [10, 9, 8, 9, 10, 11]
        signals = [engine.update(value, str(i)) for i, value in enumerate(values)]
        self.assertTrue(any(signal and signal.side == "BUY" for signal in signals))

    def test_duplicate_prices_are_ignored(self):
        engine = EmaCrossover("TEST", 2, 3)
        self.assertIsNone(engine.update(10))
        self.assertIsNone(engine.update(10))
        self.assertEqual(engine.samples, 1)

    def test_invalid_periods_rejected(self):
        with self.assertRaises(ValueError):
            EmaCrossover("TEST", 11, 9)

    def test_backtest_closes_long_on_bearish_cross(self):
        bars = [(str(i), value) for i, value in enumerate([10, 9, 8, 9, 11, 12, 11, 9, 8])]
        trades, open_position = simulate(bars, 2, 3)
        self.assertIsNone(open_position)
        self.assertEqual(len(trades), 1)
        self.assertGreater(trades[0].exit_price, trades[0].entry_price)


if __name__ == "__main__":
    unittest.main()
