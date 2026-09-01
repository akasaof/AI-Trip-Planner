
import hashlib
import random
import time

_cache: dict[str, tuple[float, object]] = {}


def seeded_random(*parts: str) -> random.Random:
    key = "|".join(str(p) for p in parts)
    seed = int(hashlib.sha256(key.encode()).hexdigest(), 16) % (2**32)
    return random.Random(seed)


def cache_get(key: str):
    entry = _cache.get(key)
    if not entry:
        return None
    expires_at, value = entry
    if time.time() > expires_at:
        _cache.pop(key, None)
        return None
    return value


def cache_set(key: str, value, ttl_seconds: int) -> None:
    _cache[key] = (time.time() + ttl_seconds, value)


class ProviderUnavailable(Exception):
    """Raised (or just returned as an empty result) when a tool's
    required API key is missing or the provider errors out. Tools catch
    their own provider-specific exceptions and degrade to an empty list
    rather than let this propagate — the orchestrator treats "no data"
    as a normal, expected outcome, not a crash."""
