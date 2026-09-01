
import httpx
from langchain_core.tools import tool

from app.config import get_settings
from app.tools.common import cache_get, cache_set

ER_API_BASE = "https://open.er-api.com/v6/latest"


@tool
async def currency_convert(amount: float, from_currency: str, to_currency: str) -> dict:
    """Convert an amount from one currency to another using live
    exchange rates (open.er-api.com — free, no API key required).
    Returns the converted amount, or an error dict if the live lookup
    fails (never a fabricated rate)."""
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()
    settings = get_settings()

    cache_key = f"fx:{from_currency}"
    rates = cache_get(cache_key)
    if rates is None:
        try:
            async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
                resp = await client.get(f"{ER_API_BASE}/{from_currency}")
                resp.raise_for_status()
                data = resp.json()
            rates = data.get("rates", {})
            cache_set(cache_key, rates, ttl_seconds=60 * 60)
        except httpx.HTTPError:
            return {"error": f"Could not fetch live exchange rates for {from_currency}", "source": "live"}

    if to_currency not in rates:
        return {"error": f"Unsupported currency {to_currency}", "source": "live"}

    converted = amount * rates[to_currency]
    return {
        "amount": amount,
        "from_currency": from_currency,
        "to_currency": to_currency,
        "converted_amount": round(converted, 2),
        "source": "live",
    }
