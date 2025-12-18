"""LLM configuration - dev/prod mode switch"""

import os
from enum import Enum


class LLMMode(str, Enum):
    """LLM execution mode"""
    DEV = "dev"
    PROD = "prod"


def get_llm_mode() -> LLMMode:
    """
    Get the current LLM execution mode.
    
    Set via LLM_MODE environment variable:
    - "dev" or "development": No LLM calls, use cached facts only
    - "prod" or "production": Full LLM calls enabled
    
    Defaults to DEV if not set.
    """
    mode_str = os.environ.get("LLM_MODE", "dev").lower().strip()
    
    if mode_str in ("prod", "production"):
        return LLMMode.PROD
    
    return LLMMode.DEV


def is_llm_enabled() -> bool:
    """Check if LLM calls are enabled based on current mode"""
    return get_llm_mode() == LLMMode.PROD
