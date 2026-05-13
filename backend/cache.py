"""Simple in-memory TTL cache to replace Streamlit's @st.cache_data.

Supports an optional ``maxsize`` parameter that bounds memory by evicting the
least-recently-used entry. This is important for large response payloads like
SEC company facts JSON, which can be 10-30 MB per ticker and quickly blow past
small dyno memory budgets when refreshing the full S&P 500.
"""

import time
from collections import OrderedDict
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


def cached(ttl=300, maxsize=None):
    """Decorator that caches function results with a TTL in seconds.

    When ``maxsize`` is set, results are stored in a per-decorator OrderedDict
    and evicted in least-recently-used order once the bound is exceeded.
    """

    def decorator(fn):
        local_cache: OrderedDict | None = OrderedDict() if maxsize is not None else None

        def wrapper(*args, **kwargs):
            key = (
                fn.__name__,
                _freeze(args),
                tuple(sorted((k, _freeze(v)) for k, v in kwargs.items())),
            )
            store = local_cache if local_cache is not None else _cache
            with _lock:
                if key in store:
                    value, expiry = store[key]
                    if time.time() < expiry:
                        if local_cache is not None:
                            store.move_to_end(key)
                        return value
                    store.pop(key, None)
            result = fn(*args, **kwargs)
            with _lock:
                store[key] = (result, time.time() + ttl)
                if local_cache is not None and len(store) > maxsize:
                    store.popitem(last=False)
            return result

        wrapper.__name__ = fn.__name__

        def _clear():
            with _lock:
                if local_cache is not None:
                    local_cache.clear()
                else:
                    for k in [
                        k for k in list(_cache.keys()) if k and k[0] == fn.__name__
                    ]:
                        _cache.pop(k, None)

        wrapper.cache_clear = _clear
        return wrapper

    return decorator


def clear_cache():
    """Clears the shared cache (per-decorator LRU caches are untouched)."""
    with _lock:
        _cache.clear()
