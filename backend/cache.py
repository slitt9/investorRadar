"""Simple in-memory TTL cache to replace Streamlit's @st.cache_data."""

import time
from threading import Lock

_cache = {}
_lock = Lock()


def _freeze(value):
    """Convert common unhashable types into a stable, hashable representation."""
    if isinstance(value, dict):
        return tuple(sorted((k, _freeze(v)) for k, v in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v) for v in value)
    if isinstance(value, set):
        return tuple(sorted(_freeze(v) for v in value))
    try:
        hash(value)
        return value
    except Exception:
        return repr(value)


def cached(ttl=300):
    """Decorator that caches function results with a TTL in seconds."""
    def decorator(fn):
        def wrapper(*args, **kwargs):
            key = (
                fn.__name__,
                _freeze(args),
                tuple(sorted((k, _freeze(v)) for k, v in kwargs.items())),
            )
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
