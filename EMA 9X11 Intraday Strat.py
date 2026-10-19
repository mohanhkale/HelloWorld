import os
import sys
import time
import json
import logging
from neo_api_client import NeoAPI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("KotakNeoWebSocket")

# 1. Credentials Configuration
CONFIG = {
    "CONSUMER_KEY": os.getenv("KOTAK_CONSUMER_KEY", "f8c04662-3dea-4086-bedb-4d29d5070065"),
    "CONSUMER_SECRET": os.getenv("KOTAK_CONSUMER_SECRET", "XZE3Q"),
    "MOBILE_NUMBER": os.getenv("KOTAK_MOBILE", "+919356837843"),
    "MPIN": os.getenv("KOTAK_MPIN", "540906"),
    "ENVIRONMENT": "prod"
}

# 2. Map of Sectoral Indices to their Segment and Token
SECTORAL_INDICES = [
    {"instrument_token": "26001", "exchange_segment": "nse_cm", "name": "NIFTY BANK"},
    {"instrument_token": "26002", "exchange_segment": "nse_cm", "name": "NIFTY IT"},
    {"instrument_token": "26004", "exchange_segment": "nse_cm", "name": "NIFTY AUTO"},
    {"instrument_token": "26005", "exchange_segment": "nse_cm", "name": "NIFTY PHARMA"},
    {"instrument_token": "26006", "exchange_segment": "nse_cm", "name": "NIFTY METAL"},
    {"instrument_token": "26037", "exchange_segment": "nse_cm", "name": "NIFTY FIN SERVICE"}
]

# Quick reverse-lookup dictionary by token
TOKEN_MAP = {item["instrument_token"]: item["name"] for item in SECTORAL_INDICES}


class SectorTickStreamer:
    def __init__(self, config):
        self.config = config
        self.client = None
        self.latest_prices = {}

    def on_message(self, message):
        """Callback triggered whenever a tick packet arrives."""
        try:
            # message can be a list or dict depending on the batch
            if isinstance(message, str):
                ticks = json.loads(message)
            else:
                ticks = message

            if isinstance(ticks, dict):
                ticks = [ticks]

            for tick in ticks:
                token = str(tick.get("tk") or tick.get("instrument_token", ""))
                index_name = TOKEN_MAP.get(token, f"Token {token}")

                # 'ltp' or 'iv' (Index Value) represents the current level
                ltp = tick.get("ltp") or tick.get("iv") or tick.get("last_traded_price")
                change = tick.get("cng") or tick.get("net_change", 0.0)
                pct_change = tick.get("nc") or tick.get("percent_change", 0.0)

                if ltp is not None:
                    self.latest_prices[index_name] = float(ltp)
                    logger.info(f"[TICK] {index_name:<18} | Value: {float(ltp):,.2f} | Chg: {change} ({pct_change}%)")

        except Exception as e:
            logger.error(f"Error parsing tick packet: {e} | Raw: {message}")

    def on_error(self, error):
        logger.error(f"WebSocket Error: {error}")

    def on_close(self, message):
        logger.warning(f"WebSocket Connection Closed: {message}")

    def on_open(self, message):
        logger.info(f"WebSocket Connected: {message}")

    def start(self):
        # Initialize client with callbacks
        self.client = NeoAPI(
            consumer_key=self.config["CONSUMER_KEY"],
            consumer_secret=self.config["CONSUMER_SECRET"],
            environment=self.config["ENVIRONMENT"],
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open
        )

        logger.info("Authenticating with Kotak Neo...")
        self.client.login(
            mobilenumber=self.config["MOBILE_NUMBER"],
            password=self.config["MPIN"]
        )
        self.client.session_2fa(mpin=self.config["MPIN"])
        logger.info("Authentication successful.")

        # Prepare instrument list for subscription
        instruments_to_subscribe = [
            {
                "instrument_token": item["instrument_token"],
                "exchange_segment": item["exchange_segment"]
            }
            for item in SECTORAL_INDICES
        ]

        logger.info("Subscribing to real-time sectoral index feeds...")
        # isIndex=True or standard quote subscription
        self.client.subscribe(
            instrument_tokens=instruments_to_subscribe,
            isIndex=True,
            isDepth=False
        )

        # Keep the thread running to receive stream updates
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Unsubscribing and shutting down stream...")
            self.client.un_subscribe(
                instrument_tokens=instruments_to_subscribe,
                isIndex=True
            )


if __name__ == "__main__":
    streamer = SectorTickStreamer(CONFIG)
    streamer.start()
