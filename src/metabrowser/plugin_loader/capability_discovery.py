"""Discover trusted backend capabilities from installed Python distributions.

Capability discovery is intentionally separate from browser-plugin discovery. A
backend-only capability provider does not need a ``manifest.toml``, ``index.js``, or
static asset root, and viewed data can never opt itself into this installed trust
boundary.
"""

from __future__ import annotations

import importlib.metadata
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from metabrowser.plugin_loader.capability_types import CapabilitySet

CAPABILITY_ENTRY_POINT_GROUP = "metabrowser.capabilities.v1"


@dataclass(frozen=True, slots=True)
class LoadedCapabilitySet:
    """One capability set loaded from an installed entry point."""

    provider_id: str
    source_distribution: str | None
    capabilities: CapabilitySet


@dataclass(frozen=True, slots=True)
class CapabilityDiscoveryResult:
    """Deterministic installed capability declarations and discovery errors."""

    providers: tuple[LoadedCapabilitySet, ...] = ()
    errors: tuple[str, ...] = ()


def _source_distribution(entry_point: importlib.metadata.EntryPoint) -> str | None:
    distribution = getattr(entry_point, "dist", None)
    name = getattr(distribution, "name", None)
    return name if isinstance(name, str) and name else None


def discover_capability_sets() -> CapabilityDiscoveryResult:
    """Load only explicitly installed ``metabrowser.capabilities.v1`` providers.

    Discovery reports every load error, but registry construction treats any such
    error as fatal. Duplicate provider IDs are never ordered overrides.
    """
    entry_points = tuple(
        sorted(
            importlib.metadata.entry_points(group=CAPABILITY_ENTRY_POINT_GROUP),
            key=lambda entry_point: (entry_point.name, entry_point.value),
        )
    )
    duplicate_names = {
        name
        for name, count in Counter(entry_point.name for entry_point in entry_points).items()
        if count > 1
    }
    errors = [f"duplicate capability provider id {name!r}" for name in sorted(duplicate_names)]
    providers: list[LoadedCapabilitySet] = []
    for entry_point in entry_points:
        if entry_point.name in duplicate_names:
            continue
        try:
            factory_object = entry_point.load()
            if not callable(factory_object):
                raise TypeError(f"{entry_point.value} is not callable")
            factory = cast(Callable[[], object], factory_object)
            capabilities = factory()
            if not isinstance(capabilities, CapabilitySet):
                raise TypeError("capability factory must return CapabilitySet")
        except Exception as exc:
            errors.append(f"capability entry-point {entry_point.name!r}: {exc}")
            continue
        providers.append(
            LoadedCapabilitySet(
                provider_id=entry_point.name,
                source_distribution=_source_distribution(entry_point),
                capabilities=capabilities,
            )
        )
    return CapabilityDiscoveryResult(providers=tuple(providers), errors=tuple(errors))


__all__ = [
    "CAPABILITY_ENTRY_POINT_GROUP",
    "CapabilityDiscoveryResult",
    "LoadedCapabilitySet",
    "discover_capability_sets",
]
