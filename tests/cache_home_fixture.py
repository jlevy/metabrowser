"""Reproducible application homes for the cache read routes and their golden transcript.

Every home is written by the production writers: ``ensure_home`` and ``migrate_layout``
create the skeleton and layout, stores and sources are staged and published with
``publish_entry`` under the locks that own them, aliases are written under the store
lease and the source-alias lock, and quarantine and reclamation run through
``quarantine_entries`` and ``reclaim_store``. Addresses, versions, and timestamps are
fixed, so identities, slugs, and records are identical on every machine; only the
quarantine entry name is random, because ``quarantine_entries`` chooses it.

Run as a script, it builds every home the golden uses below one directory::

    cache_home_fixture.py <directory>
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from metabrowser.cache.atomic import publish_entry, write_record_atomic
from metabrowser.cache.identity import (
    GitTransport,
    ObjectFormat,
    cache_slug,
    repository_store_id,
    source_identity,
    store_key,
)
from metabrowser.cache.layout import migrate_layout
from metabrowser.cache.locks import (
    repository_store_lock,
    source_alias_lock,
    staging_entry_lock,
    store_lease,
)
from metabrowser.cache.paths import (
    LAYOUT_RECORD,
    source_directory,
    source_record,
    staging_entry,
    store_directory,
)
from metabrowser.cache.reclaim import StoreReclamation, quarantine_entries, reclaim_store
from metabrowser.cache.records import (
    CACHE_LAYOUT_CONTRACT_ID,
    REPOSITORY_SOURCE_CONTRACT_ID,
    REPOSITORY_SOURCE_STATE_CONTRACT_ID,
    REPOSITORY_STORE_ALIAS_CONTRACT_ID,
    REPOSITORY_STORE_CONTRACT_ID,
    REPOSITORY_STORE_STATE_CONTRACT_ID,
    CacheLayout,
    RepositorySource,
    RepositorySourceState,
    RepositoryStore,
    RepositoryStoreAlias,
    RepositoryStoreState,
    StoreAcquisition,
    StoreOperation,
)
from metabrowser.home import ensure_home, ensure_private_directory, write_private_file_atomic

FIXTURE_VERSION: Final = "0.11.0"
CREATED_AT: Final = "2026-09-17T12:00:00Z"
FETCHED_AT: Final = "2026-09-17T12:00:05Z"
ALIASED_AT: Final = "2026-09-17T12:00:06Z"
REPOINTED_AT: Final = "2026-09-17T12:10:00Z"
OPENED_AT: Final = "2026-09-17T12:30:00Z"
FLASK_REVISION: Final = "5f4c1a2e8b0d9c7e6a5f4b3c2d1e0f9a8b7c6d5e"
# A digest of the store's Git configuration; the routes never report it.
LEFTOVER_STAGING_ENTRY: Final = "acquire-interrupted"


@dataclass(frozen=True, slots=True)
class FixtureSource:
    """A source's address and the identities derived from it."""

    transport: GitTransport
    address: str

    @property
    def id(self) -> str:
        return source_identity(self.transport, self.address)

    @property
    def slug(self) -> str:
        return cache_slug(self.transport, self.address, self.id, slug_owner=lambda _slug: None)

    def store_key(self, object_format: ObjectFormat = "sha1") -> str:
        return store_key(repository_store_id(self.id, object_format))


FLASK_HTTPS: Final = FixtureSource("https", "https://github.com/pallets/flask")
FLASK_SSH: Final = FixtureSource("ssh", "git@github.com:pallets/flask.git")
CLICK: Final = FixtureSource("https", "https://github.com/pallets/click")
JINJA: Final = FixtureSource("https", "https://github.com/pallets/jinja")
WERKZEUG: Final = FixtureSource("https", "https://github.com/pallets/werkzeug")
# Both flask spellings share the store the HTTPS source acquired.
FLASK_STORE_KEY: Final = FLASK_HTTPS.store_key()
# An acquisition interrupted after publishing its store and before its alias.
ORPHAN_STORE_KEY: Final = CLICK.store_key()
QUARANTINED_STORE_KEY: Final = JINJA.store_key()
RECLAIMED_STORE_KEY: Final = WERKZEUG.store_key()


def _stage_and_publish_store(home: Path, key: str, *, with_revision: bool) -> None:
    entry = f"store-{key[:16]}"
    staged = staging_entry(entry)
    with staging_entry_lock(home, entry) as liveness:
        ensure_private_directory(home, f"{staged}/repository.git/objects/pack")
        # A physical Git file the routes must never expose.
        write_private_file_atomic(
            home, f"{staged}/repository.git/objects/pack/pack-{key[:40]}.pack", b"PACK"
        )
        write_record_atomic(
            home,
            f"{staged}/store.yml",
            RepositoryStore(
                id=f"sha256:{key}",
                created_at=CREATED_AT,
                acquisition=StoreAcquisition(git_version="2.50.1", object_format="sha1"),
            ),
            REPOSITORY_STORE_CONTRACT_ID,
        )
        write_record_atomic(
            home,
            f"{staged}/state.yml",
            RepositoryStoreState(
                default_remote_ref="refs/remotes/origin/trunk" if with_revision else None,
                default_revision=FLASK_REVISION if with_revision else None,
                last_fetch_at=FETCHED_AT,
                last_operation=StoreOperation(kind="acquire", outcome="succeeded", at=FETCHED_AT),
            ),
            REPOSITORY_STORE_STATE_CONTRACT_ID,
        )
        with repository_store_lock(home, key) as store_lock:
            publish_entry(home, staged, store_directory(key), owner=store_lock)
        liveness.remove_lock_file()


def _stage_and_publish_source(home: Path, source: FixtureSource, *, opened: bool) -> None:
    entry = f"source-{source.id.removeprefix('sha256:')[:16]}"
    staged = staging_entry(entry)
    with staging_entry_lock(home, entry) as liveness:
        ensure_private_directory(home, staged)
        write_record_atomic(
            home,
            f"{staged}/source.yml",
            RepositorySource(
                id=source.id,
                slug=source.slug,
                display_url=source.address,
                clone_url=source.address,
                transport=source.transport,
                created_at=CREATED_AT,
            ),
            REPOSITORY_SOURCE_CONTRACT_ID,
        )
        if opened:
            write_record_atomic(
                home,
                f"{staged}/state.yml",
                RepositorySourceState(last_opened_at=OPENED_AT),
                REPOSITORY_SOURCE_STATE_CONTRACT_ID,
            )
        with source_alias_lock(home, source.slug) as alias_lock:
            publish_entry(home, staged, source_directory(source.slug), owner=alias_lock)
        liveness.remove_lock_file()


def _attach(home: Path, source: FixtureSource, key: str, *, generation: int, at: str) -> None:
    """Write the alias, the visibility commit, under the store lease and alias lock."""

    with store_lease(home, key), source_alias_lock(home, source.slug):
        write_record_atomic(
            home,
            source_record(source.slug, "store-alias.yml"),
            RepositoryStoreAlias(
                source_id=source.id,
                store_id=f"sha256:{key}",
                generation=generation,
                updated_at=at,
            ),
            REPOSITORY_STORE_ALIAS_CONTRACT_ID,
            replace=generation > 1,
        )


def build_empty_home(home: Path) -> None:
    """A home with its skeleton, layout, and config, and nothing cached."""

    ensure_home(home)
    migrate_layout(home, version=FIXTURE_VERSION)


def build_populated_home(home: Path) -> str:
    """Publish, alias, quarantine, and reclaim entries; return the quarantine entry name.

    - flask over HTTPS and over SSH are two sources aliasing one store; the SSH alias
      was repointed once, so it is at generation 2.
    - click's acquisition published its store and its source but not its alias, so the
      source is unattached and the store is unreferenced.
    - jinja's store failed revalidation and was quarantined with its alias.
    - werkzeug's unreferenced store was reclaimed, so nothing of it remains.
    - an interrupted acquisition left one staging entry for the next sweep.
    """

    build_empty_home(home)
    _stage_and_publish_store(home, FLASK_STORE_KEY, with_revision=True)
    _stage_and_publish_source(home, FLASK_HTTPS, opened=True)
    _attach(home, FLASK_HTTPS, FLASK_STORE_KEY, generation=1, at=ALIASED_AT)
    _stage_and_publish_source(home, FLASK_SSH, opened=False)
    _attach(home, FLASK_SSH, FLASK_STORE_KEY, generation=1, at=ALIASED_AT)
    _attach(home, FLASK_SSH, FLASK_STORE_KEY, generation=2, at=REPOINTED_AT)

    _stage_and_publish_store(home, ORPHAN_STORE_KEY, with_revision=False)
    _stage_and_publish_source(home, CLICK, opened=False)

    _stage_and_publish_store(home, QUARANTINED_STORE_KEY, with_revision=False)
    _stage_and_publish_source(home, JINJA, opened=False)
    _attach(home, JINJA, QUARANTINED_STORE_KEY, generation=1, at=ALIASED_AT)
    quarantined = quarantine_entries(
        home,
        source_slugs=[JINJA.slug],
        store_keys=[QUARANTINED_STORE_KEY],
        revalidate=lambda: False,
    )
    if quarantined.state != "quarantined" or quarantined.entry is None:
        raise RuntimeError(f"quarantine did not happen: {quarantined.state}")

    _stage_and_publish_store(home, RECLAIMED_STORE_KEY, with_revision=False)
    reclaimed = reclaim_store(home, RECLAIMED_STORE_KEY)
    if reclaimed is not StoreReclamation.RECLAIMED:
        raise RuntimeError(f"reclamation did not happen: {reclaimed}")

    ensure_private_directory(home, f"{staging_entry(LEFTOVER_STAGING_ENTRY)}/repository.git")
    return quarantined.entry


def build_future_home(home: Path) -> None:
    """A home whose layout a newer release wrote."""

    ensure_home(home)
    write_record_atomic(
        home,
        LAYOUT_RECORD,
        CacheLayout(format="f02", created_by="0.12.0"),
        CACHE_LAYOUT_CONTRACT_ID,
    )


def build_shared_home(home: Path) -> None:
    """A valid home whose own mode lets other users read it."""

    build_empty_home(home)
    os.chmod(home, 0o755)


def build_all(directory: Path) -> None:
    """Build every home the golden transcript reads, plus the directory it serves."""

    (directory / "root").mkdir(exist_ok=True)
    build_empty_home(directory / "empty")
    build_populated_home(directory / "populated")
    build_future_home(directory / "future")
    build_shared_home(directory / "shared")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: cache_home_fixture.py <directory>")
    build_all(Path(sys.argv[1]).resolve())
