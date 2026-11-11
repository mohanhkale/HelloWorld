"""Validated environment configuration shared by the strategy utilities."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    consumer_key: str
    mobile_number: str
    ucc: str
    mpin: str
    environment: str = "prod"

    @classmethod
    def from_env(cls) -> "Settings":
        required = {
            "NEO_CONSUMER_KEY": os.getenv("NEO_CONSUMER_KEY", "").strip(),
            "NEO_MOBILE_NUMBER": os.getenv("NEO_MOBILE_NUMBER", "").strip(),
            "NEO_UCC": os.getenv("NEO_UCC", "").strip(),
            "NEO_MPIN": os.getenv("NEO_MPIN", "").strip(),
        }
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise ValueError("Missing required environment variables: " + ", ".join(missing))
        return cls(**{
            "consumer_key": required["NEO_CONSUMER_KEY"],
            "mobile_number": required["NEO_MOBILE_NUMBER"],
            "ucc": required["NEO_UCC"],
            "mpin": required["NEO_MPIN"],
            "environment": os.getenv("NEO_ENVIRONMENT", "prod").strip() or "prod",
        })
