"""Safely validate local Kotak Neo credentials and fetch historical candles.

This script runs on the user's own machine. It never prints credential values,
never writes them to disk, and never places or modifies orders.
"""

from __future__ import annotations

import argparse
import csv
import getpass
import json
import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from neo_api_client import NeoAPI

DEFAULT_CONFIG = Path(
    r"C:\Users\Admin\Documents\Codex\2026-11-11\here-are-the-prompts-used-while\outputs\strat-01 configkey file"
)
logger = logging.getLogger("kotak-config-check")


def load_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Config file not found: {path}")
    raw = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".json" or raw.lstrip().startswith("{"):
        data = json.loads(raw)
    else:
        data: dict[str, Any] = {}
        for number, line in enumerate(raw.splitlines(), start=1):
            value = line.strip()
            if not value or value.startswith("#"):
                continue
            if "=" not in value:
                raise ValueError(f"Unsupported config format at line {number}; expected JSON or KEY=VALUE")
            key, item = value.split("=", 1)
            data[key.strip().lower()] = item.strip().strip("\"'")
    if not isinstance(data, dict):
        raise ValueError("Config must contain a JSON object or KEY=VALUE entries")

    aliases = {
        "consumer_key": ("consumer_key", "neo_consumer_key", "kotak_consumer_key"),
        "mobile_number": ("mobile_number", "neo_mobile_number", "kotak_mobile", "mobilenumber"),
        "ucc": ("ucc", "neo_ucc", "client_code"),
        "mpin": ("mpin", "neo_mpin", "kotak_mpin"),
    }
    normalized: dict[str, Any] = dict(data)
    for canonical, names in aliases.items():
        for name in names:
            if os.getenv(name.upper()):
                normalized[canonical] = os.environ[name.upper()]
                break
            if data.get(name):
                normalized[canonical] = data[name]
                break
    missing = [key for key in aliases if not normalized.get(key)]
    if missing:
        raise ValueError("Config is missing required fields: " + ", ".join(missing))
    return normalized


def resolve_symbols(config: dict[str, Any], args: argparse.Namespace) -> list[str]:
    symbols = list(args.symbol or [])
    if not symbols:
        for item in config.get("instruments", []):
            if not isinstance(item, dict):
                continue
            if item.get("neosymbol"):
                symbols.append(str(item["neosymbol"]))
            elif item.get("exchange_segment") and item.get("token"):
                symbols.append(f"{item['exchange_segment']}|{item['token']}")
            elif item.get("exchange_segment") and item.get("instrument_token"):
                symbols.append(f"{item['exchange_segment']}|{item['instrument_token']}")
    # Also accept one simple symbol/token in a KEY=VALUE or JSON file.
    if not symbols and config.get("neosymbol"):
        symbols.append(str(config["neosymbol"]))
    elif not symbols and config.get("exchange_segment") and config.get("instrument_token"):
        symbols.append(f"{config['exchange_segment']}|{config['instrument_token']}")
    return list(dict.fromkeys(symbols))


def fetch_chunked(client: NeoAPI, symbol: str, interval: str, start: date, end: date) -> list[list[Any]]:
    # Kotak's documented 15-minute request range limit is 60 calendar days.
    limit = 60 if interval in {"10min", "15min"} else 30 if interval in {"1min", "3min", "5min"} else 90 if interval in {"30min", "60min"} else 180
    rows: dict[str, list[Any]] = {}
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=limit - 1), end)
        response = client.historical_data(
            neosymbol=symbol,
            interval=interval,
            from_date=cursor.isoformat(),
            to_date=chunk_end.isoformat(),
        )
        candles = response.get("data", {}).get("candles", []) if isinstance(response, dict) else []
        for row in candles:
            if isinstance(row, (list, tuple)) and len(row) >= 6:
                rows[str(row[0])] = list(row[:7])
        cursor = chunk_end + timedelta(days=1)
    return [rows[key] for key in sorted(rows)]


def save_csv(output: Path, symbol: str, rows: list[list[Any]]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    new_file = not output.exists()
    with output.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        if new_file:
            writer.writerow(["neosymbol", "timestamp", "open", "high", "low", "close", "volume", "oi"])
        for row in rows:
            writer.writerow([symbol, *row])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(os.getenv("KOTAK_CONFIG_FILE", str(DEFAULT_CONFIG))))
    parser.add_argument("--symbol", action="append", help="Kotak symbol, e.g. nse_cm|1333; may be supplied more than once")
    parser.add_argument("--interval", default="15min", choices=("1min", "3min", "5min", "10min", "15min", "30min", "60min", "D", "W"))
    parser.add_argument("--sessions", type=int, default=20, help="Number of recent trading sessions to report")
    parser.add_argument("--output", type=Path, default=Path("outputs/strat_01/kotak_candles.csv"))
    args = parser.parse_args()
    if args.sessions < 1:
        parser.error("--sessions must be positive")

    config = load_config(args.config)
    symbols = resolve_symbols(config, args)
    if not symbols:
        parser.error("No instrument configured. Add instruments to JSON or pass --symbol nse_cm|TOKEN")

    # Request a calendar buffer for weekends/holidays and indicator warm-up.
    calendar_days = max(60, args.sessions * 2 + 20)
    end = date.today()
    start = end - timedelta(days=calendar_days)
    totp = getpass.getpass("Current Kotak Neo TOTP (not saved): ").strip()
    if not totp:
        parser.error("A current TOTP is required to validate the trading login")

    client = NeoAPI(
        consumer_key=str(config["consumer_key"]),
        environment=str(config.get("environment", "prod")),
    )
    try:
        client.totp_login(
            mobile_number=str(config["mobile_number"]),
            ucc=str(config["ucc"]),
            totp=totp,
        )
        client.totp_validate(mpin=str(config["mpin"]))
        print("Kotak Neo authentication succeeded (credential values were not displayed).")
        total_rows = 0
        for symbol in symbols:
            rows = fetch_chunked(client, symbol, args.interval, start, end)
            if not rows:
                print(f"No candles returned for {symbol}; check its current scrip-master token and data permissions.")
                continue
            save_csv(args.output, symbol, rows)
            sessions = sorted({str(row[0])[:10] for row in rows})
            selected = set(sessions[-args.sessions :])
            recent_count = sum(str(row[0])[:10] in selected for row in rows)
            total_rows += len(rows)
            print(f"{symbol}: fetched {len(rows)} candles across {len(sessions)} dates; last {len(selected)} dates contain {recent_count} candles.")
        print(f"Saved candle data to {args.output.resolve()} ({total_rows} rows total).")
        print("Historical candles only: this script does not place or change orders.")
    finally:
        try:
            client.logout()
        except Exception:
            logger.debug("Logout failed or no active session", exc_info=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    main()
