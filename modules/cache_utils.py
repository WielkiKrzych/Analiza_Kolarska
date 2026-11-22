"""
Caching layer for expensive computations.

Provides memoization for CPU-intensive operations with TTL support.
Uses diskcache as a simple alternative to Redis (no external dependencies).
"""

import dataclasses
import hashlib
import pickle
from functools import wraps
from typing import Any, Callable, Optional, TypeVar
from pathlib import Path
import pandas as pd
import numpy as np

# Try to use diskcache (file-based, no external dependencies)
try:
    from diskcache import Cache

    _CACHE_AVAILABLE = True
except ImportError:
    _CACHE_AVAILABLE = False
    Cache = None

from modules.config import Config

T = TypeVar("T")

# Global cache instance
_cache: Optional[Cache] = None


def get_cache() -> Optional[Cache]:
    """Get or create global cache instance."""
    global _cache
    if not _CACHE_AVAILABLE:
        return None

    if _cache is None:
        cache_dir = (
            Path(Config.DB_PATH).parent / "cache" if hasattr(Config, "DB_PATH") else Path("./cache")
        )
        cache_dir.mkdir(exist_ok=True)
        _cache = Cache(str(cache_dir))

    return _cache


def cache_result(ttl: int = 3600, key_func: Optional[Callable] = None):
    """
    Decorator to cache function results.

    Args:
        ttl: Time-to-live in seconds (default: 1 hour)
        key_func: Optional function to generate cache key from arguments

    Usage:
        @cache_result(ttl=3600)
        def expensive_calculation(df: pd.DataFrame, param: int) -> dict:
            return heavy_computation(df, param)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            cache = get_cache()
            if cache is None:
                return func(*args, **kwargs)

            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = _generate_cache_key(func.__name__, args, kwargs)

            # Try to get from cache
            try:
                result = cache.get(cache_key)
                if result is not None:
                    return result
            except Exception:
                pass

            # Compute and cache
            result = func(*args, **kwargs)
            try:
                cache.set(cache_key, result, expire=ttl)
            except Exception:
                pass

            return result

        # Add cache invalidation method
        wrapper.invalidate_cache = lambda *args, **kwargs: _invalidate_cache(
            func.__name__, args, kwargs, key_func
        )

        return wrapper

    return decorator


def _generate_cache_key(func_name: str, args: tuple, kwargs: dict) -> str:
    """Generate a deterministic cache key from function arguments."""
    # Convert arguments to hashable form
    key_parts = [func_name]

    for arg in args:
        key_parts.append(_hash_arg(arg))

    for k, v in sorted(kwargs.items()):
        key_parts.append(f"{k}={_hash_arg(v)}")

    key_str = "|".join(key_parts)
    return hashlib.md5(key_str.encode()).hexdigest()


def _hash_arg(arg: Any) -> str:
    """Content digest of an argument.

    Keys must cover the data itself: two rides with the same shape (e.g. identical ramp
    protocols) would otherwise share a cache entry and return each other's results.
    """
    if isinstance(arg, (pd.DataFrame, pd.Series)):
        labels = list(arg.columns) if isinstance(arg, pd.DataFrame) else [arg.name]
        try:
            values = pd.util.hash_pandas_object(arg, index=True).to_numpy().tobytes()
        except TypeError:  # unhashable cells (lists, dicts)
            values = pickle.dumps(arg)
        return f"PD:{hashlib.md5(repr(labels).encode() + values).hexdigest()}"
    if isinstance(arg, np.ndarray):
        digest = hashlib.md5(np.ascontiguousarray(arg).tobytes()).hexdigest()
        return f"ARR:{arg.dtype}:{arg.shape}:{digest}"
    if isinstance(arg, (list, tuple)):
        return f"{type(arg).__name__}[{','.join(_hash_arg(a) for a in arg)}]"
    if isinstance(arg, dict):
        items = sorted(arg.items(), key=lambda kv: repr(kv[0]))
        return "DICT{" + ",".join(f"{k!r}:{_hash_arg(v)}" for k, v in items) + "}"
    if dataclasses.is_dataclass(arg) and not isinstance(arg, type):
        fields = {f.name: getattr(arg, f.name) for f in dataclasses.fields(arg)}
        return f"{type(arg).__name__}{_hash_arg(fields)}"
    return repr(arg)


def _invalidate_cache(func_name: str, args: tuple, kwargs: dict, key_func: Optional[Callable]):
    """Invalidate cache entry for specific arguments."""
    cache = get_cache()
    if cache is None:
        return

    if key_func:
        cache_key = key_func(*args, **kwargs)
    else:
        cache_key = _generate_cache_key(func_name, args, kwargs)

    try:
        cache.delete(cache_key)
    except Exception:
        pass


def clear_cache():
    """Clear all cached results."""
    cache = get_cache()
    if cache:
        cache.clear()


def make_cache_key(*args) -> str:
    """Generate an in-memory cache key from arguments. DataFrames are hashed by content."""
    import pandas as pd

    parts = []
    for a in args:
        if isinstance(a, pd.DataFrame):
            parts.append(str(pd.util.hash_pandas_object(a).sum()))
        else:
            parts.append(repr(a))
    return hashlib.md5("|".join(parts).encode()).hexdigest()


def get_cache_stats() -> dict:
    """Get cache statistics."""
    cache = get_cache()
    if cache is None:
        return {"enabled": False}

    try:
        return {"enabled": True, "size": len(cache), "volume": cache.volume()}
    except Exception:
        return {"enabled": True, "error": "Could not get stats"}


@cache_result(ttl=3600)
def cached_generate_summary_pdf(*args, **kwargs) -> bytes:
    """Cached version of PDF generation."""
    from modules.reporting.pdf.summary_pdf import generate_summary_pdf

    return generate_summary_pdf(*args, **kwargs)


def get_session_store() -> "SessionStore":  # noqa: F821
    """Get cached SessionStore singleton.

    Uses st.cache_resource to persist the SQLite connection across Streamlit
    reruns, avoiding re-initialization on every interaction.
    """
    import streamlit as st
    from modules.db import SessionStore

    @st.cache_resource
    def _get_store() -> "SessionStore":
        return SessionStore()

    return _get_store()
