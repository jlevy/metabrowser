"""Per-commit detail: message body, changed files, and line counts.

One invocation, not two. ``--raw`` and ``--numstat`` each carry half of
what a changed-file row needs — raw has the status letter (and the
similarity score that distinguishes a rename from a copy), numstat has
the line counts and the binary marker — and git emits both sections when
both flags are given. Running two commands instead would double the
process cost of the endpoint that the hover card calls on every row.

Output shape, with ``-z``, is one NUL-terminated token stream::

    <format output>\\0
    \\n:100644 100644 <sha> <sha> M\\0<path>\\0
    :100644 100644 <sha> <sha> R075\\0<old path>\\0<new path>\\0
    <additions>\\t<deletions>\\t<path>\\0
    <additions>\\t<deletions>\\t\\0<old path>\\0<new path>\\0

Raw entries always precede numstat entries, and the two are told apart
by their first byte, so a single pass over the tokens reads both.
Renames spend three tokens in each section; binary files report ``-``
for both counts.

Merges are diffed against their first parent (``--diff-merges=
first-parent``). Git's default for a merge is a combined diff, which
shows only hunks that differ from *every* parent and so reports almost
nothing for an ordinary merge — a changed-file list that is empty for
every merge commit is worse than useless.
"""

from __future__ import annotations

import re

from metabrowser.git.log import parse_decoration, parse_epoch
from metabrowser.git.process import GitCommandError, run_git
from metabrowser.git.repo import RepoContext
from metabrowser.git.wire import (
    GitAuthor,
    GitCommit,
    GitCommitDetail,
    GitCommitStats,
    GitFileChange,
    is_full_revision,
)
from metabrowser.settings import GIT_COMMIT_MAX_FILES

_FIELD_SEP = "\x1f"

# Metadata fields, in order. %B (the full message) is last for the same
# reason the subject is last in the log format: it is the only
# multi-line field, so a bounded split leaves it intact.
_SHOW_FORMAT = _FIELD_SEP.join(["%H", "%h", "%an", "%ae", "%at", "%ct", "%P", "%D", "%B"])
_SHOW_FIELD_COUNT = 9

# A raw entry's trailing status token: a letter, optionally followed by a
# similarity score for renames and copies (``R075``).
_RAW_STATUS_RE = re.compile(r"\A([A-Z])(\d*)\Z")

# A numstat entry: two counts (or "-" for binary) and a path, tab-separated.
# The path is empty for renames, whose two paths follow as separate tokens.
_NUMSTAT_RE = re.compile(r"\A(\d+|-)\t(\d+|-)\t(.*)\Z", re.DOTALL)

_STATUS_NAMES: dict[str, str] = {
    "A": "added",
    "C": "copied",
    "D": "deleted",
    "M": "modified",
    "R": "renamed",
    "T": "typechanged",
}

# Statuses that carry a second path. Git spends three tokens on these.
_TWO_PATH_STATUSES = frozenset({"C", "R"})

_UNKNOWN_REVISION_MARKERS: tuple[str, ...] = (
    "bad object",
    "not a valid object name",
    "unknown revision or path not in the working tree",
)


def _show_args(revision: str) -> list[str]:
    """Build the ``git show`` argument vector for one commit.

    ``-M`` and ``-C`` enable rename and copy detection, without which
    every rename reads as an unrelated delete plus add — visually the
    single most misleading thing a commit view can get wrong.
    """
    return [
        "show",
        "-z",
        "--raw",
        "--numstat",
        "-M",
        "-C",
        "--diff-merges=first-parent",
        f"--format={_SHOW_FORMAT}",
        revision,
    ]


def translate_repo_path(raw_path: str, context: RepoContext) -> tuple[str, bool]:
    """Map a repository-relative path to a served-root-relative one.

    Returns ``(path, outside_root)``. Git reports paths relative to the
    repository root; every path Metabrowser puts on the wire is relative
    to the served root, and those differ whenever a subdirectory of a
    checkout is being served.

    A file inside the repository but outside the served root keeps its
    repository-relative path and is flagged. Both alternatives are worse:
    serving it as if it were navigable would invite a request the
    safe-path layer must then reject, and omitting it would misreport
    what the commit changed.
    """
    absolute = context.git_root / raw_path
    try:
        return str(absolute.relative_to(context.served_root)), False
    except ValueError:
        return raw_path, True


def _parse_raw_entry(token: str) -> tuple[str, int | None] | None:
    """Parse a ``--raw`` entry token into ``(status letter, similarity)``.

    The token is ``:<mode> <mode> <sha> <sha> <status>``; only the status
    is needed, since the modes and blob ids have no place in the view.
    Returns ``None`` for anything that does not parse, so an unfamiliar
    status (git's ``U`` for unmerged, or a future addition) drops that
    one file rather than the whole commit.
    """
    fields = token.split(" ")
    if not fields:
        return None
    match = _RAW_STATUS_RE.match(fields[-1])
    if match is None:
        return None
    letter, score = match.groups()
    if letter not in _STATUS_NAMES:
        return None
    return letter, int(score) if score else None


def _parse_change_sections(tokens: list[str], context: RepoContext) -> list[GitFileChange]:
    """Walk the token stream, merging the raw and numstat sections.

    The two sections are keyed by path — specifically by the *new* path,
    which is the only identifier both sections agree on for a rename.
    """
    statuses: dict[str, tuple[str, int | None]] = {}
    old_paths: dict[str, str] = {}
    counts: dict[str, tuple[int | None, int | None]] = {}
    # Insertion order of first sighting, so the response preserves git's
    # ordering rather than dict-iteration accident.
    order: list[str] = []

    # Git terminates the ``--format`` record with NUL and *then* writes a
    # newline before the first diff entry, so the first token of this
    # section arrives as "\n:100644 ...". Without stripping it the raw
    # prefix test misses, the walk falls out of step by one entry, and
    # the first changed file silently vanishes from the commit.
    tokens = list(tokens)
    if tokens and tokens[0].startswith("\n"):
        tokens[0] = tokens[0][1:]

    index = 0
    while index < len(tokens):
        token = tokens[index]
        if not token:
            index += 1
            continue

        if token.startswith(":"):
            parsed = _parse_raw_entry(token)
            # Path tokens must be consumed whether or not the status
            # parsed, or the walk desynchronizes from the stream.
            letter = parsed[0] if parsed else ""
            two_paths = letter in _TWO_PATH_STATUSES
            needed = 2 if two_paths else 1
            if index + needed >= len(tokens):
                break
            if two_paths:
                old_path, new_path = tokens[index + 1], tokens[index + 2]
            else:
                old_path, new_path = "", tokens[index + 1]
            index += 1 + needed

            if parsed is None or not new_path:
                continue
            if new_path not in statuses:
                order.append(new_path)
            statuses[new_path] = parsed
            if old_path:
                old_paths[new_path] = old_path
            continue

        match = _NUMSTAT_RE.match(token)
        if match is not None:
            additions_raw, deletions_raw, path = match.groups()
            if path:
                index += 1
            else:
                # Rename or copy: the empty path field is followed by the
                # old and new paths as their own tokens.
                if index + 2 >= len(tokens):
                    break
                path = tokens[index + 2]
                index += 3
            if path:
                if path not in statuses and path not in counts:
                    order.append(path)
                counts[path] = (_parse_count(additions_raw), _parse_count(deletions_raw))
            continue

        index += 1

    changes: list[GitFileChange] = []
    for path in order:
        status_entry = statuses.get(path)
        if status_entry is None:
            # numstat listed a path the raw section did not. Nothing can
            # be said about its status, and guessing "modified" would be
            # a lie on a rename; skip it.
            continue
        letter, similarity = status_entry
        additions, deletions = counts.get(path, (0, 0))
        binary = additions is None and deletions is None

        translated, outside_root = translate_repo_path(path, context)
        change = GitFileChange(
            path=translated,
            status=_STATUS_NAMES[letter],  # pyright: ignore[reportArgumentType]
            additions=additions,
            deletions=deletions,
        )
        if binary:
            change["binary"] = True
        if outside_root:
            change["outside_root"] = True
        if path in old_paths:
            old_translated, _ = translate_repo_path(old_paths[path], context)
            change["old_path"] = old_translated
        if similarity is not None:
            change["similarity"] = similarity
        changes.append(change)

    return changes


def _parse_count(raw: str) -> int | None:
    """Parse a numstat count. ``-`` means binary, reported as ``None``."""
    if raw == "-":
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _split_message(message: str) -> tuple[str, str]:
    """Split a full commit message into ``(subject, body)``.

    The subject is the first line and the body is everything after the
    blank line that follows it, matching how git itself reads ``%s`` and
    ``%b``. Surrounding blank lines are stripped so the view does not
    have to.
    """
    lines = message.split("\n")
    subject = lines[0].strip() if lines else ""
    body = "\n".join(lines[1:]).strip("\n").strip()
    return subject, body


def parse_commit_detail(
    raw: bytes,
    context: RepoContext,
    *,
    max_files: int = GIT_COMMIT_MAX_FILES,
) -> GitCommitDetail | None:
    """Parse ``git show`` output into a commit detail envelope.

    Returns ``None`` when the metadata record is unparseable, which the
    route reports as an unknown revision.
    """
    text = raw.decode("utf-8", errors="replace")
    tokens = text.split("\0")
    if not tokens:
        return None

    fields = tokens[0].split(_FIELD_SEP, _SHOW_FIELD_COUNT - 1)
    if len(fields) != _SHOW_FIELD_COUNT:
        return None

    revision, short_id, name, email, authored, committed, parents, decoration, message = fields
    if not is_full_revision(revision):
        return None

    subject, body = _split_message(message)
    commit = GitCommit(
        id=revision,
        short_id=short_id,
        parent_ids=[p for p in parents.split(" ") if is_full_revision(p)],
        author=GitAuthor(name=name, email=email),
        authored_at=parse_epoch(authored),
        committed_at=parse_epoch(committed),
        subject=subject,
    )
    # Shared with the log parser so a badge in the detail view and the
    # same badge in the graph cannot disagree.
    refs = parse_decoration(decoration, revision)
    if refs:
        commit["refs"] = refs

    changes = _parse_change_sections(tokens[1:], context)
    # Stats describe the whole commit, so they are computed before the
    # cap is applied: a truncated list must not also understate the
    # totals it was truncated from.
    stats = GitCommitStats(
        files_changed=len(changes),
        additions=sum(c["additions"] or 0 for c in changes),
        deletions=sum(c["deletions"] or 0 for c in changes),
    )
    files_truncated = len(changes) > max_files
    if files_truncated:
        changes = changes[:max_files]

    return GitCommitDetail(
        is_repo=True,
        commit=commit,
        body=body,
        stats=stats,
        files=changes,
        files_truncated=files_truncated,
    )


async def read_commit_detail(
    context: RepoContext,
    revision: str,
    *,
    max_files: int = GIT_COMMIT_MAX_FILES,
) -> GitCommitDetail | None:
    """Read one commit's detail. ``None`` when the revision is unknown."""
    try:
        raw = await run_git(_show_args(revision), cwd=context.served_root)
    except GitCommandError as exc:
        if any(marker in exc.stderr_summary.lower() for marker in _UNKNOWN_REVISION_MARKERS):
            return None
        raise
    return parse_commit_detail(raw, context, max_files=max_files)


__all__ = [
    "parse_commit_detail",
    "read_commit_detail",
    "translate_repo_path",
]
