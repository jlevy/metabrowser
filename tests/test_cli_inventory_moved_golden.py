"""Golden transcript: the moved-version outcome through ``metab --api`` and ``--walk``.

A version that keeps moving past every bounded assembly attempt cannot be produced from
a tryscript subprocess: nothing a fixture writes holds the inventory moving for exactly
the length of one request, and the application has no switch that would, nor should
it. So this transcript runs ``metab`` in process, as the other ``.txt`` goldens do, with
the selected provider behind `tests/perturbed_provider.py`, whose ``unavailable``
perturbation fails the reads each consumer assembles from. What it pins is everything a
caller sees: each route's 503 status and body, and the command-line error and exit
status. `tests/test_inventory_moved.py` asserts the ``Retry-After`` header, which
``--api`` does not print, and the event stream's resync.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from metabrowser.inventory_engine.contract import QueryKind, ReadRequest
from tests.golden_harness import block, check_golden, normalize_console, run_metab
from tests.perturbed_provider import reads_asking_for
from tests.test_inventory_moved import build_moved_fixture, route_catalog, serve_unavailable

_ROUTES = (
    "/api/tree?depth=2",
    "/api/tree?group_by=type&depth=2",
    "/api/catalog",
    "/api/rollup?path=&depth=0",
)

_TREES = reads_asking_for(QueryKind.DIRECTORY, QueryKind.GROUPED_TREE, QueryKind.ROLLUP)
_CATALOG = reads_asking_for(QueryKind.CATALOG, matching=route_catalog)


def _unavailable(request: ReadRequest) -> bool:
    return _TREES(request) or _CATALOG(request)


def test_golden_inventory_moved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("METABROWSER_PLUGINS_DIRS", raising=False)
    monkeypatch.delenv("METABROWSER_LOG_LEVEL", raising=False)
    root = build_moved_fixture(tmp_path / "movedroot")
    serve_unavailable(monkeypatch, _unavailable)
    commands = [
        *(("--api", route) for route in _ROUTES),
        ("--walk", "--format", "json"),
    ]
    blocks: list[str] = []
    for arguments in commands:
        result = run_metab([str(root), *arguments])
        assert result.exit_code == 1, result.stdout + result.stderr
        shown = " ".join(f"'{argument}'" if "?" in argument else argument for argument in arguments)
        blocks.append(
            block(
                f"metab <ROOT>/movedroot {shown}",
                result.exit_code,
                normalize_console(result.stdout, tmp_path),
                normalize_console(result.stderr, tmp_path),
            )
        )
    check_golden("cli-api-inventory-moved.txt", "\n".join(blocks))
