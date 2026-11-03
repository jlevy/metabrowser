"""Only recent observed IDs of this store and exact comparison authorize recovery."""

from pathlib import Path

import pytest

from metabrowser.git import object_failures as module
from metabrowser.git.object_failures import ObjectFailures
from metabrowser.git.process import GitCommandError, RepositoryStoreTarget
from metabrowser.git.tree_source import GitObjectCorruptError, GitObjectUnavailableError


def test_observations_are_isolated_bounded_expiring_and_disposable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = [1000.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    target = RepositoryStoreTarget(tmp_path / "one.git", "sha1")
    other = RepositoryStoreTarget(tmp_path / "two.git", "sha1")
    commits = ("a" * 40, "b" * 40)
    seen = ObjectFailures()
    first = seen.remember(target, commits, GitObjectUnavailableError("c" * 40))
    assert first is not None
    assert seen.pending(other, commits) == ()
    assert seen.pending(target, tuple(reversed(commits))) == ()
    newer = seen.remember(target, commits, GitObjectCorruptError(first.oid))
    seen.verified(target, commits, first)
    assert seen.pending(target, commits) == (newer,)
    assert newer is not None
    seen.verified(target, commits, newer)
    assert seen.pending(target, commits) == ()
    for number in range(module.MAX_FAILED_OBJECTS + 1):
        seen.remember(target, commits, GitObjectUnavailableError(f"{number:040x}"))
    assert len(seen.pending(target, commits)) == module.MAX_FAILED_OBJECTS
    assert seen.pending(target, commits)[0].oid == f"{1:040x}"
    clock[0] += module.FAILURE_TTL_S + 1
    assert seen.pending(target, commits) == ()
    for number in range(module.MAX_FAILED_COMPARISONS + 1):
        seen.remember(target, (f"{number:040x}",), GitObjectUnavailableError("c" * 40))
    assert seen.pending(target, (f"{0:040x}",)) == ()
    assert seen.pending(target, (f"{1:040x}",))
    seen.forget_store(target)
    assert seen.pending(target, (f"{1:040x}",)) == ()


@pytest.mark.parametrize(
    "prefix", ["fatal: unable to read ", "error: Could not read ", "fatal: bad object "]
)
@pytest.mark.parametrize("width", [40, 64])
def test_only_known_complete_object_diagnostics_are_retained(
    tmp_path: Path, prefix: str, width: int
) -> None:
    target = RepositoryStoreTarget(tmp_path / "store.git", "sha1")
    commits = ("a" * width, "b" * width)
    seen = ObjectFailures()
    oid = "c" * width
    for message in (
        prefix + oid + "-path",
        "path mentions " + oid,
        prefix + oid[:12],
        "private/path/" + prefix + oid,
    ):
        assert seen.remember(target, commits, GitCommandError([], 128, message)) is None
    failure = seen.remember(target, commits, GitCommandError([], 128, prefix + oid + "\n"))
    assert failure is not None and failure.oid == oid
