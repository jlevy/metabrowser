"""Where ``metab TARGET --present`` opens a target: the ``open_in`` preference.

``auto``, the default, opens a target in the macOS app when an installed build takes it,
and otherwise in a browser, on a ``metab`` server started for it; ``app`` opens it in the
app or nowhere; ``browser`` never looks for the app. Bare ``metab PATH`` does not read the
preference: whether it should is an open question of the open-anything plan
(``docs/project/specs/active/plan-2026-11-17-open-anything-from-cli-and-app.md``).

**Where it is read.** The first of these that is set wins, and :class:`OpenInPreference`
names which one it was:

- ``--open-in``, on the command line (``flag``);
- :data:`OPEN_IN_ENV` (``environment``), where an empty value counts as unset;
- ``open_in`` in ``config.yml`` (``config``), the user-owned configuration in
  ``configuration_directory()``, where ``ApplicationConfig`` (``cache/records.py``)
  declares it as a known setting;
- otherwise :data:`DEFAULT_OPEN_IN` (``default``).

**Reading config.yml.** :func:`configured_open_in` reads that one setting, and not the
whole record through its contract as ``cache/layout.py`` ``read_config`` does: the
contract's schema library adds about 240 ms of imports, measured on 2026-11-18 on an
Apple silicon Mac, to a mode that answers about as fast as ``metab --version``
(``test_present_dry_run_loads_little_beyond_version`` in
``tests/test_plugin_public_api.py``). It reads the file within the same bound
(``CONFIG_MAX_BYTES``), through the same owner-only helper, and changes nothing on disk.
``tests/test_open_in.py`` holds the two readers to the same answer for the setting.
A ``config.yml`` this reader cannot read, or whose ``open_in`` is not one of
:data:`OPEN_IN_CHOICES`, is an error that names the file and the fix; the flag and the
environment are read first, so either one still chooses while the file is broken.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, cast

from metabrowser.errors import CLIError
from metabrowser.invisible_chars import display_segment

type opening = Literal["auto", "app", "browser"]
"""Where ``--present`` opens a target."""

type OpenInSource = Literal["flag", "environment", "config", "default"]
"""Where the preference in effect was read."""

OPEN_IN_CHOICES: Final[tuple[opening, ...]] = ("auto", "app", "browser")
DEFAULT_OPEN_IN: Final[opening] = "auto"
# Chooses as `--open-in` does, which overrides it, and overrides config.yml.
OPEN_IN_ENV: Final = "METABROWSER_OPEN_IN"
# The key in config.yml's `config` mapping.
OPEN_IN_SETTING: Final = "open_in"


class OpenInError(CLIError):
    """The preference cannot be read: a value that is not a choice, or a config.yml that
    cannot be read. ``str()`` names where it was read and the fix."""


@dataclass(frozen=True, slots=True)
class OpenInPreference:
    """The preference in effect and where it was read."""

    value: opening
    source: OpenInSource


def _choices() -> str:
    return ", ".join(OPEN_IN_CHOICES[:-1]) + f", or {OPEN_IN_CHOICES[-1]}"


def parse_open_in(value: object) -> opening | None:
    """*value* as a choice, or ``None`` when it is not one."""

    if isinstance(value, str) and value in OPEN_IN_CHOICES:
        return cast(opening, value)
    return None


def _shown(path: Path) -> str:
    return display_segment(os.fsencode(path))


def configured_open_in(directory: Path | None = None) -> opening | None:
    """The ``open_in`` that ``config.yml`` sets, or ``None`` when it sets none.

    *directory* is the configuration directory, ``configuration_directory()`` when
    ``None``. No directory, no file, and a file without the setting or with a null one
    are all ``None``. Raises :class:`OpenInError` when the file cannot be read, is not
    YAML with a ``config`` mapping, or sets a value that is not a choice.
    """

    # Imported here: only a preference that neither the flag nor the environment gives
    # reads the file, and the owner-only helpers are nothing else in `--present` needs.
    import yaml

    from metabrowser.cache.paths import CONFIG_MAX_BYTES, CONFIG_RECORD
    from metabrowser.home import (
        PrivateFileTooLargeError,
        PrivateStorageError,
        StorageDirectoryError,
        configuration_directory,
        read_private_file_bounded,
    )

    try:
        home = directory if directory is not None else configuration_directory()
    except StorageDirectoryError as exc:
        raise OpenInError(f"{exc} Or choose with --open-in or {OPEN_IN_ENV}.") from exc
    path = home / CONFIG_RECORD
    fix = (
        f"fix {OPEN_IN_SETTING} there, or choose with --open-in or {OPEN_IN_ENV}, "
        "which are read first"
    )
    try:
        payload = read_private_file_bounded(
            home, CONFIG_RECORD, max_bytes=CONFIG_MAX_BYTES, shared="keep"
        )
    except FileNotFoundError:
        return None
    except PrivateFileTooLargeError as exc:
        raise OpenInError(
            f"{_shown(path)} is larger than {CONFIG_MAX_BYTES} bytes, so it is not read; {fix}"
        ) from exc
    except PrivateStorageError as exc:
        raise OpenInError(f"{exc} Or choose with --open-in or {OPEN_IN_ENV}.") from exc
    except OSError as exc:
        why = exc.strerror or "it cannot be read"
        raise OpenInError(f"{_shown(path)} cannot be read ({why}); {fix}") from exc
    try:
        document: object = yaml.load(payload, Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader))
    except Exception as exc:
        # PyYAML raises its YAMLError for text it cannot parse, and RecursionError, among
        # others, for a document nested past the interpreter's limit: each one means
        # this file holds no setting to read.
        raise OpenInError(f"{_shown(path)} is not YAML; {fix}") from exc
    values = (
        cast(dict[object, object], document).get("config") if isinstance(document, dict) else None
    )
    if not isinstance(values, dict):
        raise OpenInError(f"{_shown(path)} has no config mapping; {fix}")
    setting = cast(dict[object, object], values).get(OPEN_IN_SETTING)
    if setting is None:
        return None
    chosen = parse_open_in(setting)
    if chosen is None:
        raise OpenInError(f"{OPEN_IN_SETTING} in {_shown(path)} is not {_choices()}; {fix}")
    return chosen


def resolve_open_in(
    flag: str | None, *, environ: Mapping[str, str] | None = None, directory: Path | None = None
) -> OpenInPreference:
    """The preference in effect: *flag*, then :data:`OPEN_IN_ENV`, then ``config.yml``.

    *flag* is ``--open-in`` as its callback checked it, or ``None`` when it was not
    given. Raises :class:`OpenInError` for an environment value that is not a choice and
    for what :func:`configured_open_in` raises.
    """

    if flag is not None:
        chosen = parse_open_in(flag)
        if chosen is None:
            raise OpenInError(f"--open-in {flag!r} is not {_choices()}")
        return OpenInPreference(chosen, "flag")
    variables = os.environ if environ is None else environ
    named = variables.get(OPEN_IN_ENV, "")
    if named:
        chosen = parse_open_in(named)
        if chosen is None:
            raise OpenInError(f"{OPEN_IN_ENV} is not {_choices()}; set it to one, or unset it")
        return OpenInPreference(chosen, "environment")
    configured = configured_open_in(directory)
    if configured is not None:
        return OpenInPreference(configured, "config")
    return OpenInPreference(DEFAULT_OPEN_IN, "default")


__all__ = [
    "DEFAULT_OPEN_IN",
    "OPEN_IN_CHOICES",
    "OPEN_IN_ENV",
    "OPEN_IN_SETTING",
    "opening",
    "OpenInError",
    "OpenInPreference",
    "OpenInSource",
    "configured_open_in",
    "parse_open_in",
    "resolve_open_in",
]
