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
    
    FARM_URL_MODE controls which URL to use:
    - "prod": Use FARM_URL_PROD only
    - "dev": Use FARM_URL_DEV only  
    - "auto" (default): Auto-detect based on REPLIT_DEPLOYMENT (prod if deployed, dev otherwise)
    
    Falls back to FARM_URL for backward compatibility.
    """
    mode = os.environ.get("FARM_URL_MODE", "auto").lower()
    
    if mode == "prod":
        return os.environ.get("FARM_URL_PROD") or os.environ.get("AOS_FARM_URL")
    elif mode == "dev":
        return os.environ.get("FARM_URL_DEV") or os.environ.get("AOS_FARM_URL")
    else:
        # Auto mode - detect if running in production deployment
        is_production = os.environ.get("REPLIT_DEPLOYMENT") == "1"
        if is_production:
            return os.environ.get("FARM_URL_PROD") or os.environ.get("FARM_URL_DEV") or os.environ.get("AOS_FARM_URL")
        else:
            return os.environ.get("FARM_URL_DEV") or os.environ.get("FARM_URL_PROD") or os.environ.get("AOS_FARM_URL")


def get_farm_client() -> FarmClient | None:
    """Get Farm client if URL is configured"""
    farm_url = get_farm_url()
    if farm_url:
        return FarmClient(farm_url)
    return None
