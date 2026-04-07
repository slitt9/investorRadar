"""Simple in-memory TTL cache to replace Streamlit's @st.cache_data."""

import time
from threading import Lock

_cache = {}
_lock = Lock()


def cached(ttl=300):
    """Decorator that caches function results with a TTL in seconds."""
    def decorator(fn):
        def wrapper(*args, **kwargs):
            key = (fn.__name__, args, tuple(sorted(kwargs.items())))
            with _lock:
                if key in _cache:
                    value, expiry = _cache[key]
                    if time.time() < expiry:
                        return value
            result = fn(*args, **kwargs)
            with _lock:
                _cache[key] = (result, time.time() + ttl)
            return result
        wrapper.__name__ = fn.__name__
        return wrapper
    return decorator


def clear_cache():
    """Clears all cached data."""
    with _lock:
        _cache.clear()
