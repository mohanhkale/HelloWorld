"""Configuration loaded from environment variables; never commit live credentials."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    consumer_key: str
    mobile_number: str
    ucc: str
    mpin: str
    environment: str
    index_names: tuple[str, ...]
    fast_period: int
    slow_period: int

    @classmethod
    def from_env(cls) -> "Settings":
        names = tuple(
            name.strip()
            for name in os.getenv("NEO_INDEX_NAMES", "Nifty Bank,Nifty IT,Nifty Auto").split(",")
            if name.strip()
        )
        fast = int(os.getenv("EMA_FAST_PERIOD", "9"))
        slow = int(os.getenv("EMA_SLOW_PERIOD", "11"))
        if fast < 1 or slow < 2 or fast >= slow:
            raise ValueError("EMA periods must satisfy 1 <= fast < slow.")
        if not names:
            raise ValueError("Set NEO_INDEX_NAMES to at least one supported index name.")

        required = {
            "NEO_CONSUMER_KEY": os.getenv("NEO_CONSUMER_KEY", "").strip(),
            "NEO_MOBILE_NUMBER": os.getenv("NEO_MOBILE_NUMBER", "").strip(),
            "NEO_UCC": os.getenv("NEO_UCC", "").strip(),
            "NEO_MPIN": os.getenv("NEO_MPIN", "").strip(),
        }
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise ValueError("Missing required environment variables: " + ", ".join(missing))

        return cls(
            consumer_key=required["NEO_CONSUMER_KEY"],
            mobile_number=required["NEO_MOBILE_NUMBER"],
            ucc=required["NEO_UCC"],
            mpin=required["NEO_MPIN"],
            environment=os.getenv("NEO_ENVIRONMENT", "prod").strip() or "prod",
            index_names=names,
            fast_period=fast,
            slow_period=slow,
        )
