"""A change's size as Git pushes it and as a patch (``metabrowser.git.change_size``).

Holds the claims its module makes: the size is the thin pack and the patch Git itself
writes, it does not move with the reader's or the repository's configuration, it is
measured once and then kept, beside a repository store too, and what cannot be known is
answered ``unknown`` with its reason rather than as a wrong number.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from metabrowser.git import change_size as sizes
from metabrowser.git import repo as git_repo
from metabrowser.git.process import GitLocation, repository_store_target, run_git_at
from metabrowser.git.wire import GitChangeSize, validate_git_change_size
from tests.required_tools import needs_git

pytestmark = needs_git

STORE_KEY = "github-com-octo-demo-" + "ab" * 5 + "a"


@pytest.fixture(autouse=True)
def _fresh_sizes() -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    sizes.clear_kept_sizes()
    yield
    sizes.clear_kept_sizes()


def _env(root: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(
        {
            "GIT_AUTHOR_NAME": "Size",
            "GIT_AUTHOR_EMAIL": "size@example.invalid",
            "GIT_COMMITTER_NAME": "Size",
            "GIT_COMMITTER_EMAIL": "size@example.invalid",
            "GIT_AUTHOR_DATE": "2026-01-01T00:00:00 +0000",
            "GIT_COMMITTER_DATE": "2026-01-01T00:00:00 +0000",
            "GIT_CONFIG_GLOBAL": str(root / ".gitconfig-absent"),
            "GIT_CONFIG_SYSTEM": str(root / ".gitconfig-absent"),
        }
    )
    return env


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, env=_env(cwd.parent), check=True, capture_output=True, text=True
    ).stdout.strip()


def _repository(root: Path) -> Path:
    """A history of four commits: a root, a large file, a one-line edit, and a merge."""

    work = root / "work"
    work.mkdir()
    _git(work, "init", "-q", "--initial-branch=main")
    (work / "README.md").write_text("# Sizes\n")
    _git(work, "add", ".")
    _git(work, "commit", "-qm", "root")
    (work / "numbers.txt").write_text("".join(f"{n}\n" for n in range(1, 4001)))
    _git(work, "add", ".")
    _git(work, "commit", "-qm", "numbers")
    _git(work, "checkout", "-qb", "topic")
    (work / "numbers.txt").write_text(
        (work / "numbers.txt").read_text().replace("\n2000\n", "\ntwo thousand\n")
    )
    _git(work, "commit", "-qam", "one line")
    (work / "notes.txt").write_text("a note\n")
    _git(work, "add", ".")
    _git(work, "commit", "-qm", "a note")
    _git(work, "checkout", "-q", "main")
    _git(work, "merge", "-q", "--no-ff", "-m", "merge topic", "topic")
    return work


def _rev(work: Path, revision: str) -> str:
    return _git(work, "rev-parse", revision)


def _independent(work: Path, base: str | None, head: str) -> tuple[int, int]:
    """The two sizes, as Git writes them with the module's own pinned options."""

    revisions = f"{head}\n" + (f"^{base}\n" if base else "")
    pack = subprocess.run(
        ["git", *sizes.PACK_ARGS],
        cwd=work,
        env=_env(work.parent),
        input=revisions.encode(),
        check=True,
        capture_output=True,
    ).stdout
    old = base or "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
    patch = subprocess.run(
        ["git", *sizes.DIFF_ARGS, old, head, "--"],
        cwd=work,
        env=_env(work.parent),
        check=True,
        capture_output=True,
    ).stdout
    return len(pack), len(patch)


def _measure(location: GitLocation, revision: str) -> GitChangeSize:
    size = asyncio.run(sizes.commit_size(location, revision))
    assert size is not None
    validate_git_change_size(size)
    return size


def test_a_commit_is_its_thin_pack_and_its_patch(tmp_path: Path) -> None:
    work = _repository(tmp_path)
    location = GitLocation.filesystem(work)
    edit = _rev(work, "topic~1")
    size = _measure(location, edit)
    assert size["state"] == "measured"
    assert size["base"] == _rev(work, "topic~2")
    assert size["commits"] == 1
    assert (size["pushed_bytes"], size["diff_bytes"]) == _independent(work, size["base"], edit)
    # A one-line edit of a 19 KB file pushes a delta, not the file.
    assert size["pushed_bytes"] is not None and size["pushed_bytes"] < 1_000


def test_a_root_commit_is_measured_against_nothing(tmp_path: Path) -> None:
    work = _repository(tmp_path)
    root = _rev(work, "main~1~1")
    size = _measure(GitLocation.filesystem(work), root)
    assert size["base"] is None and size["commits"] == 1
    assert (size["pushed_bytes"], size["diff_bytes"]) == _independent(work, None, root)


def test_a_merge_is_measured_against_its_first_parent(tmp_path: Path) -> None:
    work = _repository(tmp_path)
    merge = _rev(work, "main")
    size = _measure(GitLocation.filesystem(work), merge)
    assert size["base"] == _rev(work, "main^1")
    # The merge and the two commits it brought in.
    assert size["commits"] == 3
    assert (size["pushed_bytes"], size["diff_bytes"]) == _independent(work, size["base"], merge)


def test_the_repository_configuration_does_not_move_a_size(tmp_path: Path) -> None:
    work = _repository(tmp_path)
    merge = _rev(work, "main")
    before = _measure(GitLocation.filesystem(work), merge)
    sizes.clear_kept_sizes()
    for setting, value in (
        ("core.compression", "0"),
        ("pack.compression", "9"),
        ("pack.window", "0"),
        ("diff.algorithm", "patience"),
        ("diff.context", "10"),
        ("diff.noprefix", "true"),
        ("diff.renames", "false"),
        ("core.quotePath", "false"),
    ):
        _git(work, "config", setting, value)
    _git(work, "repack", "-adq", "--window=0")
    assert _measure(GitLocation.filesystem(work), merge) == before


def test_an_unknown_commit_is_none_and_a_failure_is_not_kept(tmp_path: Path) -> None:
    work = _repository(tmp_path)
    location = GitLocation.filesystem(work)
    assert asyncio.run(sizes.commit_size(location, "0" * 40)) is None


def test_a_measured_size_is_kept_and_not_measured_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work = _repository(tmp_path)
    location = GitLocation.filesystem(work)
    edit = _rev(work, "topic~1")
    first = _measure(location, edit)

    async def refuse(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("a kept size ran Git")

    monkeypatch.setattr(sizes, "spawn_git_at", refuse)
    monkeypatch.setattr(sizes, "run_git_at", refuse)
    # Kept by the commits alone: another repository holding them answers too.
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(work), str(other)], env=_env(tmp_path), check=True)
    assert _measure(GitLocation.filesystem(other), edit) == first


def test_concurrent_asks_share_one_measurement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work = _repository(tmp_path)
    location = GitLocation.filesystem(work)
    merge = _rev(work, "main")
    calls = 0
    measure = sizes.measure_change

    async def counted(*args: object) -> GitChangeSize:
        nonlocal calls
        calls += 1
        return await measure(*args)  # pyright: ignore[reportArgumentType]

    monkeypatch.setattr(sizes, "measure_change", counted)

    async def ask() -> list[GitChangeSize | None]:
        return list(await asyncio.gather(*(sizes.commit_size(location, merge) for _ in range(5))))

    answers = asyncio.run(ask())
    assert calls == 1
    assert all(answer == answers[0] for answer in answers)


def _shallow(tmp_path: Path) -> tuple[Path, Path]:
    work = _repository(tmp_path)
    shallow = tmp_path / "shallow"
    subprocess.run(
        ["git", "clone", "-q", "--depth=2", "--no-single-branch", work.as_uri(), str(shallow)],
        env=_env(tmp_path),
        check=True,
        capture_output=True,
    )
    return work, shallow


def test_a_commit_at_a_shallow_boundary_is_parent_unavailable(tmp_path: Path) -> None:
    work, shallow = _shallow(tmp_path)
    # Two deep from main's tip, its first parent is at the boundary.
    size = _measure(GitLocation.filesystem(shallow), _rev(work, "main~1"))
    assert size["state"] == "unknown" and size["reason"] == "parent_unavailable"


def test_a_missing_base_is_objects_unavailable(tmp_path: Path) -> None:
    work, shallow = _shallow(tmp_path)
    size = asyncio.run(
        sizes.measure_change(
            GitLocation.filesystem(shallow), _rev(work, "main~1~1"), _rev(work, "main")
        )
    )
    assert size["state"] == "unknown" and size["reason"] == "objects_unavailable"


def test_a_walk_across_a_shallow_boundary_is_history_unavailable(tmp_path: Path) -> None:
    work, shallow = _shallow(tmp_path)
    location = GitLocation.filesystem(shallow)
    # main's first parent is here, at the boundary; the merge also reaches topic's tip,
    # which is at the boundary too, so a pack of the walk would hold its whole tree.
    size = asyncio.run(sizes.measure_change(location, _rev(work, "main^1"), _rev(work, "main")))
    validate_git_change_size(size)
    assert size["state"] == "unknown" and size["reason"] == "history_unavailable"


def test_too_costly_is_kept_in_memory_under_its_location(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work = _repository(tmp_path)
    location = GitLocation.filesystem(work)
    edit = _rev(work, "topic~1")
    monkeypatch.setattr(sizes, "MEASURE_TIMEOUT_S", 0.0)
    assert _measure(location, edit)["reason"] == "too_costly"
    monkeypatch.setattr(sizes, "MEASURE_TIMEOUT_S", 15.0)
    assert _measure(location, edit)["reason"] == "too_costly"
    # Another repository holding the commit measures it afresh.
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(work), str(other)], env=_env(tmp_path), check=True)
    assert _measure(GitLocation.filesystem(other), edit)["state"] == "measured"


def _store(tmp_path: Path) -> tuple[Path, Path, GitLocation]:
    """A bare copy of the history laid out as a cache's repository store."""

    work = _repository(tmp_path)
    home = tmp_path / "cache"
    git_dir = home / "repos" / STORE_KEY / "repository.git"
    git_dir.parent.mkdir(parents=True)
    for directory in (home, home / "repos", git_dir.parent):
        directory.chmod(0o700)
    subprocess.run(
        ["git", "clone", "-q", "--bare", "--template=", str(work), str(git_dir)],
        env=_env(tmp_path),
        check=True,
        capture_output=True,
    )
    location = GitLocation.revision(repository_store_target(git_dir=git_dir), _rev(work, "main"))
    return work, home, location


def test_a_store_keeps_sizes_beside_it_for_a_fresh_server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from metabrowser.cache.identity import is_store_key

    assert is_store_key(STORE_KEY)
    work, home, location = _store(tmp_path)
    merge = _rev(work, "main")
    measured = _measure(location, merge)
    bank = home / "repos" / STORE_KEY / sizes.BANK_DIRECTORY / f"{merge[:2]}.json"
    record = json.loads(bank.read_bytes())
    assert record["measure"] == sizes.MEASURE
    assert oct(bank.stat().st_mode & 0o777) == oct(0o600)

    sizes.clear_kept_sizes()

    async def refuse(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("a banked size ran Git")

    monkeypatch.setattr(sizes, "spawn_git_at", refuse)
    monkeypatch.setattr(sizes, "run_git_at", refuse)
    assert _measure(location, merge) == measured


def test_a_bank_written_for_other_options_or_corrupt_is_a_miss(tmp_path: Path) -> None:
    work, home, location = _store(tmp_path)
    merge = _rev(work, "main")
    measured = _measure(location, merge)
    bank = home / "repos" / STORE_KEY / sizes.BANK_DIRECTORY / f"{merge[:2]}.json"
    record = json.loads(bank.read_bytes())
    for spoiled in (
        json.dumps({**record, "measure": "another"}).encode(),
        b"{not json",
        json.dumps({**record, "sizes": {k: [None, -1, 2, 3] for k in record["sizes"]}}).encode(),
    ):
        bank.write_bytes(spoiled)
        sizes.clear_kept_sizes()
        assert _measure(location, merge) == measured


def test_a_folder_keeps_nothing_beside_its_repository(tmp_path: Path) -> None:
    work = _repository(tmp_path)
    _measure(GitLocation.filesystem(work), _rev(work, "main"))
    assert not list(tmp_path.rglob(sizes.BANK_DIRECTORY))


def test_bank_file_stays_under_its_read_bound(tmp_path: Path) -> None:
    """A full file of SHA-256 entries, the larger IDs, fits the bound it is read under."""

    _work, home, location = _store(tmp_path)
    bank = sizes._StoreBank.for_location(location)  # pyright: ignore[reportPrivateUsage]
    assert bank is not None
    head = "ab" + "0" * 62
    for at in range(sizes.MAX_BANK_FILE_ENTRIES + 10):
        base = f"{at:064x}"
        big = 10**12
        bank.write(
            ("range", base, head),
            sizes.measured(base, head, big, big, big),
        )
    data = (home / "repos" / STORE_KEY / sizes.BANK_DIRECTORY / "ab.json").read_bytes()
    assert len(json.loads(data)["sizes"]) == sizes.MAX_BANK_FILE_ENTRIES
    # Measured 2026-11-20: 66.4 KB, the most a file holds, against a bound about twice that.
    assert len(data) < sizes.MAX_BANK_FILE_BYTES
    # The oldest went first.
    assert bank.read(("range", f"{0:064x}", head)) is None
    assert bank.read(("range", f"{sizes.MAX_BANK_FILE_ENTRIES + 9:064x}", head)) is not None


def test_a_pull_request_is_its_head_against_the_merge_base(tmp_path: Path) -> None:
    work, _home, location = _store(tmp_path)
    topic, main = _rev(work, "topic"), _rev(work, "main~1")
    size = asyncio.run(sizes.pull_change_size(location, main, topic))
    validate_git_change_size(size)
    base = size["base"]
    assert base is not None
    assert base == _rev(work, "topic~2") and size["commits"] == 2
    assert (size["pushed_bytes"], size["diff_bytes"]) == _independent(work, base, topic)
    # The row's summary reads it from what is kept, with no Git.
    assert sizes.kept_change_size(location, base, topic) == size


def test_pack_objects_at_a_store_must_write_to_stdout(tmp_path: Path) -> None:
    _work, _home, location = _store(tmp_path)
    with pytest.raises(ValueError, match="--stdout"):
        asyncio.run(run_git_at(["pack-objects", "--revs", "pack"], location))


class _Request:
    """The one part of a request the route reads."""

    def __init__(self, revision: str) -> None:
        self.path_params = {"revision": revision}


def test_the_commit_size_route(tmp_path: Path) -> None:
    from metabrowser import paths_safe
    from metabrowser.git.routes import api_git_commit_size

    work = _repository(tmp_path)
    previous = paths_safe.ROOT_DIR
    paths_safe._set_root_dir(work)  # pyright: ignore[reportPrivateUsage]
    git_repo.clear_repo_cache()

    def ask(revision: str) -> tuple[int, dict[str, object]]:
        answer = asyncio.run(api_git_commit_size(_Request(revision)))  # pyright: ignore[reportArgumentType]
        return answer.status_code, json.loads(bytes(answer.body))

    try:
        status, body = ask(_rev(work, "main"))
        assert status == 200 and body["is_repo"] is True
        size = body["size"]
        assert isinstance(size, dict)
        validate_git_change_size(size)  # pyright: ignore[reportUnknownArgumentType]
        assert size["commits"] == 3
        assert ask("0" * 40) == (404, {"error": "unknown revision", "code": "commit_not_found"})
        assert ask("main")[0] == 400
    finally:
        paths_safe._set_root_dir(previous)  # pyright: ignore[reportPrivateUsage]
        git_repo.clear_repo_cache()
