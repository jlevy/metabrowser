"""The parity table is checked against the routes the app actually mounts.

`devtools/check_parity.py` scans source text, which is fast enough for `make
lint` but can only see what its pattern matches. It has already missed a route
once: `/api/diagnostics/pending-tallies` is registered with its path on the line
after `Route(`, so a pattern anchored to `Route("` skipped it silently.

This test asks the built application instead. Static scanning and runtime truth
must agree, so a registration style the scanner cannot read fails here rather
than quietly leaving a route ungoverned.
"""

from __future__ import annotations

from devtools.check_parity import MAP_DOC, parity_rows, registered_surfaces


def _runtime_api_routes() -> set[str]:
    from metabrowser import server

    surfaces: set[str] = set()
    for route in server.app.routes:
        path = getattr(route, "path", None)
        if isinstance(path, str) and path.startswith("/api/"):
            surfaces.add(path.split("{", 1)[0].rstrip("/"))
    return surfaces


def test_the_static_scan_finds_every_route_the_app_mounts() -> None:
    missed = _runtime_api_routes() - registered_surfaces()

    assert not missed, (
        f"check_parity's source scan missed {sorted(missed)}; "
        "these routes are mounted but invisible to the parity gate"
    )


def test_every_mounted_route_has_a_parity_row() -> None:
    listed = {row.surface for row in parity_rows(MAP_DOC.read_text(encoding="utf-8"))}
    missing = _runtime_api_routes() - listed

    assert not missing, f"mounted but absent from the parity table: {sorted(missing)}"
