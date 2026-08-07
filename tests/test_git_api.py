"""Server-side tests for the ``/api/git/`` endpoint collection.

Fixtures are real repositories built with ``git`` in ``tmp_path`` rather
than captured output. The parsers exist to handle git's actual byte
stream — NUL framing, the newline git writes between the format record
and the first diff entry, rename triples, binary markers — and a
hand-written fixture would drift from that stream without failing.

Every shape a producer emits is run through the runtime validators in
:mod:`metabrowser.git.wire`, the same way ``test_browser_wire_shape.py``
guards the tree contract.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from metabrowser import paths_safe
from metabrowser.git import repo as git_repo
from metabrowser.git.detail import read_commit_detail, translate_repo_path
from metabrowser.git.log import (
    decode_cursor,
    encode_cursor,
    parse_decoration,
    read_log_page,
    read_refs,
)
from metabrowser.git.process import (
    _REPO_PINNING_GIT_VARS,
    GitCommandError,
    GitOutputTooLargeError,
    run_git,
)
from metabrowser.git.repo import repo_info
from metabrowser.git.routes import api_git_commit, api_git_log, api_git_refs, api_git_repo
from metabrowser.git.wire import (
    is_full_revision,
    validate_git_commit,
    validate_git_commit_detail,
    validate_git_log_page,
    validate_git_ref,
    validate_git_repo_info,
)

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git executable is required to build the fixture repositories",
)


# ── Fixture repositories ─────────────────────────────────────


def _git(root: Path, *args: str) -> None:
    """Run a git command in *root*, failing the test on a non-zero exit.

    Identity and config are pinned so the fixtures do not depend on the
    developer's global git configuration — and the repository-pinning
    variables are scrubbed, because when this suite runs from inside a
    githook (the pre-push gate), git has exported ``GIT_DIR`` pointing at
    the *real* repository, and it takes precedence over ``-C``. With it
    inherited, the fixture's ``git init`` re-initializes the served
    repository as bare instead of creating the fixture repo.
    """
    env = {key: value for key, value in os.environ.items() if key not in _REPO_PINNING_GIT_VARS}
    env.update(
        {
            "GIT_AUTHOR_NAME": "Fixture Author",
            "GIT_AUTHOR_EMAIL": "author@example.invalid",
            "GIT_COMMITTER_NAME": "Fixture Committer",
            "GIT_COMMITTER_EMAIL": "committer@example.invalid",
            "GIT_CONFIG_GLOBAL": str(root / ".gitconfig-absent"),
            "GIT_CONFIG_SYSTEM": str(root / ".gitconfig-absent"),
        }
    )
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, env=env)


def _write(root: Path, rel: str, content: str | bytes) -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        target.write_bytes(content)
    else:
        target.write_text(content)


def _build_repo(root: Path) -> None:
    """Build the shared fixture repository.

    Topology, oldest first::

        root commit          a.txt, bin.dat
        rename and binary    a.txt -> renamed.txt, bin.dat rewritten
        ├─ main side commit  side.txt        (on main)
        └─ add subdir        sub/inner.txt   (on feature)
        merge feature        two parents, merged into main

    It deliberately contains every shape the parsers branch on: a root
    commit with no parent, a rename, a binary file, a two-parent merge,
    a tag, and a file below the repository root.
    """
    _git(root, "init", "-q", "-b", "main")
    _write(root, "a.txt", "a\nb\nc\n")
    _write(root, "bin.dat", b"\x00\x01\x02binary")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "root commit")

    _git(root, "mv", "a.txt", "renamed.txt")
    _write(root, "renamed.txt", "a\nb\nc\nd\n")
    _write(root, "bin.dat", b"\x00\x01\x02\x03binary2")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "rename and binary")
    _git(root, "tag", "v1.0")

    _git(root, "checkout", "-q", "-b", "feature")
    _write(root, "sub/inner.txt", "sub\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "add subdir")

    _git(root, "checkout", "-q", "main")
    _write(root, "side.txt", "main side\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "main side commit")
    _git(root, "merge", "-q", "--no-ff", "feature", "-m", "merge feature into main")


@pytest.fixture
def repo(tmp_path: Path) -> Iterator[Path]:
    """A fixture repository, served at its own root."""
    root = tmp_path / "repo"
    root.mkdir()
    _build_repo(root)
    with _served(root):
        yield root


@pytest.fixture
def plain_dir(tmp_path: Path) -> Iterator[Path]:
    """A served root that is not inside any repository."""
    root = tmp_path / "plain"
    root.mkdir()
    (root / "note.txt").write_text("no repo here")
    with _served(root):
        yield root


class _Served:
    """Context manager that points the safe-path layer at *root*."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._previous: Path | None = None

    def __enter__(self) -> Path:
        self._previous = paths_safe.ROOT_DIR
        paths_safe._set_root_dir(self._root)
        git_repo.clear_repo_cache()
        return self._root

    def __exit__(self, *_exc: object) -> None:
        if self._previous is not None:
            paths_safe._set_root_dir(self._previous)
        git_repo.clear_repo_cache()


def _served(root: Path) -> _Served:
    return _Served(root)


class _FakeRequest:
    """Minimal stand-in for a Starlette request.

    The route handlers only read ``query_params`` and ``path_params``, so
    a full request object would add setup without adding coverage.
    """

    def __init__(
        self,
        query_params: dict[str, str] | None = None,
        path_params: dict[str, str] | None = None,
    ) -> None:
        self.query_params: dict[str, str] = query_params or {}
        self.path_params: dict[str, str] = path_params or {}


def _json(response: Any) -> Any:
    import json

    return json.loads(bytes(response.body))


def _subjects(commits: Sequence[Mapping[str, Any]]) -> list[str]:
    return [c["subject"] for c in commits]


def _by_subject(commits: Sequence[Mapping[str, Any]], subject: str) -> Mapping[str, Any]:
    for commit in commits:
        if commit["subject"] == subject:
            return commit
    raise AssertionError(f"no commit with subject {subject!r} in {_subjects(commits)}")


# ── Repository discovery ─────────────────────────────────────


def test_repo_info_reports_a_repository_at_its_own_root(repo: Path) -> None:
    _context, info = asyncio.run(repo_info(repo))
    validate_git_repo_info(dict(info))
    assert info["is_repo"] is True
    # "" rather than None: the served root *is* the repo root.
    assert info["root"] == ""
    head = info["head"]
    assert head is not None
    assert head["ref"] == "refs/heads/main"
    assert head["detached"] is False
    assert head["unborn"] is False
    assert is_full_revision(head["revision"] or "")


def test_repo_info_reports_no_repository_for_a_plain_directory(plain_dir: Path) -> None:
    context, info = asyncio.run(repo_info(plain_dir))
    validate_git_repo_info(dict(info))
    assert context is None
    assert info["is_repo"] is False
    assert info.get("reason") == "not_a_repo"


def test_repo_info_reports_root_none_when_serving_a_subdirectory(repo: Path) -> None:
    with _served(repo / "sub"):
        _context, info = asyncio.run(repo_info(repo / "sub"))
    validate_git_repo_info(dict(info))
    assert info["is_repo"] is True
    # The repo root is above the served root, so it has no representation
    # inside the served tree.
    assert info["root"] is None


def test_repo_info_reports_a_detached_head(repo: Path) -> None:
    _git(repo, "checkout", "-q", "--detach", "HEAD")
    git_repo.clear_repo_cache()
    _context, info = asyncio.run(repo_info(repo))
    validate_git_repo_info(dict(info))
    head = info["head"]
    assert head is not None
    assert head["detached"] is True
    assert head["ref"] is None
    assert is_full_revision(head["revision"] or "")


def test_repo_info_reports_an_unborn_head(tmp_path: Path) -> None:
    root = tmp_path / "empty"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    with _served(root):
        _context, info = asyncio.run(repo_info(root))
    validate_git_repo_info(dict(info))
    assert info["is_repo"] is True
    head = info["head"]
    assert head is not None
    assert head["unborn"] is True
    assert head["revision"] is None
    # An unborn HEAD is still symbolic — it names the branch the first
    # commit will create — so it must not be reported as detached.
    assert head["detached"] is False


def test_repo_info_is_cached_within_the_ttl(repo: Path) -> None:
    first_context, _first = asyncio.run(repo_info(repo))
    second_context, _second = asyncio.run(repo_info(repo))
    assert first_context is not None
    # Identity, not equality: a second discovery would have spawned git
    # again and produced a distinct object.
    assert second_context is first_context


# ── Log pages ────────────────────────────────────────────────


def test_log_page_returns_every_commit_with_parents(repo: Path) -> None:
    page = asyncio.run(read_log_page(repo, skip=0, limit=50))
    validate_git_log_page(dict(page))
    subjects = _subjects(page["commits"])
    assert subjects[0] == "merge feature into main"
    assert set(subjects) == {
        "merge feature into main",
        "main side commit",
        "add subdir",
        "rename and binary",
        "root commit",
    }
    assert page["has_more"] is False
    assert page["cursor"] is None

    merge = _by_subject(page["commits"], "merge feature into main")
    assert len(merge["parent_ids"]) == 2
    root = _by_subject(page["commits"], "root commit")
    assert root["parent_ids"] == []


def test_log_page_parent_ids_reference_commits_in_the_page(repo: Path) -> None:
    # The swimlane layout matches parents against commit ids by string
    # equality, so a parent that does not resolve is a broken lane.
    page = asyncio.run(read_log_page(repo, skip=0, limit=50))
    ids = {c["id"] for c in page["commits"]}
    for commit in page["commits"]:
        for parent in commit["parent_ids"]:
            assert parent in ids, f"{commit['subject']!r} has an unresolvable parent"


def test_log_page_carries_ref_badges(repo: Path) -> None:
    page = asyncio.run(read_log_page(repo, skip=0, limit=50))
    tagged = _by_subject(page["commits"], "rename and binary")
    refs = tagged.get("refs", [])
    for ref in refs:
        validate_git_ref(ref)
    assert {(r["kind"], r["name"]) for r in refs} == {("tag", "v1.0")}

    tip = _by_subject(page["commits"], "merge feature into main")
    tip_refs = tip.get("refs", [])
    head_refs = [r for r in tip_refs if r.get("is_head")]
    assert [r["name"] for r in head_refs] == ["main"]
    # The current branch sorts first so the badge row reads consistently.
    assert tip_refs[0]["name"] == "main"


def test_log_pages_are_contiguous_and_report_has_more(repo: Path) -> None:
    first = asyncio.run(read_log_page(repo, skip=0, limit=2))
    validate_git_log_page(dict(first))
    assert len(first["commits"]) == 2
    assert first["has_more"] is True
    cursor = first["cursor"]
    assert cursor is not None

    skip = decode_cursor(cursor)
    assert skip == 2
    second = asyncio.run(read_log_page(repo, skip=skip, limit=2))
    validate_git_log_page(dict(second))

    # Contiguity is what makes browser-side lane continuity correct: the
    # second page must resume exactly where the first stopped, with no
    # overlap and no gap.
    combined = _subjects(first["commits"]) + _subjects(second["commits"])
    full = _subjects(asyncio.run(read_log_page(repo, skip=0, limit=50))["commits"])
    assert combined == full[:4]


def test_log_page_on_a_repository_with_no_commits(tmp_path: Path) -> None:
    root = tmp_path / "empty"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    with _served(root):
        response = asyncio.run(api_git_log(_FakeRequest()))  # pyright: ignore[reportArgumentType]
    payload = _json(response)
    validate_git_log_page(payload)
    # `git log` exits non-zero on an unborn branch; the route must report
    # the empty history rather than a failure.
    assert response.status_code == 200
    assert payload == {"is_repo": True, "commits": [], "cursor": None, "has_more": False}


def test_cursor_round_trips_and_rejects_junk() -> None:
    assert decode_cursor(encode_cursor(0)) == 0
    assert decode_cursor(encode_cursor(137)) == 137
    for junk in ("", "!!!", "Zm9v", encode_cursor(1)[:-1] + "%"):
        assert decode_cursor(junk) is None or isinstance(decode_cursor(junk), int)
    # A cursor decoding to a negative offset must not reach `--skip`.
    import base64
    import json

    negative = base64.urlsafe_b64encode(json.dumps({"skip": -5}).encode()).decode().rstrip("=")
    assert decode_cursor(negative) is None


# ── Refs ─────────────────────────────────────────────────────


def test_refs_lists_branches_and_tags_with_commit_targets(repo: Path) -> None:
    refs = asyncio.run(read_refs(repo))
    for ref in refs:
        validate_git_ref(ref)
    by_kind = {(r["kind"], r["name"]) for r in refs}
    assert ("branch", "main") in by_kind
    assert ("branch", "feature") in by_kind
    assert ("tag", "v1.0") in by_kind


def test_annotated_tags_resolve_to_the_commit_they_tag(repo: Path) -> None:
    _git(repo, "tag", "-a", "v2.0", "-m", "annotated")
    refs = asyncio.run(read_refs(repo))
    annotated = next(r for r in refs if r["name"] == "v2.0")
    page = asyncio.run(read_log_page(repo, skip=0, limit=50))
    # An annotated tag names a tag object, not a commit. A badge that
    # pointed at the tag object would match no row in the graph.
    assert annotated["revision"] in {c["id"] for c in page["commits"]}


def test_parse_decoration_drops_namespaces_that_are_not_badges() -> None:
    revision = "0" * 40
    refs = parse_decoration(
        "HEAD -> refs/heads/main, refs/stash, refs/notes/commits, tag: refs/tags/v1", revision
    )
    assert [(r["kind"], r["name"]) for r in refs] == [("branch", "main"), ("tag", "v1")]
    assert refs[0].get("is_head") is True


def test_parse_decoration_ignores_a_bare_detached_head_marker() -> None:
    refs = parse_decoration("HEAD, refs/heads/main", "0" * 40)
    # A bare HEAD is the detached marker, not a ref that can be badged;
    # GitHead carries that state instead.
    assert [r["name"] for r in refs] == ["main"]
    assert not any(r.get("is_head") for r in refs)


# ── Commit detail ────────────────────────────────────────────


def _detail_for(repo: Path, subject: str) -> dict[str, Any]:
    context, _info = asyncio.run(repo_info(repo))
    assert context is not None
    page = asyncio.run(read_log_page(repo, skip=0, limit=50))
    commit = _by_subject(page["commits"], subject)
    detail = asyncio.run(read_commit_detail(context, commit["id"]))
    assert detail is not None
    payload: dict[str, Any] = dict(detail)
    validate_git_commit_detail(payload)
    return payload


def test_commit_detail_lists_every_changed_file(repo: Path) -> None:
    detail = _detail_for(repo, "root commit")
    paths = {f["path"] for f in detail["files"]}
    # Regression guard: git writes a newline between the format record
    # and the first diff entry. Mishandling it silently drops the first
    # changed file of every commit — here, a.txt.
    assert paths == {"a.txt", "bin.dat"}
    assert detail["stats"]["files_changed"] == 2


def test_commit_detail_reports_renames_with_the_previous_path(repo: Path) -> None:
    detail = _detail_for(repo, "rename and binary")
    renamed = next(f for f in detail["files"] if f["path"] == "renamed.txt")
    assert renamed["status"] == "renamed"
    assert renamed["old_path"] == "a.txt"
    assert isinstance(renamed["similarity"], int)


def test_commit_detail_reports_binary_files_with_null_counts(repo: Path) -> None:
    detail = _detail_for(repo, "rename and binary")
    binary = next(f for f in detail["files"] if f["path"] == "bin.dat")
    assert binary["binary"] is True
    # None rather than 0: git reports "-", and a zero would read as "a
    # file that changed but gained and lost nothing".
    assert binary["additions"] is None
    assert binary["deletions"] is None


def test_commit_detail_stats_exclude_binary_line_counts(repo: Path) -> None:
    detail = _detail_for(repo, "rename and binary")
    assert detail["stats"]["files_changed"] == 2
    assert detail["stats"]["additions"] == 1
    assert detail["stats"]["deletions"] == 0


def test_merge_commit_diffs_against_its_first_parent(repo: Path) -> None:
    detail = _detail_for(repo, "merge feature into main")
    # Git's default for a merge is a combined diff, which is empty for an
    # ordinary merge. First-parent is what makes the file list useful.
    assert [f["path"] for f in detail["files"]] == ["sub/inner.txt"]
    assert detail["files"][0]["status"] == "added"


def test_commit_detail_splits_subject_from_body(repo: Path) -> None:
    _write(repo, "msg.txt", "x\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "subject line\n\nbody first\nbody second\n")
    git_repo.clear_repo_cache()
    detail = _detail_for(repo, "subject line")
    assert detail["body"] == "body first\nbody second"


def test_commit_detail_reports_truncation_without_understating_stats(repo: Path) -> None:
    for index in range(6):
        _write(repo, f"many/f{index}.txt", f"line {index}\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "many files")
    git_repo.clear_repo_cache()

    context, _info = asyncio.run(repo_info(repo))
    assert context is not None
    page = asyncio.run(read_log_page(repo, skip=0, limit=5))
    commit = _by_subject(page["commits"], "many files")
    detail = asyncio.run(read_commit_detail(context, commit["id"], max_files=2))
    assert detail is not None
    payload: dict[str, Any] = dict(detail)
    validate_git_commit_detail(payload)

    assert payload["files_truncated"] is True
    assert len(payload["files"]) == 2
    # Stats describe the whole commit, so the count must survive the cut.
    assert payload["stats"]["files_changed"] == 6


# ── Path translation ─────────────────────────────────────────


def test_paths_are_served_root_relative_when_serving_a_subdirectory(repo: Path) -> None:
    with _served(repo / "sub"):
        context, _info = asyncio.run(repo_info(repo / "sub"))
        assert context is not None
        page = asyncio.run(read_log_page(repo / "sub", skip=0, limit=50))
        inside = _by_subject(page["commits"], "add subdir")
        detail = asyncio.run(read_commit_detail(context, inside["id"]))
        assert detail is not None
        payload: dict[str, Any] = dict(detail)
        validate_git_commit_detail(payload)

        change = payload["files"][0]
        # Git reported "sub/inner.txt"; the browser must receive a path it
        # can hand straight to openPath.
        assert change["path"] == "inner.txt"
        assert "outside_root" not in change


def test_files_outside_the_served_root_are_flagged_not_hidden(repo: Path) -> None:
    with _served(repo / "sub"):
        context, _info = asyncio.run(repo_info(repo / "sub"))
        assert context is not None
        page = asyncio.run(read_log_page(repo / "sub", skip=0, limit=50))
        outside = _by_subject(page["commits"], "main side commit")
        detail = asyncio.run(read_commit_detail(context, outside["id"]))
        assert detail is not None
        payload: dict[str, Any] = dict(detail)
        validate_git_commit_detail(payload)

        change = payload["files"][0]
        # Present and honest about what the commit touched, but flagged so
        # the browser renders it inert rather than linking somewhere the
        # safe-path layer would refuse.
        assert change["path"] == "side.txt"
        assert change["outside_root"] is True


def test_translate_repo_path_keeps_the_repo_relative_path_when_outside(repo: Path) -> None:
    context, _info = asyncio.run(repo_info(repo))
    assert context is not None
    served_sub = type(context)(
        git_root=context.git_root, served_root=repo / "sub", head=context.head
    )
    path, outside = translate_repo_path("side.txt", served_sub)
    assert (path, outside) == ("side.txt", True)
    path, outside = translate_repo_path("sub/inner.txt", served_sub)
    assert (path, outside) == ("inner.txt", False)


# ── Process bounds ───────────────────────────────────────────


def test_run_git_raises_on_a_non_zero_exit(repo: Path) -> None:
    with pytest.raises(GitCommandError) as excinfo:
        asyncio.run(run_git(["rev-parse", "--verify", "definitely-not-a-ref"], cwd=repo))
    assert excinfo.value.returncode != 0


def test_run_git_enforces_the_output_cap(repo: Path) -> None:
    with pytest.raises(GitOutputTooLargeError):
        asyncio.run(run_git(["log", "--format=%H%n%s"], cwd=repo, max_bytes=8))


def test_run_git_ignores_a_hook_exported_git_dir(repo: Path, tmp_path: Path) -> None:
    """A leaked ``GIT_DIR`` must not redirect commands away from ``cwd``.

    Githooks run with ``GIT_DIR`` exported, and it outranks the working
    directory. Without the scrub in ``_git_env`` this exact scenario
    re-initialized the served repository as bare from inside the pre-push
    gate: the fixture's ``git init`` landed on the hook's repository
    instead of the fixture directory.
    """
    decoy = tmp_path / "decoy"
    decoy.mkdir()
    _git(decoy, "init", "-q", "-b", "main")

    poisoned = {**os.environ, "GIT_DIR": str(decoy / ".git")}
    with mock.patch.dict(os.environ, poisoned, clear=True):
        out = asyncio.run(run_git(["rev-parse", "--show-toplevel"], cwd=repo))
    # The answer must be the repo at cwd, not the decoy GIT_DIR names.
    assert Path(out.decode().strip()).resolve() == repo.resolve()


def test_run_git_returns_bytes_not_text(repo: Path) -> None:
    # Path names are raw bytes in whatever encoding the filesystem uses;
    # decoding belongs to the parsers, which choose the error policy.
    out = asyncio.run(run_git(["rev-parse", "HEAD"], cwd=repo))
    assert isinstance(out, bytes)


# ── Routes ───────────────────────────────────────────────────


def test_route_repo_returns_the_gate_envelope(repo: Path) -> None:
    response = asyncio.run(api_git_repo(_FakeRequest()))  # pyright: ignore[reportArgumentType]
    assert response.status_code == 200
    payload = _json(response)
    validate_git_repo_info(payload)
    assert payload["is_repo"] is True


def test_routes_return_the_negative_envelope_outside_a_repository(plain_dir: Path) -> None:
    for handler in (api_git_repo, api_git_refs, api_git_log):
        response = asyncio.run(handler(_FakeRequest()))  # pyright: ignore[reportArgumentType]
        payload = _json(response)
        # 200, not 4xx: "not a repository" is an ordinary state of the
        # world, and a 4xx would put it in the browser's error path.
        assert response.status_code == 200, handler.__name__
        assert payload["is_repo"] is False, handler.__name__


def test_route_log_clamps_an_out_of_range_limit(repo: Path) -> None:
    for raw_limit in ("0", "-3", "999999999", "not-a-number"):
        response = asyncio.run(
            api_git_log(_FakeRequest({"limit": raw_limit}))  # pyright: ignore[reportArgumentType]
        )
        assert response.status_code == 200, raw_limit
        payload = _json(response)
        validate_git_log_page(payload)
        assert len(payload["commits"]) >= 1, raw_limit


def test_route_log_treats_a_malformed_cursor_as_the_first_page(repo: Path) -> None:
    response = asyncio.run(
        api_git_log(_FakeRequest({"cursor": "!!!not-a-cursor"}))  # pyright: ignore[reportArgumentType]
    )
    # Restarting is recoverable; a 400 mid-scroll would strand the panel
    # with no way forward.
    assert response.status_code == 200
    payload = _json(response)
    validate_git_log_page(payload)
    assert payload["commits"][0]["subject"] == "merge feature into main"


@pytest.mark.parametrize(
    "revision",
    [
        "",
        "HEAD",
        "HEAD~1",
        "main@{upstream}",
        "0" * 39,
        "0" * 41,
        "0" * 39 + "G",
        "--upload-pack=touch /tmp/pwned",
        "../../etc/passwd",
    ],
)
def test_route_commit_rejects_anything_but_a_full_sha(repo: Path, revision: str) -> None:
    response = asyncio.run(
        api_git_commit(_FakeRequest(path_params={"revision": revision}))  # pyright: ignore[reportArgumentType]
    )
    # The gate runs before the value can reach an argument vector, so a
    # revision expression or an option-looking string never gets to git.
    assert response.status_code == 400
    # The caller-controlled value is never echoed into a message the
    # browser renders. (The empty case is vacuous for a substring test.)
    if revision:
        assert revision not in _json(response)["error"]


def test_route_commit_returns_404_for_an_unknown_object(repo: Path) -> None:
    response = asyncio.run(
        api_git_commit(_FakeRequest(path_params={"revision": "0" * 40}))  # pyright: ignore[reportArgumentType]
    )
    assert response.status_code == 404


def test_route_commit_returns_detail_for_a_known_commit(repo: Path) -> None:
    page = asyncio.run(read_log_page(repo, skip=0, limit=1))
    revision = page["commits"][0]["id"]
    response = asyncio.run(
        api_git_commit(_FakeRequest(path_params={"revision": revision}))  # pyright: ignore[reportArgumentType]
    )
    assert response.status_code == 200
    payload = _json(response)
    validate_git_commit_detail(payload)
    assert payload["commit"]["id"] == revision


def test_route_error_bodies_never_leak_local_paths(repo: Path, tmp_path: Path) -> None:
    response = asyncio.run(
        api_git_commit(_FakeRequest(path_params={"revision": "0" * 40}))  # pyright: ignore[reportArgumentType]
    )
    body = bytes(response.body).decode()
    # Git writes absolute local paths into its error text; none of it may
    # reach the client.
    assert str(tmp_path) not in body
    assert str(repo) not in body


# ── Wire validators ──────────────────────────────────────────


def test_validator_rejects_an_abbreviated_commit_id() -> None:
    commit = {
        "id": "abc1234",
        "short_id": "abc1234",
        "parent_ids": [],
        "author": {"name": "n", "email": "e"},
        "authored_at": 0.0,
        "committed_at": 0.0,
        "subject": "s",
    }
    with pytest.raises(AssertionError, match="full 40-hex"):
        validate_git_commit(commit)


def test_validator_rejects_has_more_without_a_cursor() -> None:
    with pytest.raises(AssertionError, match="nothing to page with"):
        validate_git_log_page({"is_repo": True, "commits": [], "has_more": True, "cursor": None})


def test_validator_rejects_a_binary_file_with_numeric_counts() -> None:
    detail = {
        "is_repo": True,
        "commit": {
            "id": "0" * 40,
            "short_id": "0000000",
            "parent_ids": [],
            "author": {"name": "n", "email": "e"},
            "authored_at": 0.0,
            "committed_at": 0.0,
            "subject": "s",
        },
        "body": "",
        "stats": {"files_changed": 1, "additions": 0, "deletions": 0},
        "files": [
            {"path": "b.dat", "status": "modified", "additions": 0, "deletions": 0, "binary": True}
        ],
        "files_truncated": False,
    }
    with pytest.raises(AssertionError, match="binary"):
        validate_git_commit_detail(detail)
