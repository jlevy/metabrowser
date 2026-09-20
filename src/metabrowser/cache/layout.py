"""The ``f01`` home format: its record, history, migrations, and future-format refusal.

``cache/layout.yml`` names the directory semantics of the whole application home. This
module owns the current format, the ordered history of formats a release has written,
the migration from each historical format to the next, and the error an older client
raises when it meets a newer home. Migration holds the application-home lock, refuses a
future format before writing anything, publishes the layout after each step so an
interrupted chain resumes where it stopped, and publishes ``config.yml`` last, so a
layout ahead of its config always means an unfinished migration.

``config.yml`` belongs to the user. It is rewritten only when a home is created or
migrated, keeping every setting Metabrowser does not know; comments are not preserved.
A config Metabrowser cannot read is refused and left as it is, never replaced.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from typing import Any, Final, cast

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
from metabrowser.cache.locks import application_home_lock
from metabrowser.cache.paths import (
    CONFIG_RECORD,
    LAYOUT_RECORD,
    PROVIDER_BINDINGS,
    PROVIDER_REPOSITORIES,
    QUARANTINE,
    REPOSITORY_STORES,
    SOURCES,
)
from metabrowser.cache.probe import ProbeReport, probe_application_home
from metabrowser.cache.reclaim import SweepReport, sweep_staging_and_trash
from metabrowser.cache.records import (
    CACHE_LAYOUT_CONTRACT_ID,
    CONFIG_CONTRACT_ID,
    LAYOUT_FORMAT_PATTERN,
    ApplicationConfig,
    CacheLayout,
)
from metabrowser.home import (
    SharedEntryPolicy,
    application_home,
    ensure_home,
    write_private_file_atomic,
)

LAYOUT_FORMAT: Final = "f01"
# Every format a released Metabrowser has written, oldest first, ending with the current
# one. Adding a format appends it here and adds the migration from its predecessor.
FORMAT_HISTORY: Final[tuple[str, ...]] = ("f01",)

type Migration = Callable[[Path], None]
# The migration from each historical format to the next one in FORMAT_HISTORY.
MIGRATIONS: Final[Mapping[str, Migration]] = {}

_MAX_CONFIG_BYTES: Final = 256 * 1024
_CONFIG_METADATA: Final = {
    "contract": CONFIG_CONTRACT_ID,
    "envelope": "config",
    "status": "permissive",
}


class FutureLayoutFormatError(Exception):
    """The application home was written in a format newer than this release reads."""

    def __init__(self, found: str, supported: str) -> None:
        super().__init__(
            f"This Metabrowser application home uses format {found}, and this release reads "
            f"formats up to {supported}. Upgrade Metabrowser, or set METABROWSER_HOME to a "
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


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _refuse_future(found: object, history: Sequence[str]) -> None:
    if not isinstance(found, str):
        return
    try:
        number = format_number(found)
    except ValueError:
        return
    if number > format_number(history[-1]):
        raise FutureLayoutFormatError(found, history[-1])


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
    """Read ``cache/layout.yml``; ``None`` when the home has none yet.

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
    document = _parse_yaml(payload, path, "cache/layout.yml")
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
    history: Sequence[str] = FORMAT_HISTORY,
    shared: SharedEntryPolicy = "repair",
) -> ApplicationConfig | None:
    """Read ``config.yml``; ``None`` when there is none.

    Known fields validate, unknown settings are kept, and a future format raises
    :class:`FutureLayoutFormatError`. *shared* follows :func:`read_layout`.
    """

    path = home / CONFIG_RECORD
    try:
        payload = read_bytes_bounded(
            home, CONFIG_RECORD, max_bytes=_MAX_CONFIG_BYTES, shared=shared
        )
    except FileNotFoundError:
        return None
    except RecordError as error:
        raise LayoutError(str(error), path) from error
    document = _parse_yaml(payload, path, "config.yml")
    if set(document) != {"softschema", "config"}:
        raise LayoutError(
            "config.yml must contain only its softschema header and a config mapping",
            path,
        )
    if document["softschema"] != _CONFIG_METADATA:
        raise LayoutError(
            f"config.yml must declare contract {CONFIG_CONTRACT_ID}, envelope config, and "
            "status permissive, and must not name a schema",
            path,
        )
    values = document["config"]
    if not isinstance(values, dict):
        raise LayoutError("config.yml config must be a mapping", path)
    _refuse_future(cast(dict[str, object], values).get("format"), history)
    try:
        return parse_application_config(values)
    except ValueError as error:
        raise LayoutError(str(error), path) from error


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


def _write_config(home: Path, config: ApplicationConfig) -> None:
    write_private_file_atomic(home, CONFIG_RECORD, serialize_config(config))


def _has_durable_entries(home: Path) -> bool:
    """Whether the cache holds data a layout would have to describe.

    Staging and trash are disposable in every format, so a crash that left them behind
    before the first layout was published does not block creating it.
    """

    for directory in (
        SOURCES,
        REPOSITORY_STORES,
        QUARANTINE,
        PROVIDER_BINDINGS,
        PROVIDER_REPOSITORIES,
    ):
        try:
            with os.scandir(home / directory) as entries:
                if next(entries, None) is not None:
                    return True
        except FileNotFoundError:
            continue
    return False


def _refuse_unrecognized_entries(home: Path) -> None:
    if _has_durable_entries(home):
        raise LayoutError(
            "the cache has entries but no cache/layout.yml, so their format is "
            "unknown. Move the cache directory aside, or set METABROWSER_HOME to a "
            "different directory",
            home / LAYOUT_RECORD,
        )


def _preflight_layout(home: Path, *, history: Sequence[str]) -> None:
    """Refuse unknown data before locks, skeleton creation, probes, or mode repairs.

    ``keep`` leaves a merely over-shared home to the ordinary repairing path, but a
    record this process cannot read at all — a link, a second hard link, or permissions
    that deny its owner — raises :class:`~metabrowser.home.PrivateStorageError` here.
    That record is what would have said whether the home may be adopted, so answering
    with it is the whole point of reading before anything is created or repaired.
    """

    layout = read_layout(home, history=history, shared="keep")
    read_config(home, history=history, shared="keep")
    if layout is None:
        _refuse_unrecognized_entries(home)


def _config_for(
    config: ApplicationConfig | None, fmt: str, *, version: str, upgraded_at: str | None
) -> ApplicationConfig:
    if config is None:
        return ApplicationConfig(format=fmt, written_by=version, upgrades=[])
    values = config.model_dump(mode="json")
    values["format"] = fmt
    if upgraded_at is not None:
        values["written_by"] = version
        values["upgrades"] = [*values["upgrades"], {"version": version, "at": upgraded_at}]
    return parse_application_config(values)


def migrate_layout(
    home: Path,
    *,
    version: str | None = None,
    history: Sequence[str] = FORMAT_HISTORY,
    migrations: Mapping[str, Migration] = MIGRATIONS,
    now: Callable[[], str] = _utc_now,
) -> LayoutOutcome:
    """Bring the home to the current format under the application-home lock.

    A new home receives ``layout.yml`` and then ``config.yml``. An older home runs each
    migration in *history* order, publishing the layout after each step, and then
    ``config.yml`` with an upgrade entry. A current home whose config lags its layout
    only publishes the config. A future layout or config raises
    :class:`FutureLayoutFormatError` before anything is written; a home with cache
    entries but no layout raises :class:`LayoutError` rather than adopting them.
    """

    version = metabrowser.__version__ if version is None else version
    current = history[-1]
    _preflight_layout(home, history=history)
    with application_home_lock(home):
        layout = read_layout(home, history=history)
        config = read_config(home, history=history)
        if layout is None:
            _refuse_unrecognized_entries(home)
            layout = CacheLayout(format=current, created_by=version)
            write_record_atomic(
                home, LAYOUT_RECORD, layout, CACHE_LAYOUT_CONTRACT_ID, replace=False
            )
            config = _config_for(config, current, version=version, upgraded_at=None)
            _write_config(home, config)
            return LayoutOutcome(layout, config, None, ())
        previous = layout.format
        if previous not in history:
            raise LayoutError(
                f"cache/layout.yml names format {previous}, which no Metabrowser release wrote",
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
        if config is not None and config.format == current and not migrated:
            return LayoutOutcome(layout, config, previous, ())
        upgraded = bool(migrated) or (config is not None and config.format != current)
        config = _config_for(
            config, current, version=version, upgraded_at=now() if upgraded else None
        )
        _write_config(home, config)
        return LayoutOutcome(layout, config, previous, tuple(migrated))


def open_cache(home: Path | None = None, *, version: str | None = None) -> CacheHome:
    """Prepare the application home for cache use.

    Resolves the home when none is given, creates or verifies its owner-only skeleton and
    ``CACHEDIR.TAG``, probes its locks and publication, migrates its layout, and runs the
    startup sweep of ``staging/`` and ``trash/``. Ordinary local browsing never calls
    this.
    """

    home = application_home() if home is None else home
    _preflight_layout(home, history=FORMAT_HISTORY)
    ensure_home(home)
    probe = probe_application_home(home)
    outcome = migrate_layout(home, version=version)
    sweep = sweep_staging_and_trash(home)
    return CacheHome(home, outcome.layout, outcome.config, probe, sweep)


__all__ = [
    "FORMAT_HISTORY",
    "LAYOUT_FORMAT",
    "LAYOUT_FORMAT_PATTERN",
    "MIGRATIONS",
    "CacheHome",
    "FutureLayoutFormatError",
    "LayoutError",
    "LayoutOutcome",
    "Migration",
    "format_number",
    "migrate_layout",
    "open_cache",
    "read_config",
    "read_layout",
    "serialize_config",
]
