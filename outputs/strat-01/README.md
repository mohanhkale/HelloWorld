# EMA 9/11 Kotak Neo signal monitor

This folder re-structures the repository's existing index-feed script as a small Python package using the actively maintained Kotak Neo Python SDK (`kotakneoapi` v3). It runs **market-data only**: it reports EMA crossover signals and does not submit, modify, or cancel orders.

## Strategy in brief

- Subscribe to the configured NSE index names through Kotak Neo's async SFeed `subscribe_index()` stream.
- Maintain a 9-period fast EMA and an 11-period slow EMA for each index, updating once per distinct delivered index price.
- After at least 11 distinct price updates, report a bullish cross when EMA 9 moves from at/below EMA 11 to above it; report a bearish cross for the reverse.
- The periods are counts of **feed updates**, not 9- and 11-minute bars. This is a tick-based signal monitor and does not claim to be a candle-based or backtested profitable strategy.
- Signals are informational only. No entry sizing, stop-loss, take-profit, trading hours, position management, or order execution is implemented.

## Repository structure

```text
outputs/strat-01/
├── config.py       # Validates environment configuration
├── main.py         # TOTP auth and async Kotak Neo SFeed consumer
├── strategy.py     # Pure EMA crossover logic; no broker calls
├── test_strategy.py
├── .env.example
└── README.md
```

The old root-level `EMA 9X11 Intraday Strat.py` is retained as a safe launcher. Its former inline credentials and legacy callback WebSocket usage have been removed.

## Setup (Windows PowerShell)

From the repository root:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r outputs/strat-01/requirements.txt
Copy-Item outputs/strat-01/.env.example .env
```

Set the four required values in `.env`, or set them in the shell environment. The app currently reads environment variables directly; it does not automatically load `.env`. For a PowerShell session, for example:

```powershell
$env:NEO_CONSUMER_KEY = "your-consumer-key"
$env:NEO_MOBILE_NUMBER = "+91XXXXXXXXXX"
$env:NEO_UCC = "your-UCC"
$env:NEO_MPIN = "your-MPIN"
$env:NEO_INDEX_NAMES = "Nifty Bank,Nifty IT,Nifty Auto"
```

Then run from the repository root:

```powershell
python -m outputs.strat-01.main
```

A current authenticator TOTP is requested interactively and is not saved. Ctrl+C stops the stream. `NEO_INDEX_NAMES` must contain names supported by the account/feed; `EMA_FAST_PERIOD` and `EMA_SLOW_PERIOD` can optionally override 9/11 while satisfying `fast < slow`.

## Tests

The pure strategy tests need no SDK session or live connection:

```powershell
python -m unittest outputs.strat-01.test_strategy
```

## Important security and trading notes

- The original script contained credential-like values committed in source. Treat them as compromised: revoke/rotate the Kotak Neo consumer key and MPIN, review account activity, and never reuse those values. Removing them from the current file does not erase them from Git history.
- Do not use a signal as an order instruction without independent validation. Index feeds are not themselves a tradable instrument; any derivative mapping, quantity, expiry, order type, risk limit, and square-off policy would need explicit design and testing.
- Verify index naming, subscription permissions, feed behavior, SDK version, and market hours in a non-production setup before relying on live data. Network gaps and feed updates can affect tick-based EMAs.
