"""``config.yml``, the user-owned configuration: its name and the bound on its size.

Two readers share these. ``cache/layout.py`` reads the whole record through its contract
(``ApplicationConfig`` in ``cache/records.py``), and :mod:`metabrowser.open_in` reads the
one setting ``metab --present`` needs, without loading the cache package, which a
folder's server and a client mode never import beyond its route table
(``tests/test_plugin_public_api.py``). ``cache/paths.py`` names them with the rest of the
layout. The file lives in ``configuration_directory()`` (``metabrowser.home``).
"""

from __future__ import annotations

from typing import Final

CONFIG_RECORD: Final = "config.yml"
# Every /api/cache/layout request reads and validates the whole config on a shared
# thread, so this bound is a claim about that cost. Measured on macOS arm64 and Python
# 3.14 by filling config.yml to each candidate bound and timing the route, five rounds
# each, on a machine also running unrelated work; maxima ran about 20% above the medians
# below:
#
# - Unknown settings, the most expensive shape: 25 ms at 4 KiB, 87 ms at 16 KiB, 181 ms
#   at 32 KiB, 341 ms at 64 KiB, and 1.33 s at 256 KiB. Cost is linear in the file, about
#   5 ms per KiB, almost all of it portable YAML parsing.
# - Upgrade entries: 22 ms, 70 ms, 136 ms, 274 ms, and 1.06 s at those sizes.
# - Deeply nested flow sequences are refused by the parser at about 220 ms whatever the
#   bound is, so no bound governs that shape.
#
# 16 KiB puts the worst shape beside what an ordinary cache page costs, which the
# measurements above DEFAULT_PAGE_LIMIT in cache/projection.py record. It holds about 300
# upgrade entries beside the 179-byte config this release writes, far more than a home
# accumulates, and no released Metabrowser has written a larger one. `metab --present`
# reads its one setting, `open_in`, within the same bound (`metabrowser.open_in`).
CONFIG_MAX_BYTES: Final = 16 * 1024

__all__ = ["CONFIG_MAX_BYTES", "CONFIG_RECORD"]
