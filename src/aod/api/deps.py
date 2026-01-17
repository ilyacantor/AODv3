"""Shared dependencies for API routes"""

import os
from datetime import datetime, timezone, timedelta

from ..db.database import get_db
from ..farm_client import FarmClient

PST = timezone(timedelta(hours=-8))


def now_pst() -> datetime:
    """Get current time in PST"""
    return datetime.now(PST)


def get_farm_url() -> str | None:
    """Get Farm URL from environment.
    
    Uses FARM_URL_PROD as the canonical source.
    Falls back to FARM_URL for backward compatibility.
    """
    return os.environ.get("FARM_URL_PROD") or os.environ.get("FARM_URL")


def get_farm_client() -> FarmClient | None:
    """Get Farm client if URL is configured"""
    farm_url = get_farm_url()
    if farm_url:
        return FarmClient(farm_url)
    return None
