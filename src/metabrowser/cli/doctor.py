"""The checks of ``metab --doctor``: the plugins, ``open_in``, this ``metab``, Git, the
two directories, and the event log.

``doctor_plugins`` (:mod:`metabrowser.cli.plugins`) validates the plugins, reports where
``--present`` opens a target (``open_in``) and GitHub CLI's sign-in (``github``), and
builds the checks here with :func:`doctor_checks`. Each check reads what is there and
changes nothing.

=============  ==================================================================  =========
``id``         What it checks                                                      Worst
=============  ==================================================================  =========
``plugins``    Every plugin and the packaged cache record contracts; each problem  problem
               is a detail
``open_in``    Where ``--present`` opens a target, and the app it would find       problem
``metab``      Its version, executable, Python, SoftSchema YAML parser, and      warning
               installation. Its app minimum comes from the app running the check
               (:data:`DOCTOR_APP_ENV`), or else the one ``open_in`` found
``git``        The ``git`` on ``PATH`` against the cloning floor                   warning
               (``ACQUISITION_MINIMUM``), a partial clone's
               (``PARTIAL_CLONE_GIT_MINIMUM``), and the release that reads
               file ages on a Git revision (``FILE_AGES_GIT_MINIMUM``)
``config``     The configuration directory resolves, is private or can be          problem
               created, and its ``config.yml`` is one this release reads; an
               override the app's servers do not get is a warning
``cache``      The cache directory resolves, is private and writable or can be     problem
               created, and is apart from the configuration; an override the
               app's servers do not get, or free space below
               the reserve a first clone leaves free, is a warning
``event_log``  Whether a server writes its event log, where, and what it leaves    warning
               out; an environment that turns it off, or a state directory that
               cannot hold it, is a warning
=============  ==================================================================  =========

A ``problem`` is one ``metab`` cannot serve a folder with: it makes the doctor exit 1, and
the report's ``problems`` lists it, the plugins' and ``open_in``'s one by one. A
``warning`` is a setup some work needs, cloning or the app, and never changes the exit
status, as GitHub's state does not. A configuration directory that is a problem is
reported once, by ``config``: ``open_in``, which reads its settings there, notes that it
could not. uv has no check: ``metab`` never runs it, and the ``metab`` check names it only
in the step that upgrades a uv install. No check opens a network connection.

The text output prints the plugin verdict and ``open_in`` as its first lines and the
other checks after GitHub's section.

**The JSON shape** (``--doctor --json``), which the macOS app's Check Setup… decodes and
the golden ``tests/golden/cli-doctor.tryscript.md`` pins: ``checks`` is a list in the order
above, each an object with

- ``id``: one of the ids above; ``title``: its name for a person;
- ``state``: ``ok``, ``warning``, or ``problem``;
- ``summary``: one sentence;
- ``details``: a list of ``{"name": …, "value": …}``, both strings, in display order;
- ``remedy``: ``null``, or ``{"text": …, "command": …, "url": …}``, where ``command`` is a
  shell command to copy as it is and ``url`` a page to open, either ``null``.

``title``, ``summary``, ``details``, and ``remedy.text`` are display text that no reader
parses, and a detail's ``name`` is a label, not a key. The ``github`` object's ``remedy``
has the same shape (:mod:`metabrowser.builtin_plugins.github.gh_status`).

A key is added, never renamed or removed, without a new minor release
(``docs/publishing.md#choosing-a-version``), and a reader ignores keys it does not know.
"""

from __future__ import annotations

import os
import platform
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal

from metabrowser import __version__
from metabrowser.build_version import display_version
from metabrowser.cache.free_space import (
    FREE_SPACE_RESERVE_ENV,
    free_space_reserve_bytes,
    size_text,
    volume_free_bytes,
)
from metabrowser.invisible_chars import display_segment
from metabrowser.tool_install import Remedy

if TYPE_CHECKING:
    from metabrowser.cli.present import DoctorOpenIn

type CheckState = Literal["ok", "warning", "problem"]
type MetabInstallMethod = Literal["uv_tool", "pipx", "checkout", "environment"]

# A uv tool environment holds uv's receipt, and a pipx one pipx's metadata, at its prefix.
# A source checkout's environment is a `.venv` beside the `pyproject.toml` that declares
# this project (CHECKOUT_PROJECT). `MetabInstall.of` in the app reads the same files the
# same way, and `tests/test_macos_app_pins.py` holds its names to these.
UV_RECEIPT: Final = "uv-receipt.toml"
PIPX_METADATA: Final = "pipx_metadata.json"
CHECKOUT_VENV: Final = ".venv"
# The line, on its own, with spaces or tabs around `=` and after it; `MetabInstall.
# declaresThisProject` matches the same line.
CHECKOUT_PROJECT: Final = re.compile(r'^name[ \t]*=[ \t]*"metabrowser"[ \t\r]*$', re.MULTILINE)
# A pyproject.toml read for CHECKOUT_PROJECT stops here; this repository's is about 9 KB.
_PYPROJECT_MAX_BYTES: Final = 256 * 1024
# The upgrade of a `metab` below the app's minimum, by how it was installed, with the
# minimum in place of `{minimum}`. The app's own copies, which it shows when no `metab`
# runs, are `MetabInstall` in `apps/macos/Sources/ShellCore/Setup/MetabVersion.swift`, and
# `tests/test_macos_app_pins.py` holds them to these.
METAB_UPGRADE_COMMANDS: Final[dict[MetabInstallMethod, str]] = {
    "uv_tool": "uv tool install --upgrade 'metabrowser>={minimum}'",
    "pipx": "pipx install --force 'metabrowser>={minimum}'",
    "checkout": "git pull && make install",
    "environment": "uv tool install --upgrade 'metabrowser>={minimum}'",
}
_RELEASE: Final = re.compile(r"^([0-9]+(?:\.[0-9]+)*)")
# The bundle path of the app running `metab --doctor`, which Help > Check Setup… sets
# (`DoctorRun.spec` in apps/macos/Sources/ShellCore/Setup/DoctorReport.swift). The metab
# check compares with that build's minimum, not the app LaunchServices finds first, which
# is the release build when both are installed (DEFAULT_BUNDLE_IDS). The open_in check
# keeps a terminal's lookup, since it says where `--present` in a terminal opens a target.
DOCTOR_APP_ENV: Final = "METABROWSER_DOCTOR_APP"
# What the app's servers get of the configuration and cache variables, by
# ChildEnvironment's allowlist (apps/macos/Sources/ShellCore/Runtime/ChildEnvironment.swift),
# which tests/test_macos_app_pins.py holds to these two sets; the state directory's, which
# hold only the event log, are passed too. They get none of STORAGE_OVERRIDES.
STORAGE_OVERRIDES: Final = frozenset({"XDG_CONFIG_HOME", "METABROWSER_CACHE_DIR", "XDG_CACHE_HOME"})
# They get LAUNCH_STORAGE_OVERRIDES only as the app was launched with it, by `open --env`,
# as the hand checks launch a development build to keep its recent targets apart, or from
# launchd's environment (`launchctl setenv`). A terminal's `export` reaches no app, so a
# doctor run there cannot tell what the app has, but the doctor the app runs sees the
# app's own, which its servers use too.
LAUNCH_STORAGE_OVERRIDES: Final = frozenset({"METABROWSER_CONFIG_DIR"})


@dataclass(frozen=True, slots=True)
class Check:
    """One setup check's answer, as ``--doctor`` prints it and ``--doctor --json`` serves it."""

    id: str
    title: str
    state: CheckState
    summary: str
    details: tuple[tuple[str, str], ...] = ()
    remedy: Remedy | None = None

    def to_json(self) -> dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "state": self.state,
            "summary": self.summary,
            "details": [{"name": name, "value": value} for name, value in self.details],
            "remedy": self.remedy.to_json() if self.remedy is not None else None,
        }

    def lines(self) -> tuple[str, ...]:
        """The check's text: the state and summary, then each detail, then the fix."""

        lines = [f"{self.id}: {self.state}: {self.summary}"]
        lines.extend(f"  {name}: {value}" for name, value in self.details)
        if self.remedy is not None:
            step = self.remedy.command or self.remedy.url
            lines.append(f"  fix: {self.remedy.text}" + (f" {step}" if step else ""))
        return tuple(lines)

    @property
    def problem(self) -> str | None:
        """The line the report's ``problems`` list holds for a ``problem``."""

        return f"{self.id}: {self.summary}" if self.state == "problem" else None


def _shown(path: str | Path) -> str:
    return display_segment(os.fsencode(path))


def _release(version: str) -> tuple[int, ...] | None:
    match = _RELEASE.match(version)
    return tuple(int(part) for part in match.group(1).split(".")) if match else None


def meets_release(version: str, minimum: str) -> bool | None:
    """Whether *version*'s release numbers are *minimum*'s or later, missing ones zero.

    As the app's ``MetabRequirement.accepts`` compares: a development build of the minimum,
    ``0.13.0.devN``, meets ``0.13.0``. ``None`` when either names no release numbers.
    """

    found, needed = _release(version), _release(minimum)
    if found is None or needed is None:
        return None
    width = max(len(found), len(needed))
    return found + (0,) * (width - len(found)) >= needed + (0,) * (width - len(needed))


def metab_install() -> tuple[MetabInstallMethod, Path]:
    """How this ``metab`` was installed, and where: the tool environment, or the checkout.

    A uv or pipx tool environment is recognized by its receipt at ``sys.prefix``, before a
    checkout, since ``uv tool install --editable`` makes one of each. A checkout's is a
    ``.venv`` beside the ``pyproject.toml`` that names this project, as the app reads it
    (``MetabInstall.of``), so both name the same step. An editable install into any other
    environment is ``environment`` to both, and its step installs with uv.
    """

    prefix = Path(sys.prefix)
    if (prefix / UV_RECEIPT).is_file():
        return "uv_tool", prefix
    if (prefix / PIPX_METADATA).is_file():
        return "pipx", prefix
    if prefix.name == CHECKOUT_VENV and declares_this_project(prefix.parent / "pyproject.toml"):
        return "checkout", prefix.parent
    return "environment", prefix


def declares_this_project(pyproject: Path) -> bool:
    """Whether *pyproject*, a regular file, names this project (:data:`CHECKOUT_PROJECT`),
    read bounded; a FIFO there would block the read."""

    if not pyproject.is_file():
        return False
    try:
        with pyproject.open("rb") as file:
            head = file.read(_PYPROJECT_MAX_BYTES)
    except OSError:
        return False
    return CHECKOUT_PROJECT.search(head.decode("utf-8", "replace")) is not None


def metab_upgrade_remedy(method: MetabInstallMethod, where: Path, minimum: str) -> Remedy:
    """The step that brings a ``metab`` installed by *method* at *where* to *minimum*."""

    command = METAB_UPGRADE_COMMANDS[method].format(minimum=minimum)
    if method == "uv_tool":
        text = "Upgrade the uv tool install:"
    elif method == "pipx":
        text = "Upgrade the pipx install:"
    elif method == "checkout":
        text = f"At the root of the checkout {_shown(where)}:"
    else:
        text = (
            f"This metab is in the Python environment {_shown(where)}; install one with uv, "
            "which the app finds:"
        )
    return Remedy(text, command=command)


_INSTALLED_AS: Final[dict[MetabInstallMethod, str]] = {
    "uv_tool": "with uv tool, in",
    "pipx": "with pipx, in",
    "checkout": "from the source checkout",
    "environment": "in the Python environment",
}


def plugins_check(plugin_count: int, problems: Sequence[str]) -> Check:
    """The plugins and the packaged cache record contracts, each problem a detail."""

    found = "1 plugin" if plugin_count == 1 else f"{plugin_count} plugins"
    if not problems:
        summary = f"{found} and the packaged cache record contracts check out"
        return Check("plugins", "Plugins", "ok", summary, (("plugins", str(plugin_count)),))
    summary = f"{len(problems)} problem(s) with the {found} or the packaged cache record contracts"
    details = (("plugins", str(plugin_count)), *(("problem", problem) for problem in problems))
    return Check("plugins", "Plugins", "problem", summary, details)


def open_in_check(open_in: DoctorOpenIn, *, config_unreadable: bool) -> Check:
    """Where ``--present`` opens a target, from :func:`~metabrowser.cli.present.doctor_open_in`.

    With *config_unreadable*, the settings it could not read there are details, not
    problems: the ``config`` check reports the directory once.
    """

    section = open_in.section
    value, source = section.get("value"), section.get("source")
    browser = section.get("present_browser")
    details: list[tuple[str, str]] = [
        ("open_in", f"{value} ({source})" if value is not None else "unreadable"),
        ("present_browser", "unreadable" if browser is None else str(browser).lower()),
    ]
    app = section.get("app")
    if not isinstance(app, dict):
        details.append(("app", "not looked for"))
    elif app.get("found"):
        details.append(("app", f"{_shown(str(app.get('bundle_path')))} ({app.get('bundle_id')})"))
    else:
        details.append(("app", f"none ({app.get('code')}): {app.get('reason')}"))
    problems = open_in.problems
    if config_unreadable:
        details.extend(("not read", unread) for unread in open_in.unread)
        problems = tuple(problem for problem in problems if problem not in open_in.unread)
    details.extend(("problem", problem) for problem in problems)
    if problems:
        state: CheckState = "problem"
    elif config_unreadable and open_in.unread:
        state = "warning"
    else:
        state = "ok"
    return Check("open_in", "Opening from a terminal", state, open_in.summary, tuple(details))


def metab_check(*, app_path: str | None, app_minimum: str | None, looked_up: bool) -> Check:
    """This ``metab``: its version, where it runs from, and the app's minimum if known.

    *looked_up* says whether ``open_in`` looked for the app, which it does unless the
    preference is ``browser``; *app_path* is the app it found that takes a target, and
    *app_minimum* the oldest ``metab`` that app names.
    """

    from softschema import yaml_parser_mode

    method, where = metab_install()
    executable = os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] else sys.executable
    details: list[tuple[str, str]] = [
        ("version", display_version(__version__)),
        ("executable", _shown(executable)),
        ("python", f"{platform.python_version()} at {_shown(sys.executable)}"),
        ("SoftSchema YAML parser", yaml_parser_mode()),
        ("installed", f"{_INSTALLED_AS[method]} {_shown(where)}"),
    ]
    summary = f"metab {__version__}"
    state: CheckState = "ok"
    remedy: Remedy | None = None
    if app_path is not None and app_minimum is not None:
        details.append(("app", f"{_shown(app_path)} runs metab {app_minimum} or later"))
        if meets_release(__version__, app_minimum) is False:
            state = "warning"
            summary = (
                f"metab {__version__} is older than {app_minimum}, the oldest the app at "
                f"{_shown(app_path)} runs"
            )
            remedy = metab_upgrade_remedy(method, where, app_minimum)
        else:
            summary = f"metab {__version__}, which the app runs"
    elif app_path is not None:
        details.append(("app", f"{_shown(app_path)} names no minimum metab"))
    elif looked_up:
        details.append(("app", "none that takes a target"))
    else:
        details.append(("app", "not looked for"))
    return Check("metab", "metab", state, summary, tuple(details), remedy)


def git_check() -> Check:
    """The ``git`` on ``PATH``: where it is, its version, and each thing that version does.

    The floors are the cloning floor, a partial clone's, and the release that reads file
    ages on a Git revision. A detail line says whether file ages are available, since that
    is the one a person upgrades Git for without anything else failing.
    """

    from metabrowser.checkout_revisions import (
        PARTIAL_CLONE_GIT_MINIMUM,
        partial_clone_version_label,
    )
    from metabrowser.git.file_ages import file_ages_availability, file_ages_version_label
    from metabrowser.git.process import (
        acquisition_allowed,
        detect_git_version,
        git_executable,
        git_upgrade_remedy,
        required_acquisition_version_label,
    )

    executable = git_executable()
    if executable is None:
        return Check(
            "git",
            "Git",
            "warning",
            "no git on PATH, so metab clones no Git source, shows no branch or tag of a "
            "checkout, and dates no file of a Git revision",
            (("executable", "not found on PATH"),),
            git_upgrade_remedy(None),
        )
    version, line = detect_git_version()
    ages = file_ages_availability()
    ages_detail = (
        "available"
        if ages.available
        else f"needs Git {file_ages_version_label()} or newer, so a Git revision shows no By age"
    )
    details = (
        ("executable", _shown(executable)),
        ("version", line or "unknown"),
        ("file ages", ages_detail),
    )
    if version is None:
        summary = f"git at {_shown(executable)} did not name a version metab can read"
    elif not acquisition_allowed(version):
        summary = (
            f"{line} is below the floor for cloning, {required_acquisition_version_label()}, "
            "so metab clones no Git source and shows no branch or tag of a checkout"
        )
    elif version < PARTIAL_CLONE_GIT_MINIMUM:
        summary = (
            f"{line} shows no branch or tag of a partial clone, which needs "
            f"{partial_clone_version_label()}"
        )
    elif not ages.available:
        summary = ages.hint or "file ages on Git revisions are unavailable"
    else:
        return Check("git", "Git", "ok", f"{line}, which meets every floor", details)
    return Check("git", "Git", "warning", summary, details, git_upgrade_remedy(executable))


def _directory_source(override: str, xdg: str) -> str:
    if override in os.environ:
        return override
    if xdg in os.environ:
        return xdg
    return "default"


def _servers_directory(
    directory: Path, source: str, app_path: str | None, *, cache: bool, from_app: bool = False
) -> str | None:
    """The directory the app's servers use instead of *directory*, when they differ.

    The app gives its servers none of :data:`STORAGE_OVERRIDES`, and of
    :data:`LAUNCH_STORAGE_OVERRIDES` only what the app was launched with, which a
    terminal's ``export`` does not reach. So an override set where this ``metab`` runs,
    with an app to compare, names a directory they do not read, as far as a terminal can
    tell, unless the app runs this doctor (*from_app*): then what it sees of those is the
    app's own, which its servers read too.
    """

    from metabrowser.home import StorageDirectoryError, application_cache, configuration_directory

    if source == "default" or app_path is None:
        return None
    dropped = STORAGE_OVERRIDES if from_app else STORAGE_OVERRIDES | LAUNCH_STORAGE_OVERRIDES
    environ = {name: value for name, value in os.environ.items() if name not in dropped}
    try:
        theirs = application_cache(environ) if cache else configuration_directory(environ)
    except StorageDirectoryError:
        return None
    return None if theirs == directory else _shown(theirs)


def _not_creatable(directory: Path) -> str | None:
    """Why *directory*, which does not exist, cannot be created: its nearest existing
    parent is not a directory this user may write. ``None`` when it can be."""

    parent = directory.parent
    while not parent.exists() and parent != parent.parent:
        parent = parent.parent
    if not parent.is_dir():
        return f"{_shown(parent)} is not a directory"
    if not os.access(parent, os.W_OK | os.X_OK):
        return f"{_shown(parent)} is not writable by this user"
    return None


def _create_remedy(override: str) -> Remedy:
    return Remedy(
        f"Create it with mode 700 yourself, or set {override} to a private directory you own."
    )


def config_check(*, app_path: str | None = None, from_app: bool = False) -> Check:
    """The configuration directory: where, whether it is private, and its ``config.yml``.

    *app_path* is the app ``open_in`` found, or the app running this doctor (*from_app*),
    whose servers get an override only as :func:`_servers_directory` says.
    """

    from metabrowser.cache.layout import (
        ConfigurationError,
        ConfigurationIOError,
        FutureLayoutFormatError,
        read_config,
    )
    from metabrowser.config_file import CONFIG_RECORD
    from metabrowser.home import (
        PrivateStorageError,
        StorageDirectoryError,
        configuration_directory,
        validate_private_home,
    )

    heading = "Configuration"
    source = _directory_source("METABROWSER_CONFIG_DIR", "XDG_CONFIG_HOME")
    try:
        directory = configuration_directory()
    except StorageDirectoryError as exc:
        return Check("config", heading, "problem", str(exc), (("source", source),))
    details: list[tuple[str, str]] = [("directory", _shown(directory)), ("source", source)]
    try:
        validate_private_home(directory)
    except FileNotFoundError:
        details.append((CONFIG_RECORD, "none"))
        blocked = _not_creatable(directory)
        if blocked is not None:
            return Check(
                "config",
                heading,
                "problem",
                f"the configuration directory does not exist, and metab cannot create it: "
                f"{blocked}",
                tuple(details),
                _create_remedy("METABROWSER_CONFIG_DIR"),
            )
        return _overridden(
            Check(
                "config",
                heading,
                "ok",
                "the configuration directory is not created yet; metab creates it when it "
                "first saves a setting",
                tuple(details),
            ),
            _servers_directory(directory, source, app_path, cache=False, from_app=from_app),
        )
    except (PrivateStorageError, StorageDirectoryError) as exc:
        return Check("config", heading, "problem", str(exc), tuple(details))
    except OSError as exc:
        why = exc.strerror or "it cannot be read"
        summary = f"the configuration directory cannot be read ({why})"
        return Check("config", heading, "problem", summary, tuple(details))
    try:
        config = read_config(directory, shared="keep")
    except FutureLayoutFormatError as exc:
        return Check("config", heading, "problem", str(exc), tuple(details))
    except (ConfigurationError, ConfigurationIOError) as exc:
        details.append((CONFIG_RECORD, "unreadable"))
        return Check(
            "config",
            heading,
            "problem",
            f"{CONFIG_RECORD} cannot be read: {exc}",
            tuple(details),
            Remedy(f"Move {_shown(directory / CONFIG_RECORD)} aside; metab writes a fresh one."),
        )
    details.append((CONFIG_RECORD, "none" if config is None else "read"))
    return _overridden(
        Check("config", heading, "ok", "the configuration directory is private", tuple(details)),
        _servers_directory(directory, source, app_path, cache=False, from_app=from_app),
    )


def _overridden(check: Check, servers: str | None) -> Check:
    """*check*, an ``ok`` one, as a warning when the app's servers use *servers* instead."""

    if servers is None:
        return check
    source = dict(check.details).get("source", "an override")
    return Check(
        check.id,
        check.title,
        "warning",
        f"{source} names this directory, but the app's servers get no {source} from a terminal "
        f"and use {servers}, so what metab records here in a terminal the app does not see",
        (*check.details, ("app's servers", servers)),
        Remedy(f"Unset {source} in the terminal, or open targets from the app."),
    )


def cache_check(*, app_path: str | None = None) -> Check:
    """The cache directory: where, whether it is private and writable, and its free space.

    *app_path* is the app ``open_in`` found, whose servers get none of the overrides.
    """

    from metabrowser.home import (
        PrivateStorageError,
        StorageDirectoryError,
        application_cache,
        private_directory_is_writable,
        validate_private_home,
        validate_storage_separation,
    )

    heading = "Cache"
    source = _directory_source("METABROWSER_CACHE_DIR", "XDG_CACHE_HOME")
    try:
        directory = application_cache()
        validate_storage_separation(directory)
    except StorageDirectoryError as exc:
        return Check("cache", heading, "problem", str(exc), (("source", source),))
    details: list[tuple[str, str]] = [("directory", _shown(directory)), ("source", source)]
    free = volume_free_bytes(directory)
    if free is not None:
        details.append(("free space", size_text(free)))
    try:
        validate_private_home(directory)
        writable = private_directory_is_writable(directory, "")
    except FileNotFoundError:
        blocked = _not_creatable(directory)
        if blocked is not None:
            summary = f"the cache directory does not exist, and metab cannot create it: {blocked}"
            remedy = _create_remedy("METABROWSER_CACHE_DIR")
            return Check("cache", heading, "problem", summary, tuple(details), remedy)
        summary = "the cache directory is not created yet; metab creates it on first use"
        return _cache_space(
            _overridden(
                Check("cache", heading, "ok", summary, tuple(details)),
                _servers_directory(directory, source, app_path, cache=True),
            ),
            free,
        )
    except (PrivateStorageError, StorageDirectoryError) as exc:
        return Check("cache", heading, "problem", str(exc), tuple(details))
    except OSError as exc:
        why = exc.strerror or "it cannot be read"
        summary = f"the cache directory cannot be read ({why})"
        return Check("cache", heading, "problem", summary, tuple(details))
    if not writable:
        return Check(
            "cache",
            heading,
            "problem",
            "the cache directory is not writable, so metab can keep no record or clone",
            tuple(details),
            Remedy(
                "Make it writable by you, or set METABROWSER_CACHE_DIR to a private "
                "directory you own."
            ),
        )
    summary = "the cache directory is private and writable"
    return _cache_space(
        _overridden(
            Check("cache", heading, "ok", summary, tuple(details)),
            _servers_directory(directory, source, app_path, cache=True),
        ),
        free,
    )


def event_log_check() -> Check:
    """The event log: whether a server writes one, where, and what it leaves out.

    An environment that turns it off is a warning, since no latency or failure is then
    recorded (the owner's aim is that they always are). So is a state directory that
    cannot hold it. The check reads the environment of the process that runs it, and a
    server in a folder inside the events directory writes none whatever the environment
    says, which a detail states and the page's Details names when it happens
    (:func:`metabrowser.event_log.off_reason`).
    """

    from metabrowser import event_log
    from metabrowser.home import StorageDirectoryError

    heading = "Event log"
    source = _directory_source("METABROWSER_STATE_DIR", "XDG_STATE_HOME")
    try:
        _, directory = event_log.log_directory()
    except StorageDirectoryError as exc:
        summary = f"the state directory, which holds the event log, does not resolve: {exc}"
        return Check("event_log", heading, "warning", summary, (("source", source),))
    details: list[tuple[str, str]] = [("directory", _shown(directory)), ("source", source)]
    if not event_log.enabled_by_environment():
        return Check(
            "event_log",
            heading,
            "warning",
            f"{event_log.ENABLE_ENV} turns the event log off, so no latency or failure is recorded",
            tuple(details),
            Remedy(f"Unset {event_log.ENABLE_ENV}, or set it to 1."),
        )
    details.append(
        (
            "not recorded",
            "a server whose folder is the events directory or inside it writes no log, "
            "so that browsing the log does not change it; every other server writes one",
        )
    )
    if directory.is_dir():
        segments = sum(1 for _ in directory.glob("events-*.jsonl"))
        details.append(("segments", str(segments)))
        return Check(
            "event_log", heading, "ok", "a server writes an event log here", tuple(details)
        )
    blocked = _not_creatable(directory)
    if blocked is not None:
        summary = f"the event log's directory does not exist, and metab cannot create it: {blocked}"
        return Check(
            "event_log",
            heading,
            "warning",
            summary,
            tuple(details),
            Remedy(
                "Create the state directory with mode 700 yourself, or set "
                "METABROWSER_STATE_DIR to a private directory you own."
            ),
        )
    summary = "no event log is written yet; the first server creates its directory"
    return Check("event_log", heading, "ok", summary, tuple(details))


def _cache_space(check: Check, free: int | None) -> Check:
    """*check* as a warning when its volume has less free than the reserve a first clone
    leaves (:func:`~metabrowser.cache.free_space.free_space_reserve_bytes`), so that every
    first clone is refused but one that borrows a checkout's objects, which is not checked
    (:func:`~metabrowser.cache.acquire.acquire_source`)."""

    reserve = free_space_reserve_bytes()
    if free is None or free >= reserve or check.state != "ok":
        return check
    return Check(
        check.id,
        check.title,
        "warning",
        f"the cache's volume has {size_text(free, 'down')} free, less than the "
        f"{size_text(reserve, 'up')} a first clone leaves free, so metab refuses every first clone "
        "that does not borrow from a checkout",
        check.details,
        Remedy(
            "Free space on the volume, set METABROWSER_CACHE_DIR to one with more, or "
            f"lower {FREE_SPACE_RESERVE_ENV}."
        ),
    )


def running_app() -> tuple[str, str | None] | None:
    """The app :data:`DOCTOR_APP_ENV` names and the oldest ``metab`` it runs, or ``None``
    when the variable is unset or names no bundle with an ``Info.plist``."""

    from metabrowser.cli.present import MINIMUM_METAB_KEY, read_info_plist

    named = os.environ.get(DOCTOR_APP_ENV, "")
    if not named or not os.path.isabs(named):
        return None
    info = read_info_plist(Path(named))
    if info is None:
        return None
    declared = info.get(MINIMUM_METAB_KEY)
    return named, declared if isinstance(declared, str) and declared else None


def doctor_checks(
    *, plugin_count: int, plugin_problems: Sequence[str], open_in: DoctorOpenIn
) -> tuple[Check, ...]:
    """Every check, in the order the report lists them."""

    running = running_app()
    if running is not None:
        app_path, app_minimum = running
        looked_up = True
    else:
        app_path, app_minimum = open_in.app_path, open_in.app_minimum_metab
        looked_up = open_in.section.get("app") is not None
    config = config_check(app_path=app_path, from_app=running is not None)
    return (
        plugins_check(plugin_count, plugin_problems),
        open_in_check(open_in, config_unreadable=config.state == "problem"),
        metab_check(app_path=app_path, app_minimum=app_minimum, looked_up=looked_up),
        git_check(),
        config,
        cache_check(app_path=app_path),
        event_log_check(),
    )


__all__ = [
    "CHECKOUT_PROJECT",
    "CHECKOUT_VENV",
    "DOCTOR_APP_ENV",
    "LAUNCH_STORAGE_OVERRIDES",
    "METAB_UPGRADE_COMMANDS",
    "PIPX_METADATA",
    "STORAGE_OVERRIDES",
    "UV_RECEIPT",
    "Check",
    "CheckState",
    "MetabInstallMethod",
    "declares_this_project",
    "doctor_checks",
    "event_log_check",
    "meets_release",
    "metab_check",
    "metab_install",
    "metab_upgrade_remedy",
    "open_in_check",
    "plugins_check",
    "running_app",
]
