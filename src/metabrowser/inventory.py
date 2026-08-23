"""Temporary imports for consumers migrating to the inventory-engine package."""

from metabrowser.inventory_engine.providers.python import (
    DEFAULT_MAX_DEPTH,
    DEFAULT_MAX_FILES,
    DEFAULT_REFRESH_TTL_S,
    IndexStatus,
    PythonInventoryHandle,
    walk_tree,
)

InventoryIndex = PythonInventoryHandle


class _Singleton:
    instance: PythonInventoryHandle | None = None


def get_instance() -> PythonInventoryHandle:
    """Return the temporary process owner while consumers migrate."""

    if _Singleton.instance is None:
        _Singleton.instance = PythonInventoryHandle()
    return _Singleton.instance


def reset_instance_for_tests() -> None:
    """Clear the temporary process owner between tests."""

    if _Singleton.instance is not None:
        _Singleton.instance.clear()
    _Singleton.instance = None


__all__ = [
    "DEFAULT_MAX_DEPTH",
    "DEFAULT_MAX_FILES",
    "DEFAULT_REFRESH_TTL_S",
    "IndexStatus",
    "InventoryIndex",
    "get_instance",
    "reset_instance_for_tests",
    "walk_tree",
]
