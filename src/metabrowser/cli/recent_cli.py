"""The recent-target modes: list, add, forget, and clear what was opened lately.

Four modes on the ``metab`` CLI (parsing lives in :mod:`metabrowser.cli.main`), over the
one list :mod:`metabrowser.recent_targets` keeps:

* ``metab --recent``: the list, most recently opened first; ``--json`` for a shell.
* ``metab TARGET --recent-add``: record TARGET as opened, as serving it would, without
  serving. A shell uses it for an open that starts no server, such as the macOS app
  bringing forward a folder that is already open.
* ``metab TARGET --recent-forget``: remove TARGET's entry.
* ``metab --recent-clear``: empty the list.

None of them starts a server, imports one, or reads a repository, and none looks at a
listed folder (``docs/project/architecture/arch-recent-targets.md`` says why). TARGET is
read as ROOT is: a folder, a file, which stands for its folder, or a URL, which stands
for its repository whatever it selects inside it.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from metabrowser import recent_targets
from metabrowser.errors import CLIError
from metabrowser.invisible_chars import display_segment
from metabrowser.paths_safe import tilde_path
from metabrowser.recent_targets import RecentTarget, RecentTargetsError, TargetMode

if TYPE_CHECKING:
    from metabrowser.cache.urls import GitSource

# The transports a server serves (``_require_acquired_transport`` in ``git_pin_cli.py``);
# a source of any other cannot be opened, so it is not a recent target.
_SERVED_TRANSPORTS = frozenset({"file", "https"})


def _shown(target: RecentTarget, home: Path | None) -> str:
    """A root for a terminal: the home folder as ``~``, and nothing a terminal acts on."""

    root = target.root
    if target.mode == "folder" and home is not None:
        root = tilde_path(Path(root), home)
    return display_segment(root.encode("utf-8", "surrogateescape"))


def _home() -> Path | None:
    try:
        return Path.home().resolve()
    except (OSError, RuntimeError):
        return None


def list_recent(*, as_json: bool) -> None:
    """Print the recent targets, most recently opened first.

    ``--json`` prints one object: ``limit``, how many the list keeps; ``targets``, each
    with its ``mode``, ``root``, and ``opened_at``; and ``problem``, ``null`` or the
    sentence that says why a damaged or newer file lists as empty. A problem is part of
    the answer, with exit status 0, so a shell that reads standard output and standard
    error together still finds one object.
    """

    try:
        listing = recent_targets.read()
    except RecentTargetsError as error:
        raise CLIError(str(error)) from error
    if as_json:
        document = {
            "limit": recent_targets.MAX_RECENT_TARGETS,
            "targets": [target.as_json() for target in listing.targets],
            "problem": listing.problem,
        }
        typer.echo(json.dumps(document, indent=2, ensure_ascii=False))
        return
    if listing.problem is not None:
        typer.echo(listing.problem, err=True)
        return
    if not listing.targets:
        typer.echo("No recent targets.")
        return
    home = _home()
    for target in listing.targets:
        typer.echo(f"{target.mode:<6}  {target.opened_at}  {_shown(target, home)}")


def _served_folder(path: Path) -> Path:
    """The folder a serve of *path* would serve: itself, or a file's folder."""

    resolved = path.expanduser().resolve()
    if resolved.is_file():
        resolved = resolved.parent
    if not resolved.is_dir():
        raise CLIError(f"{resolved} is not a directory")
    return resolved


def _mirror_root(source: GitSource) -> str:
    if source.transport not in _SERVED_TRANSPORTS:
        raise CLIError(
            f"{source.transport} Git sources are not served yet ({source.normalized}), "
            "so they are not recent targets"
        )
    return source.normalized


def add_recent(target: Path | GitSource) -> None:
    """Record *target* as opened now, as a serve of it would."""

    mode: TargetMode
    if isinstance(target, Path):
        mode, root = "folder", recent_targets.folder_root(_served_folder(target))
    else:
        mode, root = "mirror", _mirror_root(target)
    try:
        recent_targets.record(mode, root)
    except (RecentTargetsError, recent_targets.UnrecordableRootError) as error:
        raise CLIError(f"not recorded: {error}") from error


def _folder_spellings(path: Path) -> frozenset[tuple[str, str]]:
    """Every root a folder entry for *path* could be stored under.

    A folder that exists is stored as :func:`~metabrowser.recent_targets.folder_root`
    spells it. One that is gone cannot be resolved, so its entry is matched by the path
    as given, made absolute, which is how a shell hands back a root it was listed.
    """

    expanded = path.expanduser()
    spellings = {os.path.abspath(expanded)}
    try:
        resolved = expanded.resolve(strict=True)
    except (OSError, RuntimeError):
        return frozenset(("folder", spelling) for spelling in spellings)
    if resolved.is_file():
        resolved = resolved.parent
    spellings.add(str(resolved))
    spellings.add(recent_targets.folder_root(resolved))
    return frozenset(("folder", spelling) for spelling in spellings)


def forget_recent(target: Path | GitSource) -> None:
    """Remove *target*'s entry, and say whether there was one."""

    if isinstance(target, Path):
        roots = _folder_spellings(target)
    else:
        roots = frozenset({("mirror", target.normalized)})
    try:
        removed = recent_targets.forget(roots)
    except RecentTargetsError as error:
        raise CLIError(str(error)) from error
    typer.echo("Forgotten." if removed else "Not a recent target; nothing changed.")


def clear_recent() -> None:
    """Empty the list, and say how many entries it held."""

    try:
        removed = recent_targets.clear()
    except RecentTargetsError as error:
        raise CLIError(str(error)) from error
    noun = "target" if removed == 1 else "targets"
    typer.echo(f"Cleared {removed} recent {noun}.")
