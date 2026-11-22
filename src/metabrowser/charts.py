"""Compatibility imports for the chart extraction now owned by the Agents plugin."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from metabrowser.builtin_plugins.agents import charts

    _CHARTS_CACHE = charts._CHARTS_CACHE
    _cache_key = charts._cache_key
    clear_charts_cache = charts.clear_charts_cache
    extract_agent_charts = charts.extract_agent_charts
    extract_agent_charts_bytes = charts.extract_agent_charts_bytes
    lookup_agent_charts = charts.lookup_agent_charts
    remember_agent_charts = charts.remember_agent_charts


__all__ = [
    "clear_charts_cache",
    "extract_agent_charts",
    "extract_agent_charts_bytes",
    "lookup_agent_charts",
    "remember_agent_charts",
]


def __getattr__(name: str) -> Any:
    """Resolve legacy chart symbols on demand."""
    if name not in __all__ and name not in ("_cache_key", "_CHARTS_CACHE"):
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from metabrowser.builtin_plugins.agents import charts

    return getattr(charts, name)
