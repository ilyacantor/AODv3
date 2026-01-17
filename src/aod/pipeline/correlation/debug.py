"""Debug logging utilities for correlation matching."""

import logging
import os

from .constants import AUTHORITATIVE_MATCH_METHODS

logger = logging.getLogger(__name__)

_DEBUG_MATCH = os.environ.get("AOD_DEBUG_MATCH", "0") == "1"


def log_match_debug(plane_name: str, match_method: str, entity_name: str, matched_id: str) -> None:
    """Log match debug info when AOD_DEBUG_MATCH=1"""
    if _DEBUG_MATCH:
        log_type = "AUTH_MATCH" if match_method in AUTHORITATIVE_MATCH_METHODS else "HEURISTIC_MATCH"
        logger.info(f"{log_type} plane={plane_name} method={match_method} entity={entity_name} matched={matched_id}")


# Alias with underscore prefix for backwards compatibility
_log_match_debug = log_match_debug
