"""
Config resolver for v2 API — merges per-request config with server defaults.
"""

from typing import Any, Dict, Optional

from powermem import auto_config

from ..models.request_v2 import PowermemConfig


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge *override* into *base* (returns a new dict)."""
    merged = dict(base)
    for key, value in override.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def resolve_config(powermem_config: Optional[PowermemConfig] = None) -> Dict[str, Any]:
    """Build a full config dict from per-request overrides.

    If *powermem_config* is ``None`` the server-side defaults (env / .env)
    are returned as-is.  Otherwise the request values are deep-merged on top
    of the defaults so callers only need to send the fields they want to
    override.
    """
    base = auto_config()
    if powermem_config is None:
        return base
    override = powermem_config.model_dump(exclude_none=True)
    return _deep_merge(base, override)
