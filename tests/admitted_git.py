"""Gate for tests that must run on a real Git at or above the acquisition floor.

Production refuses URL acquisition below the security floor in
``tests/fixtures/repository-cache/git-version-gates.json``, and the ordinary CI
runner's Git is below it, so most acquisition tests patch the floor. Tests gated
here run the production floor unpatched instead. The full-clone acceptance tests
use it to prove on each admitted release that acquisition leaves a complete store
and that every read answers from that store with the origin gone.

Without ``METABROWSER_REQUIRE_ADMITTED_GIT`` a Git below the floor skips these
tests. The CI ``admitted-git`` job builds admitted releases from source and sets
that variable to the version it put on ``PATH``. There, a skip becomes a
failure, and so does a different Git answering, so a job that silently tested
nothing cannot pass.
"""

from __future__ import annotations

import os

import pytest

from metabrowser.git.process import acquisition_allowed, detect_git_version, parse_git_version

REQUIRE_ADMITTED_GIT_ENV = "METABROWSER_REQUIRE_ADMITTED_GIT"


def required_admitted_git() -> str | None:
    """The exact Git release this run must use, or ``None`` when it may skip."""

    value = os.environ.get(REQUIRE_ADMITTED_GIT_ENV, "").strip()
    return value or None


def require_admitted_git() -> tuple[int, int, int]:
    """Return the running Git version when the production floor admits it.

    Skips below the floor, unless ``METABROWSER_REQUIRE_ADMITTED_GIT`` names the
    release this run must use; then anything else fails.
    """

    version, raw = detect_git_version()
    expected = required_admitted_git()
    if expected is None:
        if version is None or not acquisition_allowed(version):
            pytest.skip(
                f"needs a Git the acquisition floor admits; found {raw or 'no git'!r}. "
                f"CI sets {REQUIRE_ADMITTED_GIT_ENV} so this cannot skip there."
            )
        return version
    wanted = parse_git_version(f"git version {expected}")
    if wanted is None:
        pytest.fail(f"{REQUIRE_ADMITTED_GIT_ENV}={expected!r} is not a Git version")
    if version is None or version != wanted:
        pytest.fail(f"{REQUIRE_ADMITTED_GIT_ENV}={expected} but {raw or 'no git'!r} answered")
    if not acquisition_allowed(version):
        pytest.fail(f"Git {expected} is below the acquisition floor")
    return version
