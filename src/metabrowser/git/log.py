"""``git log`` argument vectors, output parsing, and page cursors.

Output format
-------------

Records are NUL-separated (``-z``) and fields within a record are
separated by ``US`` (0x1f). Two properties make this parseable without
ambiguity:

* ``-z`` terminates each commit record with NUL, and NUL cannot occur in
  any field git emits here, so record framing is exact.
* ``%s`` (the subject) is last in the record and is single-line by
  construction. Splitting a record on ``US`` with a bounded ``maxsplit``
  therefore leaves any stray separator byte harmlessly inside the
  subject rather than shifting every subsequent field.

VS Code's git extension uses ``%n`` between fields and takes "everything
after field seven" as the message. That works because the message is
last, but it cannot carry a single-line field after a multi-line one.
Using an explicit separator keeps the record extensible.

Ordering
--------

``--topo-order`` is what makes the graph readable: it keeps a branch's
commits contiguous instead of interleaving branches by date, so a lane
stays a lane for its whole length. It is also what makes paging sound —
lane state at the end of one page is exactly the lane state at the start
of the next.
"""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Sequence
from pathlib import Path

from metabrowser.git.process import GitError, run_git
from metabrowser.git.wire import GitAuthor, GitCommit, GitLogPage, GitRef, is_full_revision
from metabrowser.settings import GIT_LOG_MAX_SKIP

# Field separator inside one commit record. Chosen from the C0 separator
# block, which git never emits itself in these fields.
_FIELD_SEP = "\x1f"

# Field order in LOG_FORMAT. The subject is last on purpose; see the
# module docstring.
LOG_FORMAT = _FIELD_SEP.join(
    ["%H", "%h", "%an", "%ae", "%at", "%ct", "%P", "%D", "%s"],
)
_LOG_FIELD_COUNT = 9


# The names a repository gives its trunk, and the remotes whose copies of
# it count as trunk too. Whichever of these exist are always in scope: a
# graph that cannot show the branch you merge into is not showing you the
# repository. Remote forms are derived rather than spelled out, so adding
# a remote is a one-word change.
TRUNK_BRANCH_NAMES = ("main", "master")
TRUNK_REMOTES = ("origin",)


def trunk_refs() -> tuple[str, ...]:
    """Local trunk names followed by their remote-tracking forms."""
    remote_forms = tuple(
        f"{remote}/{name}" for remote in TRUNK_REMOTES for name in TRUNK_BRANCH_NAMES
    )
    return (*TRUNK_BRANCH_NAMES, *remote_forms)


def is_trunk_ref(name: str, kind: str) -> bool:
    """Whether a short ref name is the branch the repository merges into.

    Tags are never trunk however they are named; a tag called ``main``
    is still a tag. Remote-tracking forms count too, so a clone whose
    local branch is something else still shows its remote trunk as
    trunk.
    """
    if kind == "tag":
        return False
    return name in trunk_refs()


def _log_args(*, skip: int, limit: int, refs: Sequence[str] | None = None) -> list[str]:
    """Build the ``git log`` argument vector for one page.

    *refs* scopes the walk. ``None`` means every ref (``--all``), which
    is the explicit "all branches" choice; a list is the default scope
    the panel asks for. Scope matters because ``--all`` in a repository
    with many refs shows whichever branch commits most often — an
    automation branch can fill every visible row while the trunk sits
    hundreds of rows down.

    ``--date-order`` rather than ``--topo-order``: both guarantee no
    parent is drawn before its children, which is all the lane layout
    requires, but topological order walks one lineage to exhaustion
    before switching, so a busy branch buries the others. Date order
    intermixes lines of history, which is what makes recent activity
    across branches legible.

    ``--decorate=full`` is required for ``%D`` to emit unambiguous full
    refnames — the short form cannot distinguish a branch from a tag of
    the same name.
    """
    scope = ["--all"] if refs is None else list(refs)
    return [
        "log",
        "-z",
        f"--format={LOG_FORMAT}",
        "--decorate=full",
        "--date-order",
        *scope,
        f"--skip={skip}",
        # One extra row beyond the page: its presence is how `has_more`
        # is determined without a second counting pass over the history.
        f"--max-count={limit + 1}",
    ]


async def resolve_default_scope(served_root: Path) -> list[str]:
    """The refs the graph shows unless asked for everything.

    HEAD, its upstream, and whichever trunk refs exist — so the view is
    always "where I am, and what I merge into", which is the comparison
    a history view is for. Refs that do not resolve are dropped rather
    than passed to git, which would fail the whole walk.
    """
    candidates = ["HEAD", "@{upstream}", *trunk_refs()]
    scope: list[str] = []
    for candidate in candidates:
        try:
            await run_git(
                ["rev-parse", "--verify", "--quiet", f"{candidate}^{{commit}}"], cwd=served_root
            )
        except GitError:
            continue
        scope.append(candidate)
    # HEAD always resolves in a repository with commits; an empty scope
    # means an unborn branch, where `--all` is the honest answer.
    return scope or []


def parse_decoration(decoration: str, revision: str) -> list[GitRef]:
    """Parse a ``%D`` decoration string into refs.

    The raw form is comma-separated, e.g.::

        HEAD -> refs/heads/feature, tag: refs/tags/v1.0, refs/heads/main

    ``HEAD`` appears three ways and each means something different: as
    ``HEAD -> <ref>`` when on a branch, as a bare ``HEAD`` when detached,
    and absent otherwise. Only the arrow form marks a real ref as
    current; a bare ``HEAD`` is not a ref the panel can badge, so it is
    dropped and the detached state is carried by
    :class:`~metabrowser.git.wire.GitHead` instead.
    """
    refs: list[GitRef] = []
    for raw_part in decoration.split(","):
        part = raw_part.strip()
        if not part:
            continue

        is_head = False
        if part.startswith("HEAD -> "):
            part = part[len("HEAD -> ") :].strip()
            is_head = True
        elif part == "HEAD":
            # Detached HEAD marker, not a ref. GitHead carries this.
            continue

        ref = _ref_from_full_name(part, revision)
        if ref is None:
            continue
        if is_head:
            ref["is_head"] = True
        if is_trunk_ref(ref["name"], ref["kind"]):
            ref["is_trunk"] = True
        refs.append(ref)

    refs.sort(key=_ref_sort_key)
    return refs


def _ref_from_full_name(full_name: str, revision: str) -> GitRef | None:
    """Build a :class:`GitRef` from a full refname, or ``None`` if unknown.

    Unrecognized namespaces — ``refs/stash``, ``refs/notes/*``,
    ``refs/pull/*`` from a fetch refspec, and anything a tool invented —
    are dropped rather than guessed at. They are not branches, and
    badging them as such would be wrong.
    """
    if full_name.startswith("tag: "):
        full_name = full_name[len("tag: ") :].strip()

    if full_name.startswith("refs/heads/"):
        return GitRef(
            id=full_name,
            name=full_name[len("refs/heads/") :],
            kind="branch",
            revision=revision,
        )
    if full_name.startswith("refs/tags/"):
        return GitRef(
            id=full_name,
            name=full_name[len("refs/tags/") :],
            kind="tag",
            revision=revision,
        )
    if full_name.startswith("refs/remotes/"):
        short = full_name[len("refs/remotes/") :]
        remote, _, _rest = short.partition("/")
        return GitRef(
            id=full_name,
            name=short,
            kind="remote",
            revision=revision,
            remote=remote,
        )
    return None


def _ref_sort_key(ref: GitRef) -> tuple[int, str]:
    """Display order: current branch, other branches, remotes, tags.

    This is VS Code's precedence (``compareHistoryItemRefs`` in
    ``scmHistory.ts``) reduced to the ref kinds this feature has. The name
    is the tiebreak so a row's badges do not reorder between requests.
    """
    if ref.get("is_head"):
        order = 0
    elif ref["kind"] == "branch":
        order = 1
    elif ref["kind"] == "remote":
        order = 2
    else:
        order = 3
    return (order, ref.get("name", ""))


def _parse_commit_record(record: str) -> GitCommit | None:
    """Parse one NUL-delimited record, or ``None`` if it is not one.

    A record that does not carry the expected field count is skipped
    rather than raising: the alternative is that one malformed commit
    (or a git version emitting an unexpected extra field) blanks the
    whole panel.
    """
    fields = record.split(_FIELD_SEP, _LOG_FIELD_COUNT - 1)
    if len(fields) != _LOG_FIELD_COUNT:
        return None

    (
        revision,
        short_id,
        author_name,
        author_email,
        authored,
        committed,
        parents,
        decoration,
        subj,
    ) = fields
    if not is_full_revision(revision):
        return None

    parent_ids = [p for p in parents.split(" ") if is_full_revision(p)]

    commit = GitCommit(
        id=revision,
        short_id=short_id,
        parent_ids=parent_ids,
        author=GitAuthor(name=author_name, email=author_email),
        authored_at=parse_epoch(authored),
        committed_at=parse_epoch(committed),
        subject=subj,
    )
    refs = parse_decoration(decoration, revision)
    if refs:
        commit["refs"] = refs
    return commit


def parse_epoch(raw: str) -> float:
    """Parse a ``%at``/``%ct`` epoch field, tolerating a malformed value.

    A commit with an unparseable date still belongs in the graph — its
    topology is what the layout runs on — so this degrades to 0.0 rather
    than dropping the row.
    """
    try:
        return float(raw)
    except ValueError:
        return 0.0


def parse_log_output(raw: bytes) -> list[GitCommit]:
    """Parse the full ``git log -z`` byte stream into commits.

    Decoding is ``utf-8`` with replacement. Author names and subjects are
    whatever bytes the committer's terminal produced and are not
    guaranteed to be valid UTF-8; a mojibake author name is a far better
    outcome than a 500 on one bad commit in the history.
    """
    text = raw.decode("utf-8", errors="replace")
    commits: list[GitCommit] = []
    for record in text.split("\0"):
        if not record:
            continue
        commit = _parse_commit_record(record)
        if commit is not None:
            commits.append(commit)
    return commits


def encode_cursor(skip: int) -> str:
    """Encode a page cursor.

    Opaque by construction — base64 of a JSON object — so the offset is
    not part of the API and paging can change shape without a client
    change. Callers never build one; they echo back what a page returned.
    """
    payload = json.dumps({"skip": skip}, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_cursor(cursor: str) -> int | None:
    """Decode a page cursor to its skip offset, or ``None`` if unusable.

    The route rejects ``None`` as a bad request. Restarting at offset zero
    would make the append-only client duplicate commits and corrupt lane
    continuity.

    A well-formed cursor is not yet a usable one: the offset is bounded by
    ``GIT_LOG_MAX_SKIP`` because ``git log --skip`` walks and discards the
    whole prefix, so an arbitrary offset buys a full history walk that
    returns nothing.
    """
    try:
        padding = "=" * (-len(cursor) % 4)
        payload = base64.urlsafe_b64decode(cursor + padding)
        skip = json.loads(payload)["skip"]
    except (binascii.Error, UnicodeDecodeError, ValueError, KeyError, TypeError):
        return None
    if not isinstance(skip, int) or isinstance(skip, bool) or skip < 0:
        return None
    if skip > GIT_LOG_MAX_SKIP:
        return None
    return skip


async def read_log_page(
    served_root: Path, *, skip: int, limit: int, refs: Sequence[str] | None = None
) -> GitLogPage:
    """Read one page of history.

    *refs* is the scope; ``None`` walks every ref. The page is
    over-fetched by one commit; that extra row is the ``has_more``
    signal and is dropped before the page is returned. The alternative —
    counting the whole history to know whether more exists — costs a
    full walk on every page.
    """
    raw = await run_git(_log_args(skip=skip, limit=limit, refs=refs), cwd=served_root)
    commits = parse_log_output(raw)

    has_more = len(commits) > limit
    if has_more:
        commits = commits[:limit]

    return GitLogPage(
        is_repo=True,
        commits=commits,
        cursor=encode_cursor(skip + len(commits)) if has_more else None,
        has_more=has_more,
    )


async def read_refs(served_root: Path, *, head_ref: str | None = None) -> list[GitRef]:
    """List every branch, remote branch, and tag with its target commit.

    ``for-each-ref`` rather than ``branch``/``tag``: it emits full
    refnames and dereferenced targets in one pass, and ``%(objectname)``
    on a ``refs/tags/*`` entry with ``^{}`` appended resolves an annotated
    tag through to the commit it tags — a badge must point at a commit in
    the graph, not at the tag object.

    ``head_ref`` is the symbolic ref discovered with the repository
    context. Passing it into this single ref walk avoids another process
    while still marking the checked-out branch for client lane colors.
    """
    raw = await run_git(
        [
            "for-each-ref",
            "--format=%(refname)\x1f%(objectname)\x1f%(*objectname)",
            "refs/heads",
            "refs/remotes",
            "refs/tags",
        ],
        cwd=served_root,
    )

    refs: list[GitRef] = []
    for line in raw.decode("utf-8", errors="replace").splitlines():
        parts = line.split(_FIELD_SEP)
        if len(parts) != 3:
            continue
        full_name, object_name, peeled = parts
        # `*objectname` is populated only for annotated tags; for
        # everything else it is empty and the object name is already the
        # commit.
        revision = peeled or object_name
        if not is_full_revision(revision):
            continue
        ref = _ref_from_full_name(full_name, revision)
        if ref is not None:
            if full_name == head_ref:
                ref["is_head"] = True
            refs.append(ref)

    refs.sort(key=_ref_sort_key)
    return refs


__all__ = [
    "decode_cursor",
    "encode_cursor",
    "parse_decoration",
    "parse_epoch",
    "TRUNK_BRANCH_NAMES",
    "TRUNK_REMOTES",
    "parse_log_output",
    "is_trunk_ref",
    "read_log_page",
    "resolve_default_scope",
    "trunk_refs",
    "read_refs",
]
