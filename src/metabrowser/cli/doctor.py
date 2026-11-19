"""The setup checks of ``metab --doctor``: this ``metab``, Git, and the two directories.

``doctor_plugins`` (:mod:`metabrowser.cli.plugins`) checks the plugins, reports where
``--present`` opens a target (``open_in``) and GitHub CLI's sign-in (``github``), and then
runs :func:`setup_checks`. Each check reads what is there and changes nothing.

=============  ==================================================================  =========
``id``         What it checks                                                      Worst
=============  ==================================================================  =========
``metab``      Its version, executable, Python, how it was installed, and, when    warning
               ``open_in`` found the app, the oldest ``metab`` that app runs
``git``        The ``git`` on ``PATH`` against the cloning floor                   warning
               (``ACQUISITION_MINIMUM``) and a partial clone's
               (``PARTIAL_CLONE_GIT_MINIMUM``)
``config``     The configuration directory resolves, is private, and its           problem
               ``config.yml`` is one this release reads
``cache``      The cache directory resolves, is private and writable, and is       problem
               apart from the configuration; its volume's free space
=============  ==================================================================  =========

A ``problem`` is one ``metab`` cannot serve a folder with, so it is also listed in the
report's ``problems`` and makes the doctor exit 1. A ``warning`` is a setup some work
needs, cloning or the app, and never changes the exit status, as GitHub's state does not.
uv has no check: ``metab`` never runs it, and the ``metab`` check names it only in the
step that upgrades a uv install. No check opens a network connection.

**The JSON shape** (``--doctor --json``), which the macOS app's Check Setup… decodes and
the golden ``tests/golden/cli-doctor.tryscript.md`` pins: ``checks`` is a list in the order
above, each an object with

- ``id``: one of the ids above; ``title``: its name for a person;
- ``state``: ``ok``, ``warning``, or ``problem``;
- ``summary``: one sentence;
- ``details``: a list of ``{"name": …, "value": …}``, both strings, in display order;
- ``remedy``: ``null``, or ``{"text": …, "command": …, "url": …}``, where ``command`` is a
  shell command to copy as it is and ``url`` a page to open, either ``null``.

A key is added, never renamed or removed, without a new minor release
(``docs/publishing.md#choosing-a-version``), and a reader ignores keys it does not know.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from metabrowser import __version__
from metabrowser.build_version import display_version, source_checkout
from metabrowser.invisible_chars import display_segment
from metabrowser.tool_install import Remedy

type CheckState = Literal["ok", "warning", "problem"]
type MetabInstallMethod = Literal["uv_tool", "pipx", "checkout", "environment"]

# A uv tool environment holds uv's receipt, and a pipx one pipx's metadata, at its prefix.
UV_RECEIPT: Final = "uv-receipt.toml"
PIPX_METADATA: Final = "pipx_metadata.json"
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
    checkout, since ``uv tool install --editable`` makes one of each. A checkout is the
    repository whose tracked source is running (:func:`source_checkout`).
    """

    prefix = Path(sys.prefix)
    if (prefix / UV_RECEIPT).is_file():
        return "uv_tool", prefix
    if (prefix / PIPX_METADATA).is_file():
        return "pipx", prefix
    checkout = source_checkout()
    if checkout is not None:
        return "checkout", checkout
    return "environment", prefix


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


def metab_check(*, app_path: str | None, app_minimum: str | None, looked_up: bool) -> Check:
    """This ``metab``: its version, where it runs from, and the app's minimum if known.

    *looked_up* says whether ``open_in`` looked for the app, which it does unless the
    preference is ``browser``; *app_path* is the app it found that takes a target, and
    *app_minimum* the oldest ``metab`` that app names.
    """

    method, where = metab_install()
    executable = os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] else sys.executable
    details: list[tuple[str, str]] = [
        ("version", display_version(__version__)),
        ("executable", _shown(executable)),
        ("python", f"{platform.python_version()} at {_shown(sys.executable)}"),
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
    """The ``git`` on ``PATH``, against the floor for cloning and a partial clone's."""

    from metabrowser.checkout_revisions import (
        PARTIAL_CLONE_GIT_MINIMUM,
        partial_clone_version_label,
    )
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
            "no git on PATH, so metab clones no Git source and shows no branch or tag of a "
            "checkout",
            (("executable", "not found on PATH"),),
            git_upgrade_remedy(None),
        )
    version, line = detect_git_version()
    details = (("executable", _shown(executable)), ("version", line or "unknown"))
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
    else:
        return Check("git", "Git", "ok", f"{line}, which meets every floor", details)
    return Check("git", "Git", "warning", summary, details, git_upgrade_remedy(executable))


def _directory_source(override: str, xdg: str) -> str:
    if override in os.environ:
        return override
    if xdg in os.environ:
        return xdg
    return "default"


def config_check() -> Check:
    """The configuration directory: where, whether it is private, and its ``config.yml``."""

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
        return Check(
            "config",
            heading,
            "ok",
            "the configuration directory is not created yet; metab creates it when it "
            "first saves a setting",
            tuple(details),
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
    return Check("config", heading, "ok", "the configuration directory is private", tuple(details))


def _free_space(directory: Path) -> str | None:
    """The free space on the volume that holds *directory*, or its nearest existing parent."""

    probe = directory
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    try:
        free = shutil.disk_usage(probe).free
    except OSError:
        return None
    return f"{free / 1e9:.1f} GB"


def cache_check() -> Check:
    """The cache directory: where, whether it is private and writable, and its free space."""

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
    free = _free_space(directory)
    if free is not None:
        details.append(("free space", free))
    try:
        validate_private_home(directory)
        writable = private_directory_is_writable(directory, "")
    except FileNotFoundError:
        summary = "the cache directory is not created yet; metab creates it on first use"
        return Check("cache", heading, "ok", summary, tuple(details))
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
    return Check("cache", heading, "ok", summary, tuple(details))


def setup_checks(
    *, app_path: str | None, app_minimum: str | None, looked_up: bool
) -> tuple[Check, ...]:
    """Every setup check, in the order the report lists them."""

    return (
        metab_check(app_path=app_path, app_minimum=app_minimum, looked_up=looked_up),
        git_check(),
        config_check(),
        cache_check(),
    )


__all__ = [
    "METAB_UPGRADE_COMMANDS",
    "PIPX_METADATA",
    "UV_RECEIPT",
    "Check",
    "CheckState",
    "MetabInstallMethod",
    "meets_release",
    "metab_check",
    "metab_install",
    "metab_upgrade_remedy",
    "setup_checks",
]
