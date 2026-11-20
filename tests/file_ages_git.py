"""The Git a test reads file ages with.

File ages on a Git revision need ``git last-modified``
(``metabrowser.git.file_ages.FILE_AGES_GIT_MINIMUM``). The suite has to pass on whatever Git
a machine has, so every test starts with the Git reading as 2.50.1, which is below that
minimum: a page, a transcript, and a route answer the same everywhere, and none shows a time
a revision does not have there. A test that exercises the feature asks for
:func:`file_ages_git`, which leaves the real Git in place and skips when it is too old.

Without ``METABROWSER_REQUIRE_ADMITTED_GIT`` such a skip stands. The CI ``admitted-git`` job
that builds a Git at or above the minimum sets it to that release, and there a skip is a
failure, so the present path cannot go untested there; the jobs that build older releases run
the same modules and exercise the absent path.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Generator
from typing import Final

import pytest

from metabrowser.git import file_ages
from metabrowser.git import file_ages_service as service_module
from metabrowser.git.file_ages import FILE_AGES_GIT_MINIMUM, RevisionAges, file_ages_availability
from metabrowser.git.file_ages_service import FileAgesService
from metabrowser.git.process import RepositoryStoreTarget, detect_git_version
from tests.admitted_git import REQUIRE_ADMITTED_GIT_ENV, required_admitted_git
from tests.required_tools import require_git

FILE_AGES_GIT_SKIP: Final = "needs a Git that reads file ages"
# The Git every test sees unless it asks for the real one: Apple's, and the Git of the
# macOS 26.6 toolchain, below the minimum.
PRETEND_GIT_VERSION: Final = (2, 50, 1)
PRETEND_GIT_LINE: Final = "git version 2.50.1 (Apple Git-155)"


def pretend_old_git(patch: pytest.MonkeyPatch) -> None:
    """Make the Git ``file_ages_availability`` reads a 2.50.1, which has no last-modified."""

    patch.setattr(file_ages, "git_executable", lambda: "/usr/bin/git")
    patch.setattr(file_ages, "detect_git_version", lambda: (PRETEND_GIT_VERSION, PRETEND_GIT_LINE))


def pretend_git(patch: pytest.MonkeyPatch, line: str, version: tuple[int, int, int] | None) -> None:
    """Make the Git ``file_ages_availability`` reads the one *line* names."""

    patch.setattr(file_ages, "git_executable", lambda: "/usr/bin/git")
    patch.setattr(file_ages, "detect_git_version", lambda: (version, line))


def reset_file_ages_service() -> None:
    """Forget the process's answers and cancel its reads, as a test starts and ends.

    These helpers are the tests' alone: production asks the service for a status and never
    waits for a read, counts one, or looks inside it.
    """

    service, service_module._service = service_module._service, None  # pyright: ignore[reportPrivateUsage]
    if service is not None:
        for task in list(service._jobs.values()):  # pyright: ignore[reportPrivateUsage]
            task.cancel()


def kept_answer(
    service: FileAgesService, target: RepositoryStoreTarget, commit: str
) -> RevisionAges | None:
    """The answer *service* keeps for *commit*, without asking for one."""

    return service._answers.get((target.git_dir, commit))  # pyright: ignore[reportPrivateUsage]


def service_is_idle(service: FileAgesService) -> bool:
    """Whether *service* keeps no answer, read, or failure."""

    return not (
        service._answers or service._jobs or service._failures  # pyright: ignore[reportPrivateUsage]
    )


async def settled(service: FileAgesService, target: RepositoryStoreTarget, commit: str) -> None:
    """Wait for *commit*'s running read to end; its failure is the service's to record, and a
    cancellation of the waiter is the waiter's."""

    task = service._jobs.get((target.git_dir, commit))  # pyright: ignore[reportPrivateUsage]
    if task is not None:
        await asyncio.wait({task})


def require_file_ages_git() -> tuple[int, int, int]:
    """Return the real Git's version when it reads file ages; otherwise skip, or fail when
    CI named a release that must."""

    require_git()
    availability = file_ages_availability()
    expected = required_admitted_git()
    if availability.available:
        version, _line = detect_git_version()
        assert version is not None
        return version
    if expected is not None:
        parts = tuple(int(part) for part in expected.split(".")[:3])
        padded = (*parts, *([0] * (3 - len(parts))))
        if padded >= FILE_AGES_GIT_MINIMUM:
            pytest.fail(
                f"{REQUIRE_ADMITTED_GIT_ENV}={expected} reads file ages, but "
                f"{availability.version_line or 'no git'!r} answered"
            )
    pytest.skip(
        f"{FILE_AGES_GIT_SKIP}; found {availability.version_line or 'no git'!r}. "
        f"CI sets {REQUIRE_ADMITTED_GIT_ENV} so this cannot skip there."
    )


type FileAgesGitFixture = Callable[[], tuple[int, int, int]]


@pytest.fixture
def file_ages_git() -> Generator[tuple[int, int, int]]:
    """The real Git, for a test of the present path; skipped where it cannot read ages."""

    yield require_file_ages_git()


@pytest.fixture(autouse=True)
def fixed_file_ages_git(request: pytest.FixtureRequest) -> Generator[None]:
    """Every test starts with no kept file ages and, unless it asks for the real Git, with
    the Git of ``PRETEND_GIT_LINE``.

    It patches with a ``MonkeyPatch`` of its own and not the test's ``monkeypatch``: the
    fixture would otherwise be made before every module's autouse fixtures and undone after
    them, and a test's own patch of something such a fixture clears at teardown would still
    be in place when it does.
    """

    reset_file_ages_service()
    with pytest.MonkeyPatch.context() as patch:
        if "file_ages_git" not in request.fixturenames:
            pretend_old_git(patch)
        yield
    reset_file_ages_service()
