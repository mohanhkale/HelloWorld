"""Kotak Neo SDK authentication and async SFeed index consumer."""

from __future__ import annotations

import asyncio
import getpass
import logging

from neo_api_client import NeoAPI
from neo_api_client.websocket.feed import SFeedIndex, WsToken

from .config import Settings
from .strategy import EmaCrossover

logger = logging.getLogger("strat-01")


async def run() -> None:
    settings = Settings.from_env()
    totp = getpass.getpass("Current Kotak Neo TOTP: ").strip()
    if not totp:
        raise ValueError("A current TOTP code is required to authenticate.")

    client = NeoAPI(
        consumer_key=settings.consumer_key,
        environment=settings.environment,
    )
    client.totp_login(
        mobile_number=settings.mobile_number,
        ucc=settings.ucc,
        totp=totp,
    )
    client.totp_validate(mpin=settings.mpin)
    logger.info("Kotak Neo authentication succeeded; starting signal-only feed.")

    strategies = {
        name.casefold(): EmaCrossover(name, settings.fast_period, settings.slow_period)
        for name in settings.index_names
    }
    tokens = [WsToken("nse_cm", name) for name in settings.index_names]

    try:
        async with client.create_websocket() as ws:
            await ws.subscribe_index(tokens)
            logger.info("Subscribed to index feed: %s", ", ".join(settings.index_names))
            async for message in ws:
                if not isinstance(message, SFeedIndex):
                    continue
                instrument = (message.name or message.trading_symbol or "").casefold()
                strategy = strategies.get(instrument)
                if strategy is None:
                    logger.debug("Ignoring unconfigured index message: %s", message)
                    continue
                price = message.last_traded_price
                if price is None:
                    continue
                signal = strategy.update(price)
                if signal:
                    logger.warning(
                        "SIGNAL ONLY %s %s price=%.2f EMA%d=%.2f EMA%d=%.2f samples=%d",
                        signal.instrument,
                        signal.direction,
                        signal.price,
                        settings.fast_period,
                        signal.fast_ema,
                        settings.slow_period,
                        signal.slow_ema,
                        signal.samples,
                    )
    finally:
        try:
            client.logout()
        except Exception:
            logger.exception("Kotak Neo logout failed")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Stopped by user.")


if __name__ == "__main__":
    main()
