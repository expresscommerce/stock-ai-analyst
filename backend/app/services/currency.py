"""Currency conversion using ExchangeRate-API with Redis caching."""

import json
import logging
import requests  # type: ignore

from flask import current_app
from app.extensions import redis_client

logger = logging.getLogger(__name__)

CACHE_KEY = "exchange_rates:USD"
CACHE_TTL = 3600  # 1 hour


def get_exchange_rates(base: str = "USD") -> dict:
    """Get live exchange rates with Redis caching.

    Args:
        base: Base currency (default USD)

    Returns:
        Dict of currency codes to rates.
    """
    cache_key = f"exchange_rates:{base}"

    # Try Redis cache first
    if redis_client:
        try:
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Redis cache read error: {e}")

    # Fetch from API
    api_key = current_app.config.get("EXCHANGE_RATE_API_KEY")
    if not api_key:
        logger.warning("EXCHANGE_RATE_API_KEY not configured")
        return _fallback_rates()

    try:
        resp = requests.get(
            f"https://v6.exchangerate-api.com/v6/{api_key}/latest/{base}",
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("result") != "success":
            logger.error(f"ExchangeRate-API error: {data}")
            return _fallback_rates()

        rates = data.get("conversion_rates", {})

        # Filter to supported currencies
        supported = current_app.config.get("SUPPORTED_CURRENCIES", [])
        filtered = {k: v for k, v in rates.items() if k in supported} if supported else rates

        # Cache in Redis
        if redis_client:
            try:
                redis_client.setex(cache_key, CACHE_TTL, json.dumps(filtered))
            except Exception as e:
                logger.warning(f"Redis cache write error: {e}")

        return filtered

    except Exception as e:
        logger.error(f"Error fetching exchange rates: {e}")
        return _fallback_rates()


def convert_currency(amount: float, from_currency: str, to_currency: str) -> float | None:
    """Convert an amount between currencies.

    Args:
        amount: Amount to convert
        from_currency: Source currency code
        to_currency: Target currency code

    Returns:
        Converted amount or None if conversion failed.
    """
    if from_currency == to_currency:
        return amount

    rates = get_exchange_rates(from_currency)
    rate = rates.get(to_currency)

    if rate is None:
        # Try via USD as intermediate
        usd_rates = get_exchange_rates("USD")
        from_rate = usd_rates.get(from_currency, 1)
        to_rate = usd_rates.get(to_currency)
        if to_rate and from_rate:
            return round(amount / from_rate * to_rate, 4)
        return None

    return round(amount * rate, 4)


def _fallback_rates() -> dict:
    """Fallback approximate rates if API is unavailable."""
    return {
        "USD": 1.0,
        "EUR": 0.92,
        "GBP": 0.79,
        "JPY": 149.50,
        "PKR": 278.50,
        "AED": 3.67,
        "SAR": 3.75,
        "CAD": 1.36,
        "AUD": 1.53,
    }
