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
CACHE_ROOT: Final = "."
LAYOUT_RECORD: Final = "layout.yml"
STAGING: Final = "staging"
SOURCES: Final = "sources"
REPOSITORY_STORES: Final = "repository-stores"
STAGING_LOCKS: Final = "locks/staging"
# The GitHub URL grammar's ``^[1-9][0-9]{0,9}$``.
MAX_PULL_REQUEST_NUMBER: Final = 9_999_999_999
# The catalog filters a provider exposes: GitHub's open, closed, or all pull requests.
type PullListName = Literal["all", "open", "closed"]
PULL_LIST_NAMES: Final[tuple[PullListName, ...]] = ("all", "open", "closed")

type SourceRecordName = Literal["source.yml", "state.yml", "store-alias.yml"]
type StoreRecordName = Literal["store.yml", "state.yml"]


def source_directory(slug: str) -> str:
    """Return ``sources/<slug>``."""

    if not is_slug(slug):
        raise ValueError("invalid source slug")
    return f"{SOURCES}/{slug}"


def source_record(slug: str, name: SourceRecordName) -> str:
    """Return the path of one record of a source."""

    return f"{source_directory(slug)}/{name}"


def source_pulls_directory(slug: str) -> str:
    """Return ``sources/<slug>/pulls``, where a provider keeps pull-request records."""

    return f"{source_directory(slug)}/pulls"


def source_stacks(slug: str) -> str:
    """Return the GitHub plugin's optional native stack snapshot."""

    return f"{source_pulls_directory(slug)}/stacks.json"


def source_pull_record(slug: str, number: int) -> str:
    """Return ``sources/<slug>/pulls/<n>.json`` for a positive pull-request number."""

    if isinstance(number, bool) or not 1 <= number <= MAX_PULL_REQUEST_NUMBER:
        raise ValueError("invalid pull-request number")
    return f"{source_pulls_directory(slug)}/{number}.json"


def source_pull_refresh(slug: str, number: int) -> str:
    """Return ``sources/<slug>/pulls/<n>.refresh.json``: how its last refresh ended."""

    return source_pull_record(slug, number).removesuffix(".json") + ".refresh.json"


def source_pull_list_refresh(slug: str, name: PullListName) -> str:
    """Return ``sources/<slug>/pulls/list-<name>.refresh.json``: its refresh outcome."""

    if name not in PULL_LIST_NAMES:
        raise ValueError("invalid pull-request list")
    return f"{source_pulls_directory(slug)}/list-{name}.refresh.json"


def source_pull_timeline(slug: str, number: int) -> str:
    """Return the bounded Conversation projection beside the pull request record."""

    return source_pull_record(slug, number).removesuffix(".json") + ".timeline.json"


def source_pull_files(slug: str, number: int) -> str:
    """Return ``sources/<slug>/pulls/<n>.files.json``: the pull request's changed files."""

    return source_pull_record(slug, number).removesuffix(".json") + ".files.json"


def source_pull_files_refresh(slug: str, number: int) -> str:
    """Return ``sources/<slug>/pulls/<n>.files.refresh.json``: how that list's refresh ended."""

    return source_pull_record(slug, number).removesuffix(".json") + ".files.refresh.json"


def store_directory(store_key: str) -> str:
    """Return ``repository-stores/<store-key>``."""

    if not is_store_key(store_key):
        raise ValueError("invalid store key")
    return f"{REPOSITORY_STORES}/{store_key}"


def store_record(store_key: str, name: StoreRecordName) -> str:
    """Return the path of one record of a repository store."""

    return f"{store_directory(store_key)}/{name}"


def staging_entry(entry: str) -> str:
    """Return ``staging/<entry>``."""

    if not is_entry_name(entry):
        raise ValueError("invalid staging entry name")
    return f"{STAGING}/{entry}"


__all__ = [
    "CACHE_ROOT",
    "CONFIG_RECORD",
    "LAYOUT_RECORD",
    "MAX_PULL_REQUEST_NUMBER",
    "PULL_LIST_NAMES",
    "PullListName",
    "REPOSITORY_STORES",
    "SOURCES",
    "STAGING",
    "STAGING_LOCKS",
    "source_directory",
    "source_pull_files",
    "source_pull_files_refresh",
    "source_pull_list_refresh",
    "source_pull_record",
    "source_pull_refresh",
    "source_pull_timeline",
    "source_pulls_directory",
    "source_record",
    "source_stacks",
    "staging_entry",
    "store_directory",
    "store_record",
]
