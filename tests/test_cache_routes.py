"""The read-only ``/api/cache/`` routes, through the mounted application.

What the routes answer is ``tests/golden/cli-api-cache.tryscript.md``: every envelope
for a missing, empty, populated, damaged, future, and shared home, in full. These tests
hold what a transcript cannot show. A read creates, locks, and repairs nothing; no
response carries a cache path, a Git internal, or a value from a record; every route
refuses a home the same way; and pages, bounds, and the verified listing behave at
their edges.

Every home is temporary and built by the production writers in
``tests/cache_home_fixture.py``. The routes resolve ``METABROWSER_HOME`` per request, so
each test points it at its own home after the application is imported.
"""

from __future__ import annotations

import os
import stat
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser.cache import listing as listing_module
from metabrowser.cache import projection
from metabrowser.cache.listing import ListingLimitError, list_private_directory
from metabrowser.cache.paths import SOURCES, STAGING, source_directory, source_record
from metabrowser.home import (
    METABROWSER_HOME_ENV,
    PrivateStorageError,
    SharedEntryPolicy,
    ensure_home,
    ensure_private_directory,
    write_private_file_atomic,
)
from metabrowser.server import app
from tests.cache_home_fixture import (
    CLICK,
    FLASK_HTTPS,
    FLASK_SSH,
    FLASK_STORE_KEY,
    ORPHAN_STORE_KEY,
    RECORD_SECRET,
    UNRECOGNIZED_ENTRY,
    build_damaged_home,
    build_empty_home,
    build_future_home,
    build_populated_home,
    build_shared_directories_home,
    build_shared_home,
)

pytestmark = pytest.mark.skipif(os.name != "posix", reason="owner-only storage needs POSIX")

LIST_ROUTES = ("/api/cache/layout", "/api/cache/sources", "/api/cache/stores")


@pytest.fixture
def client() -> Iterator[TestClient]:
    # No lifespan: these routes need no served root or inventory.
    yield TestClient(app)


@pytest.fixture
def use_home(monkeypatch: pytest.MonkeyPatch) -> Any:
    def point_at(home: Path) -> Path:
        monkeypatch.setenv(METABROWSER_HOME_ENV, str(home))
        return home

    return point_at


def _snapshot(root: Path) -> dict[str, tuple[int, int]]:
    """Every path below *root* with its mode and size, so any write or lock is visible."""

    entries: dict[str, tuple[int, int]] = {}
    if not root.exists():
        return entries
    for path in [root, *sorted(root.rglob("*"))]:
        status = path.lstat()
        entries[str(path.relative_to(root))] = (status.st_mode, status.st_size)
    return entries


def _json(client: TestClient, route: str, status: int = 200) -> dict[str, Any]:
    response = client.get(route)
    assert response.status_code == status, response.text
    return response.json()


# ── Home resolution and absence ────────────────────────────────────


@pytest.mark.parametrize("relative_home", ["missing", "missing-parent/home"])
def test_a_missing_home_is_an_absent_state_and_is_never_created(
    client: TestClient, use_home: Any, tmp_path: Path, relative_home: str
) -> None:
    home = use_home(tmp_path / relative_home)
    before = _snapshot(tmp_path)

    for route in LIST_ROUTES:
        assert _json(client, route)["home"] == "absent", route
    detail = _json(client, f"/api/cache/source/{FLASK_HTTPS.slug}", 404)

    assert detail["code"] == "source_not_found"
    assert not home.exists()
    assert _snapshot(tmp_path) == before


def test_a_home_without_a_cache_is_uninitialized_and_nothing_is_created(
    client: TestClient, use_home: Any, tmp_path: Path
) -> None:
    home = use_home(tmp_path / "home")
    home.mkdir(mode=0o700)
    before = _snapshot(tmp_path)

    layout = _json(client, "/api/cache/layout")
    sources = _json(client, "/api/cache/sources")
    stores = _json(client, "/api/cache/stores")

    assert layout["home"] == "present"
    assert layout["state"] == "uninitialized"
    assert layout["layout"] is None and layout["config"] is None
    assert layout["reclamation"] == {"staging_entries": 0}
    assert sources["home"] == "present" and sources["layout_format"] is None
    assert sources["sources"] == [] and stores["stores"] == []
    assert _snapshot(tmp_path) == before


def test_an_unusable_home_setting_is_a_typed_refusal(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(METABROWSER_HOME_ENV, "relative/home")

    for route in (*LIST_ROUTES, f"/api/cache/source/{FLASK_HTTPS.slug}"):
        body = _json(client, route, 409)
        assert body["code"] == "invalid_home_setting"
        assert "METABROWSER_HOME" in body["error"]


def test_a_shared_home_is_refused_without_its_path_and_left_unrepaired(
    client: TestClient, use_home: Any, tmp_path: Path
) -> None:
    home = use_home(tmp_path / "shared")
    build_shared_home(home)
    before = _snapshot(tmp_path)

    for route in (*LIST_ROUTES, f"/api/cache/source/{FLASK_HTTPS.slug}"):
        response = client.get(route)
        assert response.status_code == 409, route
        assert response.json()["code"] == "home_not_private", route
        assert str(tmp_path) not in response.text

    assert stat.S_IMODE(home.stat().st_mode) == 0o755
    assert _snapshot(tmp_path) == before


def test_a_symlinked_sources_directory_is_refused_rather_than_listed(
    client: TestClient, use_home: Any, tmp_path: Path
) -> None:
    home = use_home(tmp_path / "home")
    build_empty_home(home)
    elsewhere = tmp_path / "elsewhere"
    (elsewhere / FLASK_HTTPS.slug).mkdir(parents=True)
    (home / SOURCES).rmdir()
    (home / SOURCES).symlink_to(elsewhere, target_is_directory=True)

    response = client.get("/api/cache/sources")

    assert response.status_code == 409
    assert response.json()["code"] == "home_not_private"
    assert response.json()["violation"] == "symlink"
    assert FLASK_HTTPS.slug not in response.text


# ── Layout ─────────────────────────────────────────────────────────


def test_a_config_behind_its_layout_is_an_unfinished_migration(
    client: TestClient, use_home: Any, tmp_path: Path
) -> None:
    home = use_home(tmp_path / "home")
    build_empty_home(home)
    (home / "config.yml").unlink()

    layout = _json(client, "/api/cache/layout")

    assert layout["state"] == "config_pending"
    assert layout["config"] is None


def test_a_future_layout_is_refused_by_every_route_before_reading_entries(
    client: TestClient, use_home: Any, tmp_path: Path
) -> None:
    home = use_home(tmp_path / "home")
    build_future_home(home)
    before = _snapshot(tmp_path)

    for route in (*LIST_ROUTES, f"/api/cache/source/{FLASK_HTTPS.slug}"):
        assert _json(client, route, 409)["code"] == "future_format", route

    assert _snapshot(tmp_path) == before


def test_entries_without_a_layout_are_refused_like_migration_refuses_them(
    client: TestClient, use_home: Any, tmp_path: Path
) -> None:
    home = use_home(tmp_path / "home")
    ensure_home(home)
    ensure_private_directory(home, f"{SOURCES}/{FLASK_HTTPS.slug}")

    for route in LIST_ROUTES:
        body = _json(client, route, 409)
        assert body["code"] == "layout_missing", route
        assert str(tmp_path) not in body["error"]


def test_an_unreadable_layout_is_a_typed_refusal(
    client: TestClient, use_home: Any, tmp_path: Path
) -> None:
    home = use_home(tmp_path / "home")
    ensure_home(home)
    write_private_file_atomic(home, "cache/layout.yml", b"layout: [unclosed\n")

    for route in LIST_ROUTES:
        body = _json(client, route, 409)
        assert body["code"] == "layout_unreadable", route


# ── A populated cache ──────────────────────────────────────────────


@pytest.fixture
def populated(use_home: Any, tmp_path: Path) -> Path:
    home = use_home(tmp_path / "home")
    build_populated_home(home)
    return home


def test_an_unknown_or_malformed_slug_is_answered_honestly(
    client: TestClient, populated: Path
) -> None:
    missing = _json(client, "/api/cache/source/github-com--nobody--nothing--000000000000", 404)
    malformed = _json(client, "/api/cache/source/Not_A_Slug", 400)

    assert missing["code"] == "source_not_found"
    assert malformed["code"] == "invalid_parameter"


def test_pages_follow_the_sorted_keys_and_clamp_their_limit(
    client: TestClient, populated: Path
) -> None:
    slugs = sorted([CLICK.slug, FLASK_HTTPS.slug, FLASK_SSH.slug])

    first = _json(client, "/api/cache/sources?limit=2")
    second = _json(client, f"/api/cache/sources?limit=2&after={first['next_after']}")
    clamped_low = _json(client, "/api/cache/sources?limit=0")
    clamped_high = _json(client, "/api/cache/sources?limit=99999")
    unparsable = _json(client, "/api/cache/sources?limit=many")
    stores = _json(client, "/api/cache/stores?limit=1")

    assert [row["slug"] for row in second["sources"]] == slugs[2:]
    assert second["next_after"] is None
    assert clamped_low["limit"] == 1 and len(clamped_low["sources"]) == 1
    assert clamped_high["limit"] == projection.MAX_PAGE_LIMIT
    assert unparsable["limit"] == projection.DEFAULT_PAGE_LIMIT
    assert len(stores["stores"]) == 1
    assert stores["next_after"] == stores["stores"][0]["id"]
    after_store = _json(client, f"/api/cache/stores?after={stores['next_after']}")
    assert [row["id"] for row in after_store["stores"]] == [
        f"sha256:{max(FLASK_STORE_KEY, ORPHAN_STORE_KEY)}"
    ]


@pytest.mark.parametrize(
    "route",
    ["/api/cache/sources?after=Not_A_Slug", "/api/cache/stores?after=sha256:xyz"],
)
def test_a_malformed_page_key_is_a_bad_request(
    client: TestClient, populated: Path, route: str
) -> None:
    assert _json(client, route, 400)["code"] == "invalid_parameter"


@pytest.mark.parametrize("build", [build_populated_home, build_damaged_home])
def test_reads_change_nothing_and_name_nothing_private(
    client: TestClient, use_home: Any, tmp_path: Path, build: Callable[[Path], None]
) -> None:
    """Every route over the two homes whose answers the golden records in full.

    The snapshot holds modes, so in the damaged home an entry other users can reach
    was reported and not tightened, and in both no lock file appeared. A store holds
    pack files, a record that fails validation can hold a credential-bearing URL, and
    an unrecognized entry can be named anything, so none of those may reach a response.
    """

    build(use_home(tmp_path / "home"))
    before = _snapshot(tmp_path)

    slugs = [row["slug"] for row in _json(client, "/api/cache/sources")["sources"]]
    for route in (*LIST_ROUTES, *(f"/api/cache/source/{slug}" for slug in slugs)):
        response = client.get(route)
        assert response.status_code == 200, (route, response.text)
        for private in (
            str(tmp_path),
            "repository.git",
            ".pack",
            "configuration_digest",
            UNRECOGNIZED_ENTRY,
            RECORD_SECRET,
            "input_value",
        ):
            assert private not in response.text, (route, private)

    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize(
    ("layout_path", "route"),
    [(SOURCES, "/api/cache/sources"), (STAGING, "/api/cache/layout")],
)
def test_a_shared_cache_directory_is_refused_and_left_as_it_is(
    client: TestClient, use_home: Any, tmp_path: Path, layout_path: str, route: str
) -> None:
    home = use_home(tmp_path / "home")
    build_shared_directories_home(home)

    body = _json(client, route, 409)

    assert body["code"] == "home_not_private" and body["path"] == layout_path
    assert str(home) not in body["error"]
    assert stat.S_IMODE((home / layout_path).stat().st_mode) == 0o755


def _unrecognized_entry(home: Path) -> None:
    ensure_private_directory(home, f"{SOURCES}/{UNRECOGNIZED_ENTRY}")


def _unreadable_alias(home: Path) -> None:
    write_private_file_atomic(
        home, source_record(FLASK_SSH.slug, "store-alias.yml"), b"alias: nonsense\n"
    )


def _shared_entry(home: Path) -> None:
    (home / source_directory(FLASK_SSH.slug)).chmod(0o750)


@pytest.mark.parametrize("damage", [_unrecognized_entry, _unreadable_alias, _shared_entry])
def test_whatever_could_hide_a_reference_makes_an_unreferenced_store_unknown(
    client: TestClient, populated: Path, damage: Callable[[Path], None]
) -> None:
    """One cause at a time; the damaged home in the golden has all three at once.

    click's store has no alias. An entry that is not a slug, an alias that does not
    parse, and an alias other users can reach might each name it, so reclamation must
    not read it as unreferenced. The flask store keeps the alias that still reads.
    """

    orphan, flask = f"sha256:{ORPHAN_STORE_KEY}", f"sha256:{FLASK_STORE_KEY}"
    stores = {row["id"]: row for row in _json(client, "/api/cache/stores")["stores"]}
    assert stores[orphan]["reference_state"] == "unreferenced"

    damage(populated)

    stores = {row["id"]: row for row in _json(client, "/api/cache/stores")["stores"]}
    assert stores[orphan]["reference_state"] == "unknown"
    assert stores[flask]["reference_state"] == "referenced"


# ── Bounds ─────────────────────────────────────────────────────────


def test_a_directory_past_the_enumeration_bound_is_refused(
    client: TestClient, populated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(projection, "MAX_DIRECTORY_ENTRIES", 2)

    body = _json(client, "/api/cache/sources", 503)

    assert body["code"] == "cache_enumeration_limit"


def test_a_reference_scan_cut_by_the_record_budget_reports_unknown(
    client: TestClient, populated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The page is served first; what the budget has left decides how far aliases go."""

    # Two store rows at two records each, and nothing left for the three aliases.
    monkeypatch.setattr(projection, "MAX_RECORDS_PER_REQUEST", 4)

    body = _json(client, "/api/cache/stores")
    rows = {row["id"]: row for row in body["stores"]}

    assert len(rows) == 2 and body["next_after"] is None
    assert {row["reference_state"] for row in rows.values()} == {"unknown"}
    assert all(row["referenced_by"] == [] for row in rows.values())


def test_a_page_cut_by_the_record_budget_stays_resumable(
    client: TestClient, populated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(projection, "MAX_RECORDS_PER_REQUEST", 3)
    slugs = sorted([CLICK.slug, FLASK_HTTPS.slug, FLASK_SSH.slug])

    first = _json(client, "/api/cache/sources")

    assert [row["slug"] for row in first["sources"]] == slugs[:1]
    assert first["limit"] == projection.DEFAULT_PAGE_LIMIT
    assert first["next_after"] == slugs[0]


# ── The verified listing helper ────────────────────────────────────


def test_listing_is_sorted_verified_and_never_creates(tmp_path: Path) -> None:
    home = tmp_path / "home"
    build_empty_home(home)
    for name in ("b", "a", "c"):
        ensure_private_directory(home, f"{SOURCES}/{name}")
    before = _snapshot(tmp_path)

    assert list_private_directory(home, SOURCES, max_entries=10) == ("a", "b", "c")
    with pytest.raises(FileNotFoundError):
        list_private_directory(home, "cache/absent", max_entries=10)
    with pytest.raises(ListingLimitError):
        list_private_directory(home, SOURCES, max_entries=2)
    assert _snapshot(tmp_path) == before


def test_the_listing_comes_from_the_verified_descriptor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A directory swapped for a link right after verification cannot change the answer."""

    home = tmp_path / "home"
    build_empty_home(home)
    for name in ("a", "b"):
        ensure_private_directory(home, f"{SOURCES}/{name}")
    decoy = tmp_path / "decoy"
    (decoy / "impostor").mkdir(parents=True)
    open_directory = listing_module._open_directory_entry

    def swap_after_verifying(
        parent_fd: int,
        name: str,
        path: Path,
        *,
        create: bool,
        shared: SharedEntryPolicy = "repair",
    ) -> int:
        fd = open_directory(parent_fd, name, path, create=create, shared=shared)
        if name == SOURCES.rpartition("/")[2]:
            (home / SOURCES).rename(tmp_path / "moved-aside")
            (home / SOURCES).symlink_to(decoy, target_is_directory=True)
        return fd

    monkeypatch.setattr(listing_module, "_open_directory_entry", swap_after_verifying)

    assert list_private_directory(home, SOURCES, max_entries=10) == ("a", "b")


def test_listing_refuses_a_symlinked_directory(tmp_path: Path) -> None:
    home = tmp_path / "home"
    build_empty_home(home)
    (tmp_path / "elsewhere").mkdir()
    (home / SOURCES).rmdir()
    (home / SOURCES).symlink_to(tmp_path / "elsewhere", target_is_directory=True)

    with pytest.raises(PrivateStorageError) as refused:
        list_private_directory(home, SOURCES, max_entries=10)

    assert refused.value.violation.value == "symlink"
    assert str(tmp_path) not in str(refused.value)
