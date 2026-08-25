"""Sealed construction point for in-tree inventory providers."""

from __future__ import annotations

from enum import StrEnum
from typing import assert_never

from metabrowser.inventory_engine.contract import InventoryBackend
from metabrowser.inventory_engine.providers.python_inventory import PythonInventoryBackend


class InventoryProvider(StrEnum):
    """Inventory implementations shipped in this Metabrowser build."""

    PYTHON = "python"


def create_inventory_backend(
    provider: InventoryProvider | str = InventoryProvider.PYTHON,
) -> InventoryBackend:
    """Construct the selected backend or fail explicitly for an unknown name."""

    normalized = str(provider).strip().lower()
    try:
        selected = InventoryProvider(normalized)
    except ValueError as error:
        raise ValueError(f"unknown inventory provider: {provider!r}") from error
    if selected is InventoryProvider.PYTHON:
        return PythonInventoryBackend()
    assert_never(selected)


__all__ = ["InventoryProvider", "create_inventory_backend"]
