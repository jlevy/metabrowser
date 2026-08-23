"""Application-owned composition root for the inventory engine."""

from __future__ import annotations

from pathlib import Path

from metabrowser.constants import LOGS_DIR, STATE_DIR
from metabrowser.file_type_registry import load_file_type_registry
from metabrowser.inventory_engine.contract import InventoryConfig
from metabrowser.inventory_engine.coordinator import HostVersion, InventoryCoordinator
from metabrowser.inventory_engine.factory import InventoryProvider, create_inventory_backend
from metabrowser.settings import (
    INVENTORY_MAX_DEPTH,
    INVENTORY_MAX_FILES,
    SSE_BUS_INVENTORY_QUEUE_SIZE,
)


def default_inventory_config() -> InventoryConfig:
    """Build the provider config matching Metabrowser's current inventory scope."""

    return InventoryConfig(
        max_entries=INVENTORY_MAX_FILES,
        max_depth=INVENTORY_MAX_DEPTH,
        hidden_allowlist=tuple(sorted((LOGS_DIR, STATE_DIR))),
        registry_fingerprint=load_file_type_registry().fingerprint,
        change_queue_size=SSE_BUS_INVENTORY_QUEUE_SIZE,
    )


class InventoryRuntime:
    """Own one coordinator for one application lifespan."""

    def __init__(
        self,
        *,
        provider: InventoryProvider | str = InventoryProvider.PYTHON,
        config: InventoryConfig | None = None,
    ) -> None:
        selected = InventoryProvider(provider)
        self.provider = selected
        self.config = config if config is not None else default_inventory_config()
        self.coordinator = InventoryCoordinator(
            backend=create_inventory_backend(selected),
            config=self.config,
        )

    async def open(self, root: Path) -> HostVersion:
        """Open the initial served root."""

        return await self.coordinator.open(root)

    async def replace_root(self, root: Path) -> HostVersion:
        """Replace the served root within the same application lifespan."""

        return await self.coordinator.replace_root(root)

    async def close(self) -> None:
        """Promptly stop and join all inventory work."""

        await self.coordinator.close()


__all__ = ["InventoryRuntime", "default_inventory_config"]
