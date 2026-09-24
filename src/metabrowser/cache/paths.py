"""Logical paths of the ``f01`` layout, relative to the application home.

Every cache module and the read routes spell layout locations through these names, so a
physical spelling changes in one place. Callers pass only validated slugs, store keys,
and entry names; the helpers refuse anything else rather than build a path from it.
"""

from __future__ import annotations

from typing import Final, Literal

from metabrowser.cache.identity import is_slug, is_store_key
from metabrowser.cache.locks import is_entry_name

CONFIG_RECORD: Final = "config.yml"
CACHE_ROOT: Final = "cache"
LAYOUT_RECORD: Final = "cache/layout.yml"
STAGING: Final = "cache/staging"
SOURCES: Final = "cache/sources"
REPOSITORY_STORES: Final = "cache/repository-stores"
PROVIDER_BINDINGS: Final = "cache/provider-bindings"
PROVIDER_REPOSITORIES: Final = "cache/provider-repositories"
STAGING_LOCKS: Final = "cache/locks/staging"
# The GitHub URL grammar's ``^[1-9][0-9]{0,9}$``.
MAX_PULL_REQUEST_NUMBER: Final = 9_999_999_999

type SourceRecordName = Literal["source.yml", "state.yml", "store-alias.yml"]
type StoreRecordName = Literal["store.yml", "state.yml"]


def source_directory(slug: str) -> str:
    """Return ``cache/sources/<slug>``."""

    if not is_slug(slug):
        raise ValueError("invalid source slug")
    return f"{SOURCES}/{slug}"


def source_record(slug: str, name: SourceRecordName) -> str:
    """Return the path of one record of a source."""

    return f"{source_directory(slug)}/{name}"


def source_pulls_directory(slug: str) -> str:
    """Return ``cache/sources/<slug>/pulls``, where a provider keeps pull-request records."""

    return f"{source_directory(slug)}/pulls"


def source_pull_record(slug: str, number: int) -> str:
    """Return ``cache/sources/<slug>/pulls/<n>.json`` for a positive pull-request number."""

    if isinstance(number, bool) or not 1 <= number <= MAX_PULL_REQUEST_NUMBER:
        raise ValueError("invalid pull-request number")
    return f"{source_pulls_directory(slug)}/{number}.json"


def source_pull_refresh(slug: str, number: int) -> str:
    """Return ``cache/sources/<slug>/pulls/<n>.refresh.json``: how its last refresh ended."""

    return source_pull_record(slug, number).removesuffix(".json") + ".refresh.json"


def store_directory(store_key: str) -> str:
    """Return ``cache/repository-stores/<store-key>``."""

    if not is_store_key(store_key):
        raise ValueError("invalid store key")
    return f"{REPOSITORY_STORES}/{store_key}"


def store_record(store_key: str, name: StoreRecordName) -> str:
    """Return the path of one record of a repository store."""

    return f"{store_directory(store_key)}/{name}"


def staging_entry(entry: str) -> str:
    """Return ``cache/staging/<entry>``."""

    if not is_entry_name(entry):
        raise ValueError("invalid staging entry name")
    return f"{STAGING}/{entry}"


__all__ = [
    "CACHE_ROOT",
    "CONFIG_RECORD",
    "LAYOUT_RECORD",
    "MAX_PULL_REQUEST_NUMBER",
    "PROVIDER_BINDINGS",
    "PROVIDER_REPOSITORIES",
    "REPOSITORY_STORES",
    "SOURCES",
    "STAGING",
    "STAGING_LOCKS",
    "source_directory",
    "source_pull_record",
    "source_pull_refresh",
    "source_pulls_directory",
    "source_record",
    "staging_entry",
    "store_directory",
    "store_record",
]
