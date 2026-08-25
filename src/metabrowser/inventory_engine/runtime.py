"""Application-owned composition root for the inventory engine."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from metabrowser.constants import LOGS_DIR, STATE_DIR
from metabrowser.file_type_registry import load_file_type_registry
from metabrowser.inventory_engine.contract import InventoryBackend, InventoryConfig
from metabrowser.inventory_engine.coordinator import (
    HostChange,
    HostVersion,
    InventoryCoordinator,
)
from metabrowser.inventory_engine.factory import InventoryProvider, create_inventory_backend
from metabrowser.projections import (
    invalidate_all_projection_caches,
)
from metabrowser.projections import (
    invalidate_path as invalidate_projection_path,
)
from metabrowser.settings import (
    INVENTORY_MAX_DEPTH,
    INVENTORY_MAX_FILES,
    SSE_BUS_INVENTORY_QUEUE_SIZE,
)


def default_inventory_config() -> InventoryConfig:
    """Build the provider config matching Metabrowser's current inventory scope."""

    return InventoryConfig(
        max_files=INVENTORY_MAX_FILES,
        max_depth=INVENTORY_MAX_DEPTH,
        hidden_allowlist=tuple(sorted((LOGS_DIR, STATE_DIR))),
        registry_fingerprint=load_file_type_registry().fingerprint,
        change_queue_size=SSE_BUS_INVENTORY_QUEUE_SIZE,
    )


def inventory_provider_from_environment() -> InventoryProvider:
    """Resolve the sealed provider selection used by the composition root."""

    raw = os.environ.get("METABROWSER_INVENTORY_PROVIDER", InventoryProvider.PYTHON.value)
    try:
        return InventoryProvider(raw.strip().lower())
    except ValueError as error:
        supported = ", ".join(provider.value for provider in InventoryProvider)
        raise RuntimeError(
            f"unknown inventory provider {raw!r}; supported providers: {supported}"
        ) from error


class InventoryRuntime:
    """Own one coordinator for one application lifespan."""

    def __init__(
        self,
        *,
        provider: InventoryProvider | str = InventoryProvider.PYTHON,
        config: InventoryConfig | None = None,
        backend: InventoryBackend | None = None,
    ) -> None:
        selected = InventoryProvider(provider)
        self.provider = selected
        self.config = config if config is not None else default_inventory_config()
        self.coordinator = InventoryCoordinator(
            backend=backend if backend is not None else create_inventory_backend(selected),
            config=self.config,
        )
        self._root: Path | None = None
        self._remove_invalidation_listener = self.coordinator.add_invalidation_listener(
            self._invalidate_host_projections
        )

    def _invalidate_host_projections(self, change: HostChange) -> None:
        root = self._root
        if root is None:
            return
        if change.reset or change.all_dirty:
            invalidate_all_projection_caches()
            return
        if not change.facts_changed:
            return
        for relative_path in change.dirty_paths:
            invalidate_projection_path(root / relative_path)

    async def open(self, root: Path) -> HostVersion:
        """Open the initial served root."""

        version = await self.coordinator.open(root)
        self._root = await asyncio.to_thread(root.resolve)
        return version

    async def replace_root(self, root: Path) -> HostVersion:
        """Replace the served root within the same application lifespan."""

        version = await self.coordinator.replace_root(root)
        self._root = await asyncio.to_thread(root.resolve)
        return version

    async def close(self) -> None:
        """Promptly stop and join all inventory work."""

        await self.coordinator.close()
        self._remove_invalidation_listener()
        self._root = None


__all__ = [
    "InventoryRuntime",
    "default_inventory_config",
    "inventory_provider_from_environment",
]
