"""The read-only ``/api/cache/`` routes, through the mounted application.

Every home is temporary and built by the production writers in
``tests/cache_home_fixture.py``. The routes resolve ``METABROWSER_HOME`` per request, so
each test points it at its own home after the application is imported. Beyond the
projected shapes, the tests prove the boundaries: a missing home is an answer rather than
an error or a side effect, reads create and lock nothing, refusals are typed and
path-free, and no response names a cache path, a pack file, or a Git internal.
"""

from __future__ import annotations

import os
import stat
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from metabrowser.cache import listing as listing_module
from metabrowser.cache import projection
from metabrowser.cache.atomic import write_record_atomic
from metabrowser.cache.listing import ListingLimitError, list_private_directory
from metabrowser.cache.paths import (
    SOURCES,
    STAGING,
    quarantine_entry,
    source_directory,
    source_record,
    store_record,
)
from metabrowser.cache.records import (
    REPOSITORY_STORE_ALIAS_CONTRACT_ID,
    RepositoryStoreAlias,
)
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
    FIXTURE_VERSION,
    FLASK_HTTPS,
    FLASK_REVISION,
    FLASK_SSH,
    FLASK_STORE_KEY,
    JINJA,
    OPENED_AT,
    ORPHAN_STORE_KEY,
    QUARANTINED_STORE_KEY,
    RECLAIMED_STORE_KEY,
    build_empty_home,
    build_future_home,
    build_populated_home,
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

    layout = _json(client, "/api/cache/layout")
    sources = _json(client, "/api/cache/sources")
    stores = _json(client, "/api/cache/stores")
    detail = _json(client, f"/api/cache/source/{FLASK_HTTPS.slug}", 404)

    assert layout == {
        "home": "absent",
        "supported_format": "f01",
        "state": "absent",
        "layout": None,
        "config": None,
        "reclamation": None,
    }
    assert sources == {
        "home": "absent",
        "layout_format": None,
        "sources": [],
        "unrecognized_entries": 0,
        "limit": projection.DEFAULT_PAGE_LIMIT,
        "next_after": None,
    }
    assert stores["home"] == "absent" and stores["stores"] == []
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
    assert layout["reclamation"] == {
        "staging_entries": 0,
        "trash_entries": 0,
        "quarantine_entries": 0,
        "quarantine": [],
        "quarantine_truncated": False,
    }
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
        body = response.json()
        assert body["code"] == "home_not_private"
        assert body["location"] == "home"
        assert body["violation"] == "permissive"
        assert "0755" in body["error"]
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


def test_an_empty_cache_reports_its_current_layout_and_config(
    client: TestClient, use_home: Any, tmp_path: Path
) -> None:
    build_empty_home(use_home(tmp_path / "home"))

    layout = _json(client, "/api/cache/layout")
    sources = _json(client, "/api/cache/sources")
    stores = _json(client, "/api/cache/stores")

    assert layout == {
        "home": "present",
        "supported_format": "f01",
        "state": "current",
        "layout": {"format": "f01", "created_by": FIXTURE_VERSION},
        "config": {"format": "f01", "written_by": FIXTURE_VERSION, "upgrades": []},
        "reclamation": {
            "staging_entries": 0,
            "trash_entries": 0,
            "quarantine_entries": 0,
            "quarantine": [],
            "quarantine_truncated": False,
        },
    }
    assert sources["layout_format"] == "f01" and sources["sources"] == []
    assert stores["layout_format"] == "f01" and stores["stores"] == []


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
        body = _json(client, route, 409)
        assert body["code"] == "future_format", route
        assert body["found"] == "f02" and body["supported"] == "f01"
        assert "Upgrade Metabrowser" in body["error"]

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
def populated(use_home: Any, tmp_path: Path) -> tuple[Path, str]:
    home = use_home(tmp_path / "home")
    entry = build_populated_home(home)
    return home, entry


def test_reclamation_outcomes_are_reported_on_the_layout(
    client: TestClient, populated: tuple[Path, str]
) -> None:
    _home, entry = populated

    layout = _json(client, "/api/cache/layout")

    assert layout["state"] == "current"
    assert layout["reclamation"] == {
        "staging_entries": 1,
        "trash_entries": 0,
        "quarantine_entries": 1,
        "quarantine": [
            {
                "entry": entry,
                "sources": [JINJA.slug],
                "stores": [f"sha256:{QUARANTINED_STORE_KEY}"],
                "truncated": False,
            }
        ],
        "quarantine_truncated": False,
    }


def test_sources_report_identity_alias_generation_and_publication(
    client: TestClient, populated: tuple[Path, str]
) -> None:
    body = _json(client, "/api/cache/sources")

    assert body["home"] == "present" and body["layout_format"] == "f01"
    assert body["next_after"] is None and body["unrecognized_entries"] == 0
    rows = {row["slug"]: row for row in body["sources"]}
    assert list(rows) == sorted([CLICK.slug, FLASK_HTTPS.slug, FLASK_SSH.slug])
    assert JINJA.slug not in rows

    https = rows[FLASK_HTTPS.slug]
    assert https == {
        "slug": FLASK_HTTPS.slug,
        "publication": "published",
        "identity": {
            "id": FLASK_HTTPS.id,
            "display_url": FLASK_HTTPS.address,
            "clone_url": FLASK_HTTPS.address,
            "transport": "https",
            "created_at": "2026-09-17T12:00:00Z",
        },
        "alias": {
            "store_id": f"sha256:{FLASK_STORE_KEY}",
            "generation": 1,
            "updated_at": "2026-09-17T12:00:06Z",
        },
        "state": {"last_opened_at": OPENED_AT},
        "problems": [],
    }
    ssh = rows[FLASK_SSH.slug]
    assert ssh["publication"] == "published"
    assert ssh["identity"]["transport"] == "ssh"
    assert ssh["alias"] == {
        "store_id": f"sha256:{FLASK_STORE_KEY}",
        "generation": 2,
        "updated_at": "2026-09-17T12:10:00Z",
    }
    assert ssh["state"] is None
    click = rows[CLICK.slug]
    assert click["publication"] == "unattached"
    assert click["alias"] is None and click["problems"] == []


def test_stores_report_references_and_what_reclamation_would_keep(
    client: TestClient, populated: tuple[Path, str]
) -> None:
    body = _json(client, "/api/cache/stores")

    rows = {row["id"]: row for row in body["stores"]}
    assert list(rows) == sorted([f"sha256:{FLASK_STORE_KEY}", f"sha256:{ORPHAN_STORE_KEY}"])
    assert f"sha256:{QUARANTINED_STORE_KEY}" not in rows
    assert f"sha256:{RECLAIMED_STORE_KEY}" not in rows

    flask = rows[f"sha256:{FLASK_STORE_KEY}"]
    assert flask == {
        "id": f"sha256:{FLASK_STORE_KEY}",
        "publication": "published",
        "identity": {
            "created_at": "2026-09-17T12:00:00Z",
            "acquisition": {
                "strategy": "blobless",
                "git_version": "2.50.1",
                "object_format": "sha1",
            },
        },
        "state": {
            "object_state": "converging",
            "default_remote_ref": "refs/remotes/origin/trunk",
            "default_revision": FLASK_REVISION,
            "last_fetch_at": "2026-09-17T12:00:05Z",
            "last_operation": {
                "kind": "acquire",
                "outcome": "succeeded",
                "at": "2026-09-17T12:00:05Z",
            },
        },
        "problems": [],
        "referenced_by": [
            {"slug": FLASK_SSH.slug, "generation": 2},
            {"slug": FLASK_HTTPS.slug, "generation": 1},
        ],
        "reference_state": "referenced",
    }
    orphan = rows[f"sha256:{ORPHAN_STORE_KEY}"]
    assert orphan["publication"] == "published"
    assert orphan["referenced_by"] == [] and orphan["reference_state"] == "unreferenced"


def test_a_source_detail_adds_its_recency_and_its_store_head(
    client: TestClient, populated: tuple[Path, str]
) -> None:
    body = _json(client, f"/api/cache/source/{FLASK_HTTPS.slug}")

    assert body["home"] == "present" and body["layout_format"] == "f01"
    detail = body["source"]
    assert detail["publication"] == "published"
    assert detail["state"] == {"last_opened_at": OPENED_AT}
    assert detail["store"]["id"] == f"sha256:{FLASK_STORE_KEY}"
    assert detail["store"]["publication"] == "published"
    assert detail["store"]["state"]["default_revision"] == FLASK_REVISION
    assert "referenced_by" not in detail["store"]

    unattached = _json(client, f"/api/cache/source/{CLICK.slug}")["source"]
    assert unattached["publication"] == "unattached"
    assert unattached["state"] is None and unattached["store"] is None


def test_an_unknown_or_malformed_slug_is_answered_honestly(
    client: TestClient, populated: tuple[Path, str]
) -> None:
    missing = _json(client, "/api/cache/source/github-com--nobody--nothing--000000000000", 404)
    quarantined = _json(client, f"/api/cache/source/{JINJA.slug}", 404)
    malformed = _json(client, "/api/cache/source/Not_A_Slug", 400)

    assert missing["code"] == quarantined["code"] == "source_not_found"
    assert malformed["code"] == "invalid_parameter"


def test_pages_follow_the_sorted_keys_and_clamp_their_limit(
    client: TestClient, populated: tuple[Path, str]
) -> None:
    slugs = sorted([CLICK.slug, FLASK_HTTPS.slug, FLASK_SSH.slug])

    first = _json(client, "/api/cache/sources?limit=2")
    second = _json(client, f"/api/cache/sources?limit=2&after={first['next_after']}")
    clamped_low = _json(client, "/api/cache/sources?limit=0")
    clamped_high = _json(client, "/api/cache/sources?limit=99999")
    unparsable = _json(client, "/api/cache/sources?limit=many")
    stores = _json(client, "/api/cache/stores?limit=1")

    assert [row["slug"] for row in first["sources"]] == slugs[:2]
    assert first["limit"] == 2 and first["next_after"] == slugs[1]
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
    client: TestClient, populated: tuple[Path, str], route: str
) -> None:
    assert _json(client, route, 400)["code"] == "invalid_parameter"


def test_reads_take_no_lock_and_write_nothing(
    client: TestClient, populated: tuple[Path, str], tmp_path: Path
) -> None:
    home, _entry = populated
    # Entries the old read path would have repaired, so the snapshot constrains that too.
    (home / source_record(CLICK.slug, "source.yml")).chmod(0o640)
    (home / source_directory(FLASK_SSH.slug)).chmod(0o750)
    before = _snapshot(tmp_path)

    for route in (*LIST_ROUTES, f"/api/cache/source/{FLASK_HTTPS.slug}"):
        _json(client, route)

    assert _snapshot(tmp_path) == before


def test_a_shared_record_is_reported_rather_than_repaired(
    client: TestClient, populated: tuple[Path, str]
) -> None:
    home, _entry = populated
    record = home / source_record(CLICK.slug, "source.yml")
    record.chmod(0o640)

    rows = {row["slug"]: row for row in _json(client, "/api/cache/sources")["sources"]}
    detail = _json(client, f"/api/cache/source/{CLICK.slug}")["source"]

    for row in (rows[CLICK.slug], detail):
        # A record Metabrowser refused to read is not a corrupt one; the user chmods it.
        assert row["publication"] == "not_private"
        assert row["identity"] is None
        assert [(p["record"], p["code"]) for p in row["problems"]] == [
            ("source.yml", "not_private")
        ]
        assert str(home) not in str(row)
    assert stat.S_IMODE(record.stat().st_mode) == 0o640
    assert rows[FLASK_HTTPS.slug]["publication"] == "published"


def test_a_shared_entry_directory_is_reported_rather_than_repaired(
    client: TestClient, populated: tuple[Path, str]
) -> None:
    home, _entry = populated
    directory = home / source_directory(CLICK.slug)
    directory.chmod(0o750)

    row = _json(client, f"/api/cache/source/{CLICK.slug}")["source"]

    assert row["publication"] == "not_private"
    assert {(p["record"], p["code"]) for p in row["problems"]} == {
        ("source.yml", "not_private"),
        ("store-alias.yml", "not_private"),
        ("state.yml", "not_private"),
    }
    assert stat.S_IMODE(directory.stat().st_mode) == 0o750


@pytest.mark.parametrize(
    ("layout_path", "route"),
    [(SOURCES, "/api/cache/sources"), (STAGING, "/api/cache/layout")],
)
def test_a_shared_cache_directory_is_refused_by_the_name_the_user_must_fix(
    client: TestClient, populated: tuple[Path, str], layout_path: str, route: str
) -> None:
    """A fixed layout name is not a secret, and without it the remedy is a guess."""

    home, _entry = populated
    directory = home / layout_path
    directory.chmod(0o755)

    body = _json(client, route, 409)

    assert body["code"] == "home_not_private"
    assert body["violation"] == "permissive"
    assert body["location"] == "entry"
    assert body["path"] == layout_path
    # The remedy fits a directory read, not a file a writer would replace.
    assert "chmod 700" in body["error"]
    assert "replace it atomically" not in body["error"]
    assert str(home) not in body["error"]
    assert stat.S_IMODE(directory.stat().st_mode) == 0o755


def test_a_shared_record_refusal_offers_the_file_remedy_without_naming_the_slug(
    client: TestClient, populated: tuple[Path, str]
) -> None:
    home, _entry = populated
    (home / source_record(CLICK.slug, "source.yml")).chmod(0o640)

    row = _json(client, f"/api/cache/source/{CLICK.slug}")["source"]

    (problem,) = row["problems"]
    assert "chmod 600" in problem["message"]
    assert "does not change your entries" in problem["message"]
    assert str(home) not in problem["message"]


def test_an_invalid_record_reports_its_rule_and_not_what_is_in_it(
    client: TestClient, populated: tuple[Path, str]
) -> None:
    """A record can hold a credential-bearing URL, so no reason may quote its values."""

    secret = "ghp-examplesecrettokenvalue"
    write_private_file_atomic(
        client_home := populated[0],
        source_record(CLICK.slug, "source.yml"),
        (
            "softschema:\n"
            "  contract: com.github.jlevy.metabrowser.cache:RepositorySource/v1\n"
            "  envelope: source\n"
            "  status: enforced\n"
            "source:\n"
            f"  id: sha256:{'0' * 64}\n"
            f"  slug: {CLICK.slug}\n"
            f"  display_url: https://user:{secret}@example.com/repo.git\n"
            f"  clone_url: https://user:{secret}@example.com/repo.git\n"
            "  transport: https\n"
            "  created_at: 2026-09-01T00:00:00Z\n"
        ).encode(),
    )

    row = _json(client, f"/api/cache/source/{CLICK.slug}")["source"]

    (problem,) = row["problems"]
    assert problem["code"] == "invalid"
    assert secret not in problem["message"]
    assert "input_value" not in problem["message"]
    assert "errors.pydantic.dev" not in problem["message"]
    assert str(client_home) not in problem["message"]
    assert "does not match its transport" in problem["message"]


def test_no_response_names_a_path_a_pack_or_a_git_internal(
    client: TestClient, populated: tuple[Path, str], tmp_path: Path
) -> None:
    for route in (*LIST_ROUTES, f"/api/cache/source/{FLASK_HTTPS.slug}"):
        text = client.get(route).text
        for forbidden in (str(tmp_path), "repository.git", ".pack", "configuration_digest"):
            assert forbidden not in text, (route, forbidden)


# ── Damage is reported per entry ───────────────────────────────────


def test_a_damaged_source_is_reported_beside_the_readable_ones(
    client: TestClient, populated: tuple[Path, str]
) -> None:
    home, _entry = populated
    write_private_file_atomic(
        home, source_record(FLASK_SSH.slug, "store-alias.yml"), b"alias: nonsense\n"
    )
    write_private_file_atomic(home, source_record(CLICK.slug, "source.yml"), b"source: {}\n")

    rows = {row["slug"]: row for row in _json(client, "/api/cache/sources")["sources"]}

    assert rows[FLASK_HTTPS.slug]["publication"] == "published"
    ssh = rows[FLASK_SSH.slug]
    assert ssh["publication"] == "damaged" and ssh["alias"] is None
    assert [(p["record"], p["code"]) for p in ssh["problems"]] == [("store-alias.yml", "invalid")]
    click = rows[CLICK.slug]
    assert click["publication"] == "damaged" and click["identity"] is None
    assert [(p["record"], p["code"]) for p in click["problems"]] == [("source.yml", "invalid")]

    stores = {row["id"]: row for row in _json(client, "/api/cache/stores")["stores"]}
    # An alias reclamation cannot read keeps every store it might name.
    assert stores[f"sha256:{ORPHAN_STORE_KEY}"]["reference_state"] == "unknown"
    assert stores[f"sha256:{FLASK_STORE_KEY}"]["reference_state"] == "referenced"


def test_an_alias_to_a_missing_store_is_dangling(
    client: TestClient, populated: tuple[Path, str]
) -> None:
    home, _entry = populated
    write_record_atomic(
        home,
        source_record(CLICK.slug, "store-alias.yml"),
        RepositoryStoreAlias(
            source_id=CLICK.id,
            store_id=f"sha256:{RECLAIMED_STORE_KEY}",
            generation=1,
            updated_at="2026-09-17T12:00:06Z",
        ),
        REPOSITORY_STORE_ALIAS_CONTRACT_ID,
    )

    rows = {row["slug"]: row for row in _json(client, "/api/cache/sources")["sources"]}

    assert rows[CLICK.slug]["publication"] == "dangling"


def test_an_alias_naming_another_source_is_a_mismatch(
    client: TestClient, populated: tuple[Path, str]
) -> None:
    home, _entry = populated
    write_record_atomic(
        home,
        source_record(CLICK.slug, "store-alias.yml"),
        RepositoryStoreAlias(
            source_id=FLASK_HTTPS.id,
            store_id=f"sha256:{ORPHAN_STORE_KEY}",
            generation=1,
            updated_at="2026-09-17T12:00:06Z",
        ),
        REPOSITORY_STORE_ALIAS_CONTRACT_ID,
    )

    row = _json(client, f"/api/cache/source/{CLICK.slug}")["source"]

    assert row["publication"] == "damaged"
    assert [(p["record"], p["code"]) for p in row["problems"]] == [("store-alias.yml", "mismatch")]


def test_a_store_without_its_state_record_is_damaged(
    client: TestClient, populated: tuple[Path, str]
) -> None:
    home, _entry = populated
    (home / store_record(ORPHAN_STORE_KEY, "state.yml")).unlink()

    rows = {row["id"]: row for row in _json(client, "/api/cache/stores")["stores"]}

    orphan = rows[f"sha256:{ORPHAN_STORE_KEY}"]
    assert orphan["publication"] == "damaged" and orphan["state"] is None
    assert [(p["record"], p["code"]) for p in orphan["problems"]] == [("state.yml", "missing")]


def test_a_damaged_source_state_damages_the_entry_on_both_routes(
    client: TestClient, populated: tuple[Path, str]
) -> None:
    """state.yml is read by both routes, so one entry cannot look healthy on one of them."""

    home, _entry = populated
    write_private_file_atomic(
        home, source_record(FLASK_HTTPS.slug, "state.yml"), b"state: nonsense\n"
    )

    listed = {row["slug"]: row for row in _json(client, "/api/cache/sources")["sources"]}
    detail = _json(client, f"/api/cache/source/{FLASK_HTTPS.slug}")["source"]

    for row in (listed[FLASK_HTTPS.slug], detail):
        assert row["publication"] == "damaged"
        assert row["state"] is None
        assert [(p["record"], p["code"]) for p in row["problems"]] == [("state.yml", "invalid")]
    assert listed[FLASK_HTTPS.slug]["alias"] == detail["alias"]


def test_unrecognized_source_entries_are_counted_not_named(
    client: TestClient, populated: tuple[Path, str]
) -> None:
    home, _entry = populated
    ensure_private_directory(home, f"{SOURCES}/Private Notes")

    sources = _json(client, "/api/cache/sources")
    stores = {row["id"]: row for row in _json(client, "/api/cache/stores")["stores"]}

    assert sources["unrecognized_entries"] == 1
    assert "Private Notes" not in str(sources)
    assert stores[f"sha256:{ORPHAN_STORE_KEY}"]["reference_state"] == "unknown"


# ── Bounds ─────────────────────────────────────────────────────────


def test_a_directory_past_the_enumeration_bound_is_refused(
    client: TestClient, populated: tuple[Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(projection, "MAX_DIRECTORY_ENTRIES", 2)

    body = _json(client, "/api/cache/sources", 503)

    assert body["code"] == "cache_enumeration_limit"


def test_a_quarantine_entry_reports_bounded_names(
    client: TestClient, populated: tuple[Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A quarantine entry cannot put an unbounded number of names in one response."""

    home, entry = populated
    monkeypatch.setattr(projection, "MAX_QUARANTINE_NAMES", 2)
    retained = f"{quarantine_entry(entry)}/sources"
    for index in range(3):
        ensure_private_directory(home, f"{retained}/example-com--org--repo-{index}--{index:012x}")

    quarantined = _json(client, "/api/cache/layout")["reclamation"]["quarantine"]

    assert len(quarantined) == 1
    assert len(quarantined[0]["sources"]) == 2
    assert quarantined[0]["truncated"] is True
    assert quarantined[0]["stores"] == [f"sha256:{QUARANTINED_STORE_KEY}"]


def test_a_reference_scan_cut_by_the_record_budget_reports_unknown(
    client: TestClient, populated: tuple[Path, str], monkeypatch: pytest.MonkeyPatch
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
    client: TestClient, populated: tuple[Path, str], monkeypatch: pytest.MonkeyPatch
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
        list_private_directory(home, "cache/provider-bindings", max_entries=10)
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
