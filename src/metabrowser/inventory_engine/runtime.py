"""Application-owned composition root for the inventory engine."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from metabrowser.constants import LOGS_DIR, STATE_DIR
from metabrowser.file_type_registry import load_file_type_registry_document
from metabrowser.inventory_engine.contract import (
    DiscoveryBudget,
    InventoryConfig,
    native_inventory_path,
)
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
    INVENTORY_MAX_FILES,
    SSE_BUS_INVENTORY_QUEUE_SIZE,
)


def default_inventory_config() -> InventoryConfig:
    """Build the provider config matching Metabrowser's current inventory scope."""

    return InventoryConfig(
        registry_document=load_file_type_registry_document(),
        budget=DiscoveryBudget(max_files=INVENTORY_MAX_FILES),
        hidden_allowlist=tuple(sorted((LOGS_DIR, STATE_DIR))),
        change_queue_size=SSE_BUS_INVENTORY_QUEUE_SIZE,
    )


def inventory_provider_from_environment() -> str:
    """Return the configured provider spelling for the sealed factory."""

    return os.environ.get("METABROWSER_INVENTORY_PROVIDER", InventoryProvider.PYTHON.value)


class InventoryRuntime:
    """Own one coordinator for one application lifespan."""

    def __init__(
        self,
        *,
        provider: InventoryProvider | str = InventoryProvider.PYTHON,
        config: InventoryConfig | None = None,
    ) -> None:
        self.config = config if config is not None else default_inventory_config()
        self.coordinator = InventoryCoordinator(
            backend=create_inventory_backend(provider),
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
        # The coordinator publishes every entry it discovers, so this listener sees the
        # whole first walk. That used to cost `invalidate_projection_path` once per
        # entry against caches that were empty, and each call resolved the path -- a
        # syscall -- once per projection cache: 45,516 resolves for 22,758 entries on
        # this repository, about 2s of a 4.9s walk.
        #
        # That cost is now removed in `MtimeCache.delete`, which returns before
        # resolving anything when the cache is empty. Removing it there rather than
        # here is what makes it free of semantics: an earlier version of this code
        # skipped the whole loop while the phase was DISCOVERING, which also skipped
        # real watcher and `refresh()` invalidations arriving during the initial walk
        # -- the watcher starts before the walk, so those exist. They were harmless
        # only because these caches are mtime keyed and revalidate on read, an
        # invariant living in another module with nothing binding the two together.
        # The membership check gets the same walk back without resting on it.
        for relative_path in change.dirty_paths:
            # Dirty paths are canonical identities; the projection caches are keyed by
            # resolved filesystem paths, so this crosses back to the platform spelling.
            native_relative = native_inventory_path(relative_path)
            if native_relative is None:
                continue
            invalidate_projection_path(root / native_relative)

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
