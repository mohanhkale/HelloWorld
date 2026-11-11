# Kotak Neo EMA 9/11 strategy tools

Canonical executable Python package: `outputs/strat_01/` (underscore is needed for Python imports). The earlier `outputs/strat-01/` directory remains as the original deliverable/reference. Run commands from the repository root.

## 1. Historical-candle backtest

Fetches Kotak Neo candles for a caller-specified exchange segment and token, calculates EMA crosses on completed candle closes, and simulates long-only entries on BUY and exits on SELL. It does not short, does not force-close the final open position, and writes completed trades to CSV. Results omit taxes/fees unless approximated using `--cost-bps`, and historical results are not a guarantee of future performance.

```powershell
pip install -r outputs/strat-01/requirements.txt
$env:NEO_CONSUMER_KEY="..."
$env:NEO_MOBILE_NUMBER="+91..."
$env:NEO_UCC="..."
$env:NEO_MPIN="..."
python -m outputs.strat_01.backtest --symbol "nse_cm|1333" --from 2026-01-01 --to 2026-01-30 --interval 5min --fast 9 --slow 11 --cost-bps 5
```

Use a valid Kotak Neo `exchange_segment|instrument_token`; instrument identifiers must be checked against the current scrip master. API historical-data limits apply (5-minute candles: at most 30 days per request). Configure one supported interval, no wider than the API range. The TOTP is prompted securely.

## 2. CSV live signal logger

```powershell
$env:NEO_TRADE_SYMBOL="RELIANCE-EQ"
$env:NEO_TRADE_TOKEN="verified-scrip-token"
$env:SIGNALS_CSV="outputs/strat-01/signals.csv"
python -m outputs.strat_01.signal_logger
```

Appends only qualified EMA crossover events (BUY/SELL), with timestamp, instrument, close/last price, EMA values, and sample count. It logs signals and never submits orders. This is tick-based; EMA periods count distinct feed price updates, unlike the candle backtest.

## 3. Guarded execution example — NOT turnkey production-ready

```powershell
$env:NEO_TRADE_SYMBOL="RELIANCE-EQ"
$env:NEO_TRADE_TOKEN="verified-scrip-token"
$env:NEO_ORDER_QUANTITY="1"
$env:NEO_MAX_ENTRIES_PER_DAY="1"
python -m outputs.strat_01.execution
```

Default is dry-run. For deliberate live testing only, set both `ENABLE_LIVE_TRADING=YES` and `LIVE_TRADING_CONFIRM=I_ACCEPT_LIVE_ORDER_RISK`. It uses market MIS orders: BUY crossover enters a configured long position, SELL crossover exits that position. It does not short. A failed/ambiguous order call halts further orders; inspect Neo order book and positions before any restart. Do not retry an uncertain order blindly.

This cannot honestly be called production-ready without account-specific validation. It has no stop-loss/target, broker-position reconciliation after restart, guaranteed end-of-day square-off, partial-fill handling, order-feed verification, market-hours calendar, or verified instrument/quantity suitability. Add and test those controls, use tiny size and supervised/dry runs, and obtain qualified compliance/financial review before considering live use. MIS positions and market orders can lose money rapidly.

## Strategy details and limits

- Fast EMA is 9; slow EMA is 11 (override with `EMA_FAST_PERIOD` and `EMA_SLOW_PERIOD`).
- EMA values initialize from the first observed price; signals are suppressed until more than the slow period of distinct observations are present.
- BUY occurs only when fast EMA crosses from at/below slow to above it. SELL occurs only on the reverse cross.
- Backtest evaluates once per completed candle close; live logger/execution evaluate on distinct ticks. These are different strategies in sampling terms and their outcomes are not directly comparable.
- Backtest simulation is long-only, close-price fills, no market impact, and no open-trade mark-to-market. `--cost-bps` estimates a one-way cost on entry and exit, but does not model actual brokerage/taxes.
- No profitability is implied. Backtest across multiple regimes, account for survivorship/data quality and realistic costs, then paper-test.

## Tests

```powershell
python -m unittest outputs.strat_01.test_strategy
```

Do not commit `.env` or real credentials. Rotate the credential-like values previously present in Git history; deleting the current copy does not remove historical commits.
