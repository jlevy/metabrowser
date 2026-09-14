"""What to call a build that is not exactly a released one.

``metabrowser.__version__`` is the package version, recorded by
``importlib.metadata`` when the package was installed. That is the right answer
for an installed release and a stale one for a checkout: an editable install
records its version once, and the working tree keeps moving underneath it. A
build twenty-seven commits past its tag still says the tag, and a build with
uncommitted changes says nothing at all.

That gap is not theoretical. Building a release candidate produced a
``0.5.2.dev`` artifact when a ``0.6.0`` one was wanted, and a side-by-side
comparison of two builds had both of them reporting the same version — the
candidate's number was a snapshot from before the commits being measured. A
timing attributed to the wrong build is an error that survives a whole
investigation, because nothing on screen contradicts it.

So a version shown to a person is annotated with the repository state when
the running code is that repository's tracked source: how far past the tag it
is, which commit, and whether the tree is dirty. The dirty marker is the one
that matters most, because it is the state no version string can otherwise
describe and the state a developer is in nearly all the time.

**This never changes what the package reports.** ``__version__`` stays exactly
what was installed, because the publish workflow compares it against the
release tag and a marker there would fail that check for the wrong reason. The
annotation is for display only.

**And it never fails a run.** No repository, no git binary, a shallow clone, or
a slow filesystem all fall through to the plain version. A version string is
not worth an error, and this is code that runs before anything useful happens.
"""

from __future__ import annotations

import os
import subprocess
from functools import cache
from pathlib import Path

_GIT_TIMEOUT_SECONDS = 2.0
"""Long enough for a local repository, short enough to never be the reason a
command felt slow. A version string is not worth waiting on."""

_CHECKOUT_PATH = "src/metabrowser/build_version.py"
"""Where this module sits in a Metabrowser checkout, relative to its root."""


def _git(repository: Path, *arguments: str) -> str | None:
    """Run one git command in *repository*, or return None for any reason at all."""

    # GIT_DIR and its siblings OVERRIDE -C, and git exports them to every hook
    # it runs — so a metab invoked from inside a hook would report that hook's
    # repository instead of this one. Strip them and ask only about
    # `repository`.
    environment = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    try:
        # Fixed argv, no shell, and git is resolved from PATH. Git prints tags
        # and paths as bytes that need not be UTF-8, and surrogateescape keeps
        # them rather than raising.
        completed = subprocess.run(
            ["git", "-C", str(repository), *arguments],
            capture_output=True,
            encoding="utf-8",
            errors="surrogateescape",
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
            env=environment,
        )
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


@cache
def source_checkout() -> Path | None:
    """The checkout this package is running from, or None if it is installed.

    A repository describes this build only if it is Metabrowser's repository
    and tracks the file that is running. An enclosing work tree alone is not
    enough: a virtualenv created inside a project's repository — a
    project-local ``.venv/``, or a benchmark environment under an ignored
    ``.bench/`` — puts an installed wheel under that repository without making
    it that repository's code. Tracking alone is not enough either: a copy
    committed into another project, by ``pip install --target vendor/`` and a
    commit, is tracked, but that project's tags and commits say nothing about
    which Metabrowser is running.

    So ask git for this file's tracked path from the repository root, and
    accept only the path it has in a Metabrowser checkout. An editable or
    ``uv run`` checkout, a linked worktree, or a submodule imports the tracked
    ``src/metabrowser/`` and passes, and the root is then two directories up
    with no second git call. An installed copy is untracked, outside any
    repository, or tracked somewhere else, and falls through to the plain
    version.
    """

    module = Path(__file__).resolve()
    tracked = _git(module.parent, "ls-files", "--error-unmatch", "--full-name", "--", module.name)
    return module.parents[2] if tracked == _CHECKOUT_PATH else None


@cache
def build_state() -> str:
    """How this build differs from the last tag, undecorated, or ``""``.

    Returns something like ``"+27 commits, 9084e6b, dirty"``. Undecorated so
    each caller can frame it in its own sentence rather than slicing brackets
    off a string someone else chose.

    Empty for an installed release, which is the common case and the one where
    the recorded version is already the whole truth.
    """

    repository = source_checkout()
    if repository is None:
        return ""

    parts: list[str] = []
    # Not `--dirty`: that refreshes the index and writes it back under
    # index.lock whatever --no-optional-locks says, and a version string must
    # never be the reason a concurrent `git commit` finds the index locked.
    described = _git(repository, "describe", "--tags", "--long")
    if described:
        # git describe gives `<tag>-<commits>-g<sha>`; the tag itself is
        # already in the package version, so only the distance and sha are new.
        pieces = described.split("-")
        if len(pieces) >= 3:
            ahead, sha = pieces[-2], pieces[-1]
            if ahead.isdigit() and int(ahead) > 0:
                parts.append(f"+{ahead} commits")
            if sha.startswith("g"):
                parts.append(sha[1:])
    else:
        # A repository with no tags at all still has a commit worth naming.
        head = _git(repository, "rev-parse", "--short", "HEAD")
        if head:
            parts.append(head)

    # Tracked edits, staged changes, and new files all change the build.
    if _git(repository, "--no-optional-locks", "status", "--porcelain"):
        parts.append("dirty")

    return ", ".join(parts)


def display_version(version: str) -> str:
    """*version* as a person should read it, annotated when it is not a release.

    An installed release returns unchanged. A checkout gains what the version
    alone cannot say — how far past the tag, which commit, and whether the tree
    has uncommitted changes.
    """

    state = build_state()
    return f"{version} ({state})" if state else version


def display_version_line(command_name: str, version: str) -> str:
    """Return the complete version line shown by a command or browser surface."""

    return f"{command_name} {display_version(version)}"


__all__ = ["build_state", "display_version", "display_version_line", "source_checkout"]
