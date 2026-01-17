"""Shared dependencies for API routes"""

import os
from datetime import datetime, timezone, timedelta

from ..db.database import get_db
from ..farm_client import FarmClient
from ..farm_url_resolver import get_farm_config

PST = timezone(timedelta(hours=-8))


def now_pst() -> datetime:
    """Get current time in PST"""
    return datetime.now(PST)


def get_farm_url() -> str | None:
    """Get Farm URL from environment (legacy - prefer get_farm_config)"""
    config = get_farm_config()
    if config.mode == "prod":
        return config.prod_url
    elif config.mode == "dev" and config.dev_url:
        return config.dev_url
    else:
        return config.dev_url or config.prod_url


def get_farm_client() -> FarmClient | None:
    """Get Farm client if URL is configured"""
    farm_url = get_farm_url()
    if farm_url:
        return FarmClient(farm_url)
    return None
