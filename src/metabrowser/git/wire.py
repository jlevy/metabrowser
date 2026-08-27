"""Wire-shape definitions for the ``/api/git/`` endpoints.

Single source of truth for the JSON the Git panel consumes, in the same
spirit as :mod:`metabrowser.wire_models` for the tree and recent
endpoints: TypedDicts describe the shape, and runtime validators let the
tests assert every shape a producer can emit so drift fails the suite
rather than the browser.

Convention
----------

* Conditional keys are marked ``NotRequired`` rather than the whole
  TypedDict being ``total=False``. :mod:`metabrowser.wire_models` uses
  the older form because it predates the syntax; here the required keys
  are required to the type checker as well as to the validators, so a
  producer that forgets one fails at check time instead of only in the
  test that happens to exercise that shape.
* The ``_*_REQUIRED`` gate sets below still exist because the validators
  run against plain ``dict``s parsed from JSON, where the static types
  are gone. Keep them in sync with the class bodies.
* Timestamps are epoch seconds as ``float``, matching ``mtime`` in the
  tree wire model, so the browser has one time convention to handle.
* Revisions are full object ids: 40 hexadecimal characters for SHA-1
  repositories and 64 for SHA-256 repositories. ``short_id`` carries
  the abbreviation git itself chose, which respects the repository's
  ``core.abbrev`` and grows as the repository does — recomputing it
  client-side by truncating would eventually collide.
* Paths in :class:`GitFileChange` are served-root-relative, like every
  other path Metabrowser puts on the wire. The one exception is flagged:
  see :attr:`GitFileChange.outside_root`.

What is deliberately absent
---------------------------

No swimlane, lane color, or row-geometry field appears here. Lane
assignment is a pure function of the commit list and its ordering and is
naturally incremental across pages, so it belongs to the rendering layer
— the same call :mod:`metabrowser.recent` made when it left cluster
construction to the browser. See ``static/git-graph.js``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Literal, NotRequired, TypedDict

# A full Git object name: exactly 40 or 64 lowercase hex characters.
#
# Every revision that reaches an argument vector is matched against this
# first. Abbreviations are rejected on purpose, even though git would
# accept them: the pattern is what guarantees a caller-supplied value can
# never be read as an option (``--upload-pack=…``), a revision expression
# (``HEAD~3``, ``main@{upstream}``), or a pathspec. The browser always has
# the full id, because every commit it renders came from
# :class:`GitLogPage`.
_FULL_REVISION_RE = re.compile(r"\A(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")


def is_full_revision(value: str) -> bool:
    """True iff *value* is a full SHA-1 or SHA-256 lowercase object id.

    The gate every route applies before a revision reaches
    :func:`metabrowser.git.process.run_git`.
    """
    return bool(_FULL_REVISION_RE.match(value))


class GitRef(TypedDict):
    """A reference pointing at a commit: branch, remote branch, or tag."""

    # Full refname, e.g. "refs/heads/main". Stable identity; the browser
    # keys on this rather than on `name`, which is ambiguous across kinds
    # (a branch and a tag may share a short name).
    id: str
    # Short display name: "main", "<remote>/<branch>", "v1.0".
    name: str
    kind: Literal["branch", "remote", "tag"]
    # Full SHA this ref resolves to.
    revision: str
    # Conditional: true for the ref HEAD is currently on. At most one ref
    # in a response carries it, and never when HEAD is detached.
    is_head: NotRequired[bool]
    # Conditional: true for the branch the repository merges into — main
    # or master, local or on a tracked remote. Decided server-side from
    # the same names that scope the history walk, so "what counts as
    # trunk" has one definition rather than one per surface.
    is_trunk: NotRequired[bool]
    # Conditional: remote name ("origin") when kind == "remote".
    remote: NotRequired[str]


class GitAuthor(TypedDict):
    """Commit author identity, as recorded in the commit object."""

    name: NotRequired[str]
    email: NotRequired[str]


class GitCommit(TypedDict):
    """One commit, carrying exactly what the graph needs to draw a row.

    ``parent_ids`` is the field the swimlane layout runs on; ``[0]`` is
    the first parent, and order is significant — it is what makes the
    merge lanes land on the correct side.
    """

    id: str
    short_id: str
    parent_ids: list[str]
    author: GitAuthor
    authored_at: float
    committed_at: float
    # First line of the commit message. The remainder is only fetched
    # with the commit detail; a log page carrying full message bodies
    # would be many times larger for text the rows cannot show.
    subject: str
    # Conditional: decorations resolved at this commit, in display order
    # (HEAD first, then local branches, remotes, tags).
    refs: NotRequired[list[GitRef]]


class GitHead(TypedDict):
    """Where HEAD points.

    The three states are distinct and the browser renders each
    differently: on a branch (``ref`` set), detached (``detached``), and
    unborn — a repository initialized but with no commit yet, where
    ``revision`` is ``None`` and the graph is legitimately empty.
    """

    ref: str | None
    revision: str | None
    detached: bool
    unborn: bool


class GitRepoInfo(TypedDict):
    """Repository identity — the gate for the whole feature.

    When ``is_repo`` is false the browser does not render the Git tab at
    all, and the other endpoints return this same negative envelope
    rather than an error: "not a repository" and "git is not installed"
    are ordinary conditions, not failures.
    """

    is_repo: bool
    # Always "" for a positive response because the feature is enabled
    # only when the served root is the repository root; None otherwise.
    root: str | None
    head: GitHead | None
    # Conditional: why is_repo is false, as a stable machine-readable
    # token ("no_git", "not_a_repo", "not_repo_root", "git_failed").
    # Diagnostics only — the browser branches on is_repo.
    reason: NotRequired[str]


class GitRefList(TypedDict):
    """Response shape for ``GET /api/git/refs``."""

    is_repo: bool
    refs: list[GitRef]


class GitLogPage(TypedDict):
    """Response shape for ``GET /api/git/log``.

    ``cursor`` is the opaque next-page token. The page and previous-page
    tokens make an evicted client page replayable from the same bounded
    server session without walking its prefix again. Callers never
    construct a token.
    """

    is_repo: bool
    commits: list[GitCommit]
    cursor: str | None
    has_more: bool
    page: NotRequired[int]
    page_cursor: NotRequired[str]
    previous_cursor: NotRequired[str | None]
    scope: NotRequired[Literal["default", "all"]]
    scope_refs: NotRequired[list[str]]
    scope_fingerprint: NotRequired[str]


class GitFileChange(TypedDict):
    """One file touched by a commit."""

    # Served-root-relative, so it can be handed straight to openPath —
    # unless `outside_root` is set, in which case this is the path
    # relative to the repository root and is not navigable.
    path: str
    # Conditional: the pre-rename/copy path, same convention as `path`.
    old_path: NotRequired[str]
    status: Literal["added", "modified", "deleted", "renamed", "copied", "typechanged"]
    # None for binary files: git reports "-" rather than a line count.
    additions: int | None
    deletions: int | None
    # Conditional: present and true only for binary files.
    binary: NotRequired[bool]
    # Conditional: the file is inside the repository but outside the
    # served root, so Metabrowser will not open it. The browser renders
    # these inert. Serving them would be a containment violation; hiding
    # them would misreport what the commit changed.
    outside_root: NotRequired[bool]
    # Conditional: rename/copy similarity score git reported (0-100).
    similarity: NotRequired[int]


class GitCommitStats(TypedDict):
    """Aggregate file-status and line counts for a commit.

    Counts come from the same numstat pass that produces the file list,
    so they always agree with it. Binary files contribute to
    ``files_changed`` and one status family but not to the line counts.
    """

    files_changed: int
    files_modified: int
    files_added: int
    files_deleted: int
    additions: int
    deletions: int


class GitCommitDetail(TypedDict):
    """Response shape for ``GET /api/git/commit/{revision}``.

    Backs both the hover card and the detail view, which is why it is one
    request rather than two: hovering a row then selecting it must not
    cost two round trips.
    """

    is_repo: bool
    commit: GitCommit
    # Message after the subject line, with leading and trailing blank
    # lines stripped. Empty string when the message is a subject only.
    body: str
    stats: GitCommitStats
    files: list[GitFileChange]
    # True when the commit touched more than GIT_COMMIT_MAX_FILES and the
    # list was cut. Reported rather than silently shortened; `stats`
    # still describes the whole commit.
    files_truncated: bool


# Required-key gate sets for the validators below. As in
# :mod:`metabrowser.wire_models`, TypedDict carries no required-key
# reflection in this form, so they are spelled out. Keep in sync with the
# class bodies above.
_REF_REQUIRED: frozenset[str] = frozenset({"id", "name", "kind", "revision"})
_COMMIT_REQUIRED: frozenset[str] = frozenset(
    {"id", "short_id", "parent_ids", "author", "authored_at", "committed_at", "subject"}
)
_FILE_CHANGE_REQUIRED: frozenset[str] = frozenset({"path", "status", "additions", "deletions"})
_STATS_REQUIRED: frozenset[str] = frozenset(
    {
        "files_changed",
        "files_modified",
        "files_added",
        "files_deleted",
        "additions",
        "deletions",
    }
)

_REF_KINDS: frozenset[str] = frozenset({"branch", "remote", "tag"})
_FILE_STATUSES: frozenset[str] = frozenset(
    {"added", "modified", "deleted", "renamed", "copied", "typechanged"}
)


def validate_git_ref(ref: Mapping[str, Any], *, _where: str = "") -> None:
    """Raise :class:`AssertionError` if *ref* violates :class:`GitRef`."""
    missing = _REF_REQUIRED - ref.keys()
    assert not missing, f"ref at {_where!r} missing keys: {sorted(missing)}"
    assert isinstance(ref["id"], str) and ref["id"], f"ref.id not a non-empty str at {_where!r}"
    assert isinstance(ref["name"], str), f"ref.name not str at {_where!r}"
    assert ref["kind"] in _REF_KINDS, f"ref.kind {ref['kind']!r} not in {sorted(_REF_KINDS)}"
    assert is_full_revision(ref["revision"]), (
        f"ref.revision not a full object id at {_where!r}: {ref['revision']!r}"
    )
    if "is_head" in ref:
        assert isinstance(ref["is_head"], bool), f"ref.is_head not bool at {_where!r}"
    if "remote" in ref:
        assert ref["kind"] == "remote", (
            f"ref.remote present on kind={ref['kind']!r} at {_where!r} — "
            f"remote is only meaningful for remote-tracking refs"
        )


def validate_git_commit(commit: Mapping[str, Any], *, _where: str = "") -> None:
    """Raise :class:`AssertionError` if *commit* violates :class:`GitCommit`."""
    missing = _COMMIT_REQUIRED - commit.keys()
    assert not missing, f"commit at {_where!r} missing keys: {sorted(missing)}"
    where = _where or commit.get("short_id", "?")

    assert is_full_revision(commit["id"]), (
        f"commit.id not a full object id at {where!r}: {commit['id']!r} — "
        f"the browser passes this straight back as a path parameter"
    )
    assert isinstance(commit["short_id"], str), f"commit.short_id not str at {where!r}"

    parents = commit["parent_ids"]
    assert isinstance(parents, list), f"commit.parent_ids not list at {where!r}"
    for i, parent in enumerate(parents):
        assert is_full_revision(parent), (
            f"commit.parent_ids[{i}] not a full object id at {where!r}: {parent!r} — "
            f"the swimlane layout matches parents against commit ids by equality"
        )

    author = commit["author"]
    assert isinstance(author, dict), f"commit.author not dict at {where!r}"
    assert isinstance(author.get("name", ""), str), f"commit.author.name not str at {where!r}"

    for key in ("authored_at", "committed_at"):
        assert isinstance(commit[key], (int, float)), (
            f"commit.{key} not numeric at {where!r}: {commit[key]!r}"
        )
    assert isinstance(commit["subject"], str), f"commit.subject not str at {where!r}"

    for i, ref in enumerate(commit.get("refs", [])):
        validate_git_ref(ref, _where=f"{where}.refs[{i}]")


def validate_git_log_page(page: Mapping[str, Any]) -> None:
    """Raise :class:`AssertionError` if *page* violates :class:`GitLogPage`."""
    assert isinstance(page.get("is_repo"), bool), "log page missing bool 'is_repo'"
    if not page["is_repo"]:
        return

    commits = page.get("commits")
    assert isinstance(commits, list), "log page 'commits' not a list"
    for i, commit in enumerate(commits):
        validate_git_commit(commit, _where=f"commits[{i}]")

    has_more = page.get("has_more")
    assert isinstance(has_more, bool), "log page 'has_more' not bool"
    cursor = page.get("cursor")
    # The pair is a contract, not two independent fields: the browser
    # stops paging on has_more, and would deadlock on a null cursor it
    # was told to follow.
    if has_more:
        assert isinstance(cursor, str) and cursor, (
            "log page has_more=True with no cursor — the browser has nothing to page with"
        )
    else:
        assert cursor is None, f"log page has_more=False must carry cursor=None, got {cursor!r}"

    if "page" in page:
        assert isinstance(page["page"], int) and page["page"] >= 0, (
            f"log page 'page' not a non-negative int: {page['page']!r}"
        )
        assert isinstance(page.get("page_cursor"), str) and page["page_cursor"], (
            "session log page missing its replay cursor"
        )
        previous = page.get("previous_cursor")
        if page["page"] == 0:
            assert previous is None, "first session log page must not have a previous cursor"
        else:
            assert isinstance(previous, str) and previous, (
                "non-first session log page missing its previous cursor"
            )
        assert page.get("scope") in ("default", "all"), (
            f"session log page has invalid scope: {page.get('scope')!r}"
        )
        assert isinstance(page.get("scope_refs"), list), "session log page scope_refs not a list"
        assert isinstance(page.get("scope_fingerprint"), str), (
            "session log page scope_fingerprint not a string"
        )


def validate_git_file_change(change: Mapping[str, Any], *, _where: str = "") -> None:
    """Raise :class:`AssertionError` if *change* violates :class:`GitFileChange`."""
    missing = _FILE_CHANGE_REQUIRED - change.keys()
    assert not missing, f"file change at {_where!r} missing keys: {sorted(missing)}"
    assert isinstance(change["path"], str) and change["path"], (
        f"file change path not a non-empty str at {_where!r}"
    )
    assert change["status"] in _FILE_STATUSES, (
        f"file change status {change['status']!r} not in {sorted(_FILE_STATUSES)} at {_where!r}"
    )

    binary = change.get("binary", False)
    for key in ("additions", "deletions"):
        value = change[key]
        if binary:
            assert value is None, (
                f"file change {key} must be None on a binary file at {_where!r}: {value!r}"
            )
        else:
            assert isinstance(value, int), (
                f"file change {key} not int at {_where!r}: {value!r} — "
                f"None is reserved for binary files"
            )

    if "old_path" in change:
        assert change["status"] in ("renamed", "copied"), (
            f"file change old_path present on status={change['status']!r} at {_where!r}"
        )
    if "outside_root" in change:
        assert isinstance(change["outside_root"], bool), (
            f"file change outside_root not bool at {_where!r}"
        )


def validate_git_commit_detail(detail: Mapping[str, Any]) -> None:
    """Raise :class:`AssertionError` if *detail* violates :class:`GitCommitDetail`."""
    assert isinstance(detail.get("is_repo"), bool), "commit detail missing bool 'is_repo'"
    if not detail["is_repo"]:
        return

    validate_git_commit(detail["commit"], _where="commit")
    assert isinstance(detail.get("body"), str), "commit detail 'body' not str"

    stats = detail.get("stats")
    assert isinstance(stats, dict), "commit detail 'stats' not a dict"
    missing = _STATS_REQUIRED - stats.keys()
    assert not missing, f"commit detail stats missing keys: {sorted(missing)}"
    for key in sorted(_STATS_REQUIRED):
        assert isinstance(stats[key], int), f"commit detail stats.{key} not int: {stats[key]!r}"
        assert stats[key] >= 0, f"commit detail stats.{key} is negative: {stats[key]!r}"
    status_total = stats["files_modified"] + stats["files_added"] + stats["files_deleted"]
    assert status_total == stats["files_changed"], (
        "commit detail status counts do not cover files_changed: "
        f"{status_total} != {stats['files_changed']}"
    )

    files = detail.get("files")
    assert isinstance(files, list), "commit detail 'files' not a list"
    for i, change in enumerate(files):
        validate_git_file_change(change, _where=f"files[{i}]")

    assert isinstance(detail.get("files_truncated"), bool), (
        "commit detail 'files_truncated' not bool"
    )
    # stats describes the whole commit even when the list was cut, so the
    # only direction that can be checked is this one.
    if not detail["files_truncated"]:
        assert stats["files_changed"] == len(files), (
            f"commit detail stats.files_changed={stats['files_changed']} disagrees with "
            f"{len(files)} listed files on an untruncated commit"
        )


def validate_git_repo_info(info: Mapping[str, Any]) -> None:
    """Raise :class:`AssertionError` if *info* violates :class:`GitRepoInfo`."""
    assert isinstance(info.get("is_repo"), bool), "repo info missing bool 'is_repo'"
    if not info["is_repo"]:
        assert isinstance(info.get("reason", ""), str), "repo info 'reason' not str"
        return

    root = info.get("root")
    assert root is None or isinstance(root, str), f"repo info 'root' not str|None: {root!r}"

    head = info.get("head")
    assert isinstance(head, dict), "repo info 'head' not a dict on a repository"
    assert isinstance(head.get("detached"), bool), "head.detached not bool"
    assert isinstance(head.get("unborn"), bool), "head.unborn not bool"

    revision = head.get("revision")
    if head["unborn"]:
        assert revision is None, f"unborn head must have revision=None, got {revision!r}"
    else:
        assert revision is not None and is_full_revision(revision), (
            f"head.revision not a full object id: {revision!r}"
        )

    ref = head.get("ref")
    assert ref is None or isinstance(ref, str), f"head.ref not str|None: {ref!r}"
    if head["detached"]:
        assert ref is None, f"detached head must have ref=None, got {ref!r}"


__all__ = [
    "GitAuthor",
    "GitCommit",
    "GitCommitDetail",
    "GitCommitStats",
    "GitFileChange",
    "GitHead",
    "GitLogPage",
    "GitRefList",
    "GitRef",
    "GitRepoInfo",
    "is_full_revision",
    "validate_git_commit",
    "validate_git_commit_detail",
    "validate_git_file_change",
    "validate_git_log_page",
    "validate_git_ref",
    "validate_git_repo_info",
]
