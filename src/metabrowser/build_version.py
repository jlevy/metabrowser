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
there is a repository to read: how far past the tag it is, which commit, and
whether the tree is dirty. The dirty marker is the one that matters most,
because it is the state no version string can otherwise describe and the state
a developer is in nearly all the time.

**This never changes what the package reports.** ``__version__`` stays exactly
what was installed, because the publish workflow compares it against the
release tag and a marker there would fail that check for the wrong reason. The
annotation is for display only.

**And it never fails a run.** No repository, no git binary, a shallow clone, or
a slow filesystem all fall through to the plain version. A version string is
not worth an error, and this is code that runs before anything useful happens.
"""

from __future__ import annotations

import subprocess
from functools import cache
from pathlib import Path

_GIT_TIMEOUT_SECONDS = 2.0
"""Long enough for a local repository, short enough to never be the reason a
command felt slow. A version string is not worth waiting on."""


def _git(repository: Path, *arguments: str) -> str | None:
    """Run one git command in *repository*, or return None for any reason at all."""

    try:
        # Fixed argv, no shell, and git is resolved from PATH.
        completed = subprocess.run(
            ["git", "-C", str(repository), *arguments],
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


@cache
def source_checkout() -> Path | None:
    """The repository this package is running from, or None if it is installed.

    Installed packages live in site-packages, which is not a checkout, so the
    ``rev-parse`` fails and every caller falls through to the plain version.
    """

    here = Path(__file__).resolve().parent
    top = _git(here, "rev-parse", "--show-toplevel")
    return Path(top) if top else None


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
    described = _git(repository, "describe", "--tags", "--long", "--dirty=+dirty")
    if described:
        # git describe gives `<tag>-<commits>-g<sha>[+dirty]`; the tag itself is
        # already in the package version, so only the distance and sha are new.
        marker = described.removeprefix("+dirty")
        pieces = marker.split("-")
        if len(pieces) >= 3:
            commits, sha = pieces[-2], pieces[-1]
            ahead = commits.removesuffix("+dirty")
            sha_clean = sha.removesuffix("+dirty")
            if ahead.isdigit() and int(ahead) > 0:
                parts.append(f"+{ahead} commits")
            if sha_clean.startswith("g"):
                parts.append(sha_clean[1:])
        if described.endswith("+dirty"):
            parts.append("dirty")
    elif _git(repository, "rev-parse", "--short", "HEAD"):
        # A repository with no tags at all still has a commit worth naming.
        parts.append(str(_git(repository, "rev-parse", "--short", "HEAD")))

    if "dirty" not in parts and _git(repository, "status", "--porcelain"):
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


__all__ = ["build_state", "display_version", "source_checkout"]
