"""Shared metabrowser test fixtures.

Resets the inventory and events bus so tests that drive the walker or
subscribe to the event stream do not leak
state across tests. Without this fixture, the InventoryIndex singleton
(populated by one test, e.g. the migration suite) would intercept later
tests that expect the legacy filesystem walk path.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest


@pytest.fixture(autouse=True)
def _reset_browser_inventory() -> Generator[None, None, None]:
    """Reset the process-wide InventoryIndex + events bus between tests."""
    yield
    try:
        from metabrowser.events_route import (  # noqa: PLC0415 -- guarded import (optional dep / circular)
            reset_bus_for_tests,
        )
        from metabrowser.inventory import (  # noqa: PLC0415 -- guarded import (optional dep / circular)
            reset_instance_for_tests,
        )

        reset_instance_for_tests()
        reset_bus_for_tests()
    except Exception:  # noqa: BLE001
        # Defensive: never let cleanup failure mask a test failure.
        pass
