"""Explicitly gated, fixed-quantity MIS execution example.

This is a guarded execution scaffold, NOT a turnkey production trading system.
It only trades a configured cash-market scrip, enters long on BUY, and exits on
SELL. It has no broker-side stop-loss or portfolio reconciliation.
"""

from __future__ import annotations

import asyncio
import getpass
import logging
import os
from datetime import date, datetime, timezone

from neo_api_client import NeoAPI
from neo_api_client.websocket.feed import SFeedScrip, WsToken

from .config import Settings
from .strategy import EmaCrossover

logger = logging.getLogger("strat-01.execution")
CONFIRMATION = "I_ACCEPT_LIVE_ORDER_RISK"


def place_order(client, symbol: str, side: str, quantity: int, tag: str):
    return client.place_order(
        exchange_segment="nse_cm",
        product="MIS",
        price="0",
        order_type="MKT",
        quantity=str(quantity),
        validity="DAY",
        trading_symbol=symbol,
        transaction_type="B" if side == "BUY" else "S",
        amo="NO",
        disclosed_quantity="0",
        trigger_price="0",
        tag=tag[:20],
    )


async def run() -> None:
    settings = Settings.from_env()
    symbol = os.getenv("NEO_TRADE_SYMBOL", "").strip()
    token = os.getenv("NEO_TRADE_TOKEN", "").strip()
    if not symbol or not token:
        raise ValueError("Set NEO_TRADE_SYMBOL and NEO_TRADE_TOKEN to an exact verified NSE_EQ trading symbol and token.")
    quantity = int(os.getenv("NEO_ORDER_QUANTITY", "0"))
    max_entries = int(os.getenv("NEO_MAX_ENTRIES_PER_DAY", "1"))
    if quantity <= 0 or max_entries < 1:
        raise ValueError("NEO_ORDER_QUANTITY must be positive and NEO_MAX_ENTRIES_PER_DAY >= 1")
    live_enabled = os.getenv("ENABLE_LIVE_TRADING", "NO").strip().upper() == "YES"
    confirmation = os.getenv("LIVE_TRADING_CONFIRM", "").strip()
    if live_enabled and confirmation != CONFIRMATION:
        raise ValueError(f"Live execution requires LIVE_TRADING_CONFIRM={CONFIRMATION}")
    if not live_enabled:
        logger.warning("DRY RUN ONLY: no broker orders will be sent. Set explicit live gates to enable order placement.")

    fast, slow = int(os.getenv("EMA_FAST_PERIOD", "9")), int(os.getenv("EMA_SLOW_PERIOD", "11"))
    engine = EmaCrossover(symbol, fast, slow)
    client = NeoAPI(consumer_key=settings.consumer_key, environment=settings.environment)
    client.totp_login(mobile_number=settings.mobile_number, ucc=settings.ucc, totp=getpass.getpass("Current Kotak Neo TOTP: ").strip())
    client.totp_validate(mpin=settings.mpin)
    position_open = False
    entry_count = 0
    session_day = date.today()
    halted = False
    try:
        async with client.create_websocket() as ws:
            await ws.subscribe_scrips([WsToken("nse_cm", token)])
            logger.info("Monitoring %s; entries/day cap=%d, quantity=%d", symbol, max_entries, quantity)
            async for message in ws:
                if halted or not isinstance(message, SFeedScrip) or message.last_traded_price is None:
                    continue
                if date.today() != session_day:
                    session_day, entry_count, position_open = date.today(), 0, False
                signal = engine.update(message.last_traded_price, datetime.now(timezone.utc).isoformat())
                if signal is None:
                    continue
                if signal.side == "BUY" and not position_open and entry_count < max_entries:
                    side = "BUY"
                elif signal.side == "SELL" and position_open:
                    side = "SELL"
                else:
                    continue
                logger.warning("QUALIFIED %s %s @ %.4f", side, symbol, signal.price)
                if not live_enabled:
                    logger.info("Dry-run: skipped order submission")
                    # Dry run deliberately does not pretend a position was opened.
                    continue
                try:
                    response = place_order(client, symbol, side, quantity, f"ema911-{session_day:%Y%m%d}-{side.lower()}")
                    if not isinstance(response, dict) or response.get("stat") != "Ok":
                        raise RuntimeError(f"Broker did not confirm order acceptance: {response!r}")
                except Exception:
                    halted = True
                    logger.exception("Order outcome may be uncertain; execution halted. Check broker order book before restarting.")
                    continue
                if side == "BUY":
                    position_open = True
                    entry_count += 1
                else:
                    position_open = False
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
        logger.warning("Stopped. Verify any open MIS position and broker orders manually before exiting.")


if __name__ == "__main__":
    main()
