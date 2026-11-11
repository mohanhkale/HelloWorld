"""Backward-compatible launcher for the signal-only monitor.

For backtesting, CSV signal logging, and the guarded execution example, see
outputs/strat_01/README.md. Real credentials are not embedded in source.
"""

from outputs.strat_01.signal_logger import main

if __name__ == "__main__":
    main()
