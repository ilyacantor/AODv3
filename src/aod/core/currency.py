"""
Currency Normalization Service - Multi-Currency Support.

ARCHITECTURAL PRINCIPLE:
Financial thresholds are meaningless without currency context.
$1,000 USD ≠ €1,000 EUR ≠ ¥1,000 JPY

This module provides:
- normalize_to_usd(): Convert any amount to USD base unit
- CurrencyConverter: Service for real-time FX rates (stub for now)

All financial comparisons in the pipeline should normalize to USD FIRST,
then compare against policy thresholds.
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional

logger = logging.getLogger(__name__)


# Static fallback rates (updated periodically)
# In production, these would come from an FX API
_FALLBACK_RATES_TO_USD: Dict[str, float] = {
    "USD": 1.0,
    "EUR": 1.08,      # 1 EUR = 1.08 USD
    "GBP": 1.27,      # 1 GBP = 1.27 USD
    "JPY": 0.0067,    # 1 JPY = 0.0067 USD
    "CAD": 0.74,      # 1 CAD = 0.74 USD
    "AUD": 0.65,      # 1 AUD = 0.65 USD
    "CHF": 1.13,      # 1 CHF = 1.13 USD
    "CNY": 0.14,      # 1 CNY = 0.14 USD
    "INR": 0.012,     # 1 INR = 0.012 USD
    "MXN": 0.058,     # 1 MXN = 0.058 USD
    "BRL": 0.20,      # 1 BRL = 0.20 USD
    "KRW": 0.00075,   # 1 KRW = 0.00075 USD
    "SGD": 0.74,      # 1 SGD = 0.74 USD
    "HKD": 0.13,      # 1 HKD = 0.13 USD
    "SEK": 0.095,     # 1 SEK = 0.095 USD
    "NOK": 0.093,     # 1 NOK = 0.093 USD
    "DKK": 0.145,     # 1 DKK = 0.145 USD
    "NZD": 0.60,      # 1 NZD = 0.60 USD
    "ZAR": 0.055,     # 1 ZAR = 0.055 USD
    "ILS": 0.27,      # 1 ILS = 0.27 USD
}


@dataclass
class ConversionResult:
    """Result of a currency conversion."""
    original_amount: float
    original_currency: str
    converted_amount: float
    target_currency: str
    rate_used: float
    rate_source: str  # "live", "cached", "fallback"
    converted_at: datetime


class CurrencyConverter:
    """
    Currency conversion service.

    In production, this would:
    1. Try to fetch live rates from an FX API
    2. Fall back to cached rates (Redis)
    3. Fall back to static rates as last resort

    For now, uses static fallback rates.
    """

    def __init__(self):
        self._rates = _FALLBACK_RATES_TO_USD.copy()
        self._rates_updated_at = datetime.utcnow()
        self._rate_source = "fallback"

    def get_rate_to_usd(self, currency: str) -> float:
        """Get conversion rate from currency to USD."""
        currency_upper = currency.upper()
        if currency_upper in self._rates:
            return self._rates[currency_upper]

        # Unknown currency - log warning and assume 1:1
        logger.warning("currency.unknown_rate",
                      extra={"currency": currency, "assuming": 1.0})
        return 1.0

    def convert_to_usd(self, amount: float, currency: str) -> ConversionResult:
        """Convert amount to USD."""
        rate = self.get_rate_to_usd(currency)
        converted = amount * rate

        return ConversionResult(
            original_amount=amount,
            original_currency=currency.upper(),
            converted_amount=round(converted, 2),
            target_currency="USD",
            rate_used=rate,
            rate_source=self._rate_source,
            converted_at=datetime.utcnow(),
        )

    def convert(
        self,
        amount: float,
        from_currency: str,
        to_currency: str = "USD"
    ) -> ConversionResult:
        """Convert amount between currencies."""
        if to_currency.upper() != "USD":
            # Convert to USD first, then to target
            usd_amount = amount * self.get_rate_to_usd(from_currency)
            target_rate = self.get_rate_to_usd(to_currency)
            if target_rate == 0:
                target_rate = 1.0
            final_amount = usd_amount / target_rate
            combined_rate = self.get_rate_to_usd(from_currency) / target_rate
        else:
            final_amount = amount * self.get_rate_to_usd(from_currency)
            combined_rate = self.get_rate_to_usd(from_currency)

        return ConversionResult(
            original_amount=amount,
            original_currency=from_currency.upper(),
            converted_amount=round(final_amount, 2),
            target_currency=to_currency.upper(),
            rate_used=combined_rate,
            rate_source=self._rate_source,
            converted_at=datetime.utcnow(),
        )


# Global converter instance
_converter: Optional[CurrencyConverter] = None


def get_converter() -> CurrencyConverter:
    """Get the global currency converter."""
    global _converter
    if _converter is None:
        _converter = CurrencyConverter()
    return _converter


def normalize_to_usd(amount: float, currency: str) -> float:
    """
    Normalize an amount to USD.

    This is the main entry point for currency normalization.
    Use this before comparing against any financial thresholds.

    Example:
        monthly_spend_usd = normalize_to_usd(monthly_spend, record_currency)
        if monthly_spend_usd >= policy.get_finance_gap_threshold("HIGH"):
            ...
    """
    if currency.upper() == "USD":
        return amount

    converter = get_converter()
    result = converter.convert_to_usd(amount, currency)
    return result.converted_amount


def get_supported_currencies() -> list[str]:
    """Get list of supported currency codes."""
    return list(_FALLBACK_RATES_TO_USD.keys())
