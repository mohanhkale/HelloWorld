"""Backward-compatible launcher for the restructured signal monitor.

Live credentials and the removed legacy callback-WebSocket code are intentionally
not embedded here. See outputs/strat-01/README.md for configuration and usage.
"""

from outputs.strat_01 import main

if __name__ == "__main__":
    main.main()
