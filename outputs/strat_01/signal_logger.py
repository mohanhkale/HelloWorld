"""Append qualified live EMA BUY/SELL crossover signals to a CSV file."""

from __future__ import annotations

import asyncio
import csv
import getpass
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from neo_api_client import NeoAPI
from neo_api_client.websocket.feed import SFeedScrip, WsToken

from .config import Settings
from .strategy import EmaCrossover

logger = logging.getLogger("strat-01.signal-logger")


class CsvSignalLog:
    FIELDS = ("timestamp", "instrument", "side", "price", "fast_ema", "slow_ema", "samples")

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._needs_header = not path.exists() or path.stat().st_size == 0

    def append(self, signal) -> None:
        with self.path.open("a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=self.FIELDS)
            if self._needs_header:
                writer.writeheader()
                self._needs_header = False
            writer.writerow({
                "timestamp": signal.timestamp,
                "instrument": signal.instrument,
                "side": signal.side,
                "price": f"{signal.price:.4f}",
                "fast_ema": f"{signal.fast_ema:.6f}",
                "slow_ema": f"{signal.slow_ema:.6f}",
                "samples": signal.samples,
            })


async def run() -> None:
    settings = Settings.from_env()
    symbol = os.getenv("NEO_TRADE_SYMBOL", "").strip()
    token = os.getenv("NEO_TRADE_TOKEN", "").strip()
    if not symbol or not token:
        raise ValueError("Set NEO_TRADE_SYMBOL and NEO_TRADE_TOKEN to a verified tradable NSE scrip.")
    fast, slow = int(os.getenv("EMA_FAST_PERIOD", "9")), int(os.getenv("EMA_SLOW_PERIOD", "11"))
    engine = EmaCrossover(symbol, fast, slow)
    log = CsvSignalLog(Path(os.getenv("SIGNALS_CSV", "outputs/strat-01/signals.csv")))
    client = NeoAPI(consumer_key=settings.consumer_key, environment=settings.environment)
    client.totp_login(mobile_number=settings.mobile_number, ucc=settings.ucc, totp=getpass.getpass("Current Kotak Neo TOTP: ").strip())
    client.totp_validate(mpin=settings.mpin)
    ws_token = WsToken("nse_cm", token)
    try:
        async with client.create_websocket() as ws:
            await ws.subscribe_scrips([ws_token])
            logger.info("Signal logger subscribed to %s; appending qualified crosses to %s", symbol, log.path)
            async for message in ws:
                if not isinstance(message, SFeedScrip) or message.last_traded_price is None:
                    continue
                timestamp = datetime.now(timezone.utc).isoformat()
                signal = engine.update(message.last_traded_price, timestamp)
                if signal:
                    log.append(signal)
                    logger.warning("LOGGED %s %s %.4f", signal.instrument, signal.side, signal.price)
    finally:
        try:
            client.logout()
        except Exception:
            logger.exception("Kotak Neo logout failed")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Signal logger stopped")


if __name__ == "__main__":
    main()
