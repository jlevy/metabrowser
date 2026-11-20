"""The ``f03`` home format: its record, history, migrations, and future-format refusal.

``layout.yml`` names the directory semantics of the whole application home. This
module owns the current format, the ordered history of formats a release has written,
the migration from each historical format to the next, and the error an older client
raises when it meets a newer home. Migration holds the application-home lock, refuses a
future format before writing anything, publishes the layout after each step so an
interrupted chain resumes where it stopped.

``config.yml`` belongs to the user and lives in the independent configuration directory.
It is created once if absent and is never rewritten when the cache changes. Existing
settings and comments are preserved. Unreadable configuration is refused, never replaced.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any, Final, Literal, cast

from frontmatter_format import new_yaml
from softschema.validate import parse_yaml_text

import metabrowser
from metabrowser.cache.atomic import (
    RecordError,
    parse_record,
    read_bytes_bounded,
    write_record_atomic,
)
from metabrowser.cache.contracts import parse_application_config
from metabrowser.cache.listing import ListingLimitError, list_private_directory
from metabrowser.cache.locks import application_cache_lock
from metabrowser.cache.paths import (
    CONFIG_MAX_BYTES,
    CONFIG_RECORD,
    LAYOUT_RECORD,
    REPOSITORY_STORES,
    SOURCES,
)
from metabrowser.cache.probe import ProbeReport, probe_application_cache
from metabrowser.cache.reclaim import SweepReport, sweep_staging
from metabrowser.cache.records import (
    CACHE_LAYOUT_CONTRACT_ID,
    CONFIG_CONTRACT_ID,
    LAYOUT_FORMAT_PATTERN,
    ApplicationConfig,
    CacheLayout,
)
from metabrowser.cache.store_rename import LEGACY_REPOSITORY_STORES, rename_legacy_names
from metabrowser.home import (
    SharedEntryPolicy,
    application_cache,
    configuration_directory,
    ensure_home,
    ensure_storage_root,
    validate_storage_separation,
    write_private_file_atomic,
)

LAYOUT_FORMAT: Final = "f03"
CONFIG_FORMAT: Final = "f01"
CONFIG_FORMAT_HISTORY: Final[tuple[str, ...]] = (CONFIG_FORMAT,)
# Every format a released Metabrowser has written, oldest first, ending with the current
# one. Adding a format appends it here and adds the migration from its predecessor.
# ``f02`` names each repository store by a readable key where ``f01`` spelled the whole
# digest of its identity, and ``f03`` shortens that key, and a source's slug, to single-dash
# words and a base-36 suffix where ``f02`` joined them with ``--`` and spelled the suffix
# in hexadecimal, and moves the stores from ``repository-stores`` to ``repos``
# (``store_rename``).
FORMAT_HISTORY: Final[tuple[str, ...]] = ("f01", "f02", "f03")

type Migration = Callable[[Path], None]
# The migration from each historical format to the next one in FORMAT_HISTORY.
#
# One function does both renames, because an entry named as ``f01`` or as ``f02`` is renamed
# straight to its ``f03`` name. The step from ``f02`` of a home that was ``f01`` finds
# nothing left to rename.
MIGRATIONS: Final[Mapping[str, Migration]] = {
    "f01": rename_legacy_names,
    "f02": rename_legacy_names,
}

_CONFIG_METADATA: Final = {
    "contract": CONFIG_CONTRACT_ID,
    "envelope": "config",
    "status": "permissive",
}


class FutureLayoutFormatError(Exception):
    """Cache or configuration uses a format newer than this release reads."""

    def __init__(
        self, found: str, supported: str, *, storage: Literal["cache", "configuration"] = "cache"
    ) -> None:
        override = (
            "METABROWSER_CONFIG_DIR" if storage == "configuration" else "METABROWSER_CACHE_DIR"
        )
        super().__init__(
            f"This Metabrowser {storage} directory uses format {found}, and this release reads "
            f"formats up to {supported}. Upgrade Metabrowser, or set {override} to a "
            "different directory."
        )
        self.found: str = found
        self.supported: str = supported


class LayoutError(Exception):
    """The layout or config cannot be read or adopted; nothing was changed.

    ``str()`` names no path; ``path`` is for local logs.
    """

    def __init__(self, message: str, path: Path) -> None:
        super().__init__(message)
        self.path: Path = path


class ConfigurationError(LayoutError):
    """Configuration cannot be read; the CLI can name its path and recovery step."""


class ConfigurationIOError(LayoutError):
    """Reading or creating configuration failed at the filesystem boundary."""

    def __init__(self, error: OSError, path: Path, *, operation: Literal["read", "create"]) -> None:
        reason = os.strerror(error.errno) if error.errno is not None else "filesystem error"
        super().__init__(reason, path)
        self.operation: Literal["read", "create"] = operation


@dataclass(frozen=True, slots=True)
class LayoutOutcome:
    """What :func:`migrate_layout` found and published."""

    layout: CacheLayout
    config: ApplicationConfig
    previous_format: str | None
    migrated_through: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CacheHome:
    """An application home verified, migrated, and swept for use."""

    home: Path
    layout: CacheLayout
    config: ApplicationConfig
    probe: ProbeReport
    sweep: SweepReport


def format_number(value: str) -> int:
    """Return the ordinal of a format spelling such as ``f01``."""

    if re.fullmatch(LAYOUT_FORMAT_PATTERN, value) is None:
        raise ValueError(f"not a layout format: {value!r}")
    return int(value[1:])


def _refuse_future(
    found: object, history: Sequence[str], *, storage: Literal["cache", "configuration"] = "cache"
) -> None:
    if not isinstance(found, str):
        return
    try:
        number = format_number(found)
    except ValueError:
        return
    if number > format_number(history[-1]):
        raise FutureLayoutFormatError(found, history[-1], storage=storage)


def _parse_yaml(payload: bytes, path: Path, what: str) -> dict[str, Any]:
    try:
        document = parse_yaml_text(payload.decode("utf-8").removeprefix("\ufeff"))
    except (UnicodeDecodeError, ValueError) as error:
        raise LayoutError(f"{what} is not portable YAML", path) from error
    if not isinstance(document, dict):
        raise LayoutError(f"{what} is not a YAML mapping", path)
    return cast(dict[str, Any], document)


def read_layout(
    home: Path,
    *,
    history: Sequence[str] = FORMAT_HISTORY,
    shared: SharedEntryPolicy = "repair",
) -> CacheLayout | None:
    """Read ``layout.yml``; ``None`` when the home has none yet.

    A format newer than *history* raises :class:`FutureLayoutFormatError` before the
    record is held to this release's contract, so a newer layout is never reported as
    damage. *shared* follows :func:`~metabrowser.cache.atomic.read_bytes_bounded`, so a
    read route can refuse a shared record instead of repairing it.
    """

    path = home / LAYOUT_RECORD
    try:
        payload = read_bytes_bounded(home, LAYOUT_RECORD, shared=shared)
    except FileNotFoundError:
        return None
    except RecordError as error:
        raise LayoutError(str(error), path) from error
    document = _parse_yaml(payload, path, "layout.yml")
    envelope = document.get("layout")
    if isinstance(envelope, dict):
        _refuse_future(cast(dict[str, object], envelope).get("format"), history)
    try:
        layout = parse_record(payload, CACHE_LAYOUT_CONTRACT_ID, path)
    except RecordError as error:
        raise LayoutError(str(error), path) from error
    assert isinstance(layout, CacheLayout)
    return layout


def read_config(
    home: Path,
    *,
    history: Sequence[str] = CONFIG_FORMAT_HISTORY,
    shared: SharedEntryPolicy = "repair",
) -> ApplicationConfig | None:
    """Read ``config.yml``; ``None`` when there is none.

    Keep validation and I/O failures distinct so a CLI can suggest a reset only for
    malformed data. A future format keeps its upgrade guidance. *shared* follows
    :func:`read_layout`.
    """

    path = home / CONFIG_RECORD
    try:
        payload = read_bytes_bounded(home, CONFIG_RECORD, max_bytes=CONFIG_MAX_BYTES, shared=shared)
    except FileNotFoundError:
        return None
    except RecordError as error:
        raise ConfigurationError(str(error), path) from error
    except OSError as error:
        raise ConfigurationIOError(error, path, operation="read") from error
    try:
        document = _parse_yaml(payload, path, "config.yml")
    except LayoutError as error:
        raise ConfigurationError(str(error), path) from error
    values = document.get("config")
    if isinstance(values, dict):
        _refuse_future(
            cast(dict[str, object], values).get("format"), history, storage="configuration"
        )
    if set(document) != {"softschema", "config"}:
        raise ConfigurationError(
            "config.yml must contain only its softschema header and a config mapping",
            path,
        )
    if document["softschema"] != _CONFIG_METADATA:
        raise ConfigurationError(
            f"config.yml must declare contract {CONFIG_CONTRACT_ID}, envelope config, and "
            "status permissive, and must not name a schema",
            path,
        )
    if not isinstance(values, dict):
        raise ConfigurationError("config.yml config must be a mapping", path)
    try:
        return parse_application_config(values)
    except ValueError as error:
        raise ConfigurationError(str(error), path) from error


def serialize_config(config: ApplicationConfig) -> bytes:
    """Serialize config with its header and every setting it carries."""

    document = {"softschema": dict(_CONFIG_METADATA), "config": config.model_dump(mode="json")}
    parse_application_config(document["config"])
    stream = StringIO()
    writer = new_yaml(typ="safe", allow_aliases=False, suppress_vals=None)
    # Keep the header first and the user's settings in the order they wrote them.
    writer.representer.sort_base_mapping_type_on_output = False  # pyright: ignore[reportAttributeAccessIssue]
    writer.dump(document, stream)
    text = stream.getvalue()
    if parse_yaml_text(text) != document:
        raise ValueError("config.yml holds values that do not survive portable YAML")
    return text.encode()


def ensure_configuration(*, version: str) -> ApplicationConfig:
    """Create missing configuration once, independently of the cache layout.

    Atomic create-only publication preserves user edits and handles concurrent cache
    initializations without a shared lock or rewriting an existing configuration.
    """
    directory = configuration_directory()
    config = read_config(directory)
    if config is not None:
        return config
    path = directory / CONFIG_RECORD
    try:
        ensure_storage_root(directory)
    except OSError as error:
        raise ConfigurationIOError(error, path, operation="create") from error
    config = ApplicationConfig(format=CONFIG_FORMAT, written_by=version, upgrades=[])
    payload = serialize_config(config)
    try:
        write_private_file_atomic(directory, CONFIG_RECORD, payload, replace=False)
    except FileExistsError as error:
        existing = read_config(directory)
        if existing is None:
            raise LayoutError(
                "configuration disappeared during initialization", directory / CONFIG_RECORD
            ) from error
        return existing
    except OSError as error:
        raise ConfigurationIOError(error, path, operation="create") from error
    return config


def _has_durable_entries(home: Path) -> bool:
    """Whether the cache holds data a layout would have to describe.

    Staging is disposable in every format, so a crash that left it behind before the
    first layout was published does not block creating it. Each directory is
    listed through the verified, no-follow path the read routes use, so a link where one
    of them belongs is refused with a typed, path-free
    :class:`~metabrowser.home.PrivateStorageError` instead of being followed out of the
    home. ``keep`` leaves an over-shared directory to the repairing writes that follow.
    """

    # A home whose stores are still in the directory ``f01`` and ``f02`` named has data too.
    for directory in (SOURCES, REPOSITORY_STORES, LEGACY_REPOSITORY_STORES):
        try:
            if list_private_directory(home, directory, max_entries=0, shared="keep"):
                return True
        except FileNotFoundError:
            continue
        except ListingLimitError:
            return True
    return False


def _refuse_unrecognized_entries(home: Path) -> None:
    if _has_durable_entries(home):
        raise LayoutError(
            "the cache has entries but no layout.yml, so their format is "
            "unknown. Move the cache directory aside, or set METABROWSER_CACHE_DIR to a "
            "different directory",
            home / LAYOUT_RECORD,
        )


def preflight_layout(home: Path, *, history: Sequence[str] = FORMAT_HISTORY) -> None:
    """Refuse unknown data before locks, skeleton creation, probes, or mode repairs.

    ``keep`` leaves a merely over-shared home to the ordinary repairing path, but a
    record this process cannot read at all — a link, a second hard link, or permissions
    that deny its owner — raises :class:`~metabrowser.home.PrivateStorageError` here.
    That record is what would have said whether the home may be adopted, so answering
    with it is the whole point of reading before anything is created or repaired.
    """

    validate_storage_separation(home)
    layout = read_layout(home, history=history, shared="keep")
    read_config(configuration_directory(), shared="keep")
    if layout is None:
        _refuse_unrecognized_entries(home)
    elif layout.format not in history:
        raise LayoutError(
            f"layout.yml names format {layout.format}, which no Metabrowser release wrote",
            home / LAYOUT_RECORD,
        )


def migrate_layout(
    home: Path,
    *,
    version: str | None = None,
    history: Sequence[str] = FORMAT_HISTORY,
    migrations: Mapping[str, Migration] = MIGRATIONS,
) -> LayoutOutcome:
    """Bring the home to the current format under the application-home lock.

    Configuration is initialized independently in the configuration directory and is
    never rewritten by cache migration. A new cache receives ``layout.yml``; an older
    cache runs each migration in *history* order. A future layout or config raises
    :class:`FutureLayoutFormatError` before anything is written; a home with cache
    entries but no layout raises :class:`LayoutError` rather than adopting them.
    """

    version = metabrowser.__version__ if version is None else version
    current = history[-1]
    preflight_layout(home, history=history)
    config = ensure_configuration(version=version)
    with application_cache_lock(home):
        layout = read_layout(home, history=history)
        if layout is None:
            _refuse_unrecognized_entries(home)
            layout = CacheLayout(format=current, created_by=version)
            write_record_atomic(
                home, LAYOUT_RECORD, layout, CACHE_LAYOUT_CONTRACT_ID, replace=False
            )
            return LayoutOutcome(layout, config, None, ())
        previous = layout.format
        if previous not in history:
            raise LayoutError(
                f"layout.yml names format {previous}, which no Metabrowser release wrote",
                home / LAYOUT_RECORD,
            )
        migrated: list[str] = []
        start = history.index(previous)
        for source, target in zip(history[start:], history[start + 1 :], strict=False):
            migration = migrations.get(source)
            if migration is None:
                raise RuntimeError(f"no migration from layout format {source} to {target}")
            migration(home)
            layout = CacheLayout(format=target, created_by=layout.created_by)
            write_record_atomic(home, LAYOUT_RECORD, layout, CACHE_LAYOUT_CONTRACT_ID)
            migrated.append(target)
        return LayoutOutcome(layout, config, previous, tuple(migrated))


def open_cache(home: Path | None = None, *, version: str | None = None) -> CacheHome:
    """Prepare the application home for cache use.

    Resolves the home when none is given, creates or verifies its owner-only skeleton and
    ``CACHEDIR.TAG``, probes its locks and publication, migrates its layout, and runs the
    startup sweep of ``staging/``. It never deletes a published store.
    Ordinary local browsing never calls this. Read routes do not.
    """

    home = application_cache() if home is None else home
    preflight_layout(home, history=FORMAT_HISTORY)
    ensure_storage_root(home)
    ensure_home(home)
    probe = probe_application_cache(home)
    outcome = migrate_layout(home, version=version)
    sweep = sweep_staging(home)
    return CacheHome(home, outcome.layout, outcome.config, probe, sweep)


__all__ = [
    "FORMAT_HISTORY",
    "LAYOUT_FORMAT",
    "LAYOUT_FORMAT_PATTERN",
    "MIGRATIONS",
    "CacheHome",
    "ConfigurationError",
    "ConfigurationIOError",
    "FutureLayoutFormatError",
    "LayoutError",
    "LayoutOutcome",
    "Migration",
    "format_number",
    "migrate_layout",
    "open_cache",
    "preflight_layout",
    "read_config",
    "read_layout",
    "serialize_config",
]
