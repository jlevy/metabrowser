"""An author-provided guide to the exact comparison of a cached GitHub pull request."""

from __future__ import annotations

import asyncio
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Final, Literal

from markdown_it import MarkdownIt
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from softschema.models import Contract, SchemaProfile, SchemaStatus
from softschema.validate import parse_yaml_text, validate_artifact

from metabrowser import kpress_adapter
from metabrowser.builtin_plugins.github import pulls
from metabrowser.builtin_plugins.github.pull_catalog import catalog_member
from metabrowser.builtin_plugins.github.pull_freshness import record_freshness
from metabrowser.builtin_plugins.github.pull_manifest import shared_pull_manifest
from metabrowser.builtin_plugins.github.pull_record import (
    MAX_BODY_BYTES,
    PullRecord,
    Sha,
    cut_text,
)
from metabrowser.builtin_plugins.github.pull_route import cached_pull_record
from metabrowser.cache.acquire import PublishedSource
from metabrowser.diff.adapters.base import DiffSourceError
from metabrowser.diff.adapters.git import GitDiffSource, display_path
from metabrowser.diff.format import Availability, Hunk, LineOp, LineRecord
from metabrowser.git.process import (
    GIT_NO_DRIVER_ARGS,
    GitCommandError,
    GitError,
    GitLocation,
    RepositoryStoreTarget,
    run_git_at,
)
from metabrowser.view_routes import format_pull_href

if TYPE_CHECKING:
    from markdown_it.token import Token

    from metabrowser.builtin_plugins.github.pull_route import PullHost
    from metabrowser.diff.format import FileChange, FilePatch

CONTRACT_ID = "metabrowser.collection:Collection/v1"
SCHEMA_PATH = Path(__file__).with_name("collection-v1.schema.yaml")
_CONTRACT = Contract(
    id=CONTRACT_ID,
    profile=SchemaProfile.pure_yaml,
    status=SchemaStatus.enforced,
    envelope_key="collection",
    schema_path=SCHEMA_PATH,
)
# Only block tokens matter. In particular, an example in another fence is not a guide.
_MARKDOWN = MarkdownIt("commonmark").disable("inline")

# Each item hydrates at most as many paths as the measured first paint of Changes
# (INITIAL_PULL_FILES in sidekick.py). It renders only the selected ranges.
MAX_REFERENCES = 8
# A reviewer reads a guide one item at a time, and parse_guide costs by the item: markdown-it,
# YAML, JSON Schema and pydantic, in Python that holds the GIL, take 3.3 ms an item of
# MAX_REFERENCES references and 0.6 ms a KiB of text on top. Warm, best of nine, on a
# 10-core Mac at a load average of 13 (2026-11-20): 20 items took 66 ms with the shortest
# text, 40 items 131 ms and 80 items 262 ms, and 40 items with the description filled to
# MAX_BODY_BYTES took 154 ms. The body bound alone admits 480 one-reference items, which
# took 322 ms, so this keeps the largest guide the caps admit near 150 ms. read_guide pays
# it once for each record revision.
MAX_ITEMS = 40
# Eight excerpts totaling 800 one-character rows, just past the PR body ceiling after
# the per-row charge, mounted and laid out in 11–14 ms in five headless Chrome 157 runs
# at 1280×900 on the Guided Review page (2026-11-18). A single long row must fit too. This
# bounds a step's ranged excerpts. A reference with no range shows its file's whole patch,
# which the diff source bounds as it does for Changes, and drawn by the diff plugin's file
# renderer it folds long changed runs as Changes does; MAX_REFERENCES keeps a step's files
# within the measured first paint of Changes.
MAX_EXCERPT_BYTES = MAX_BODY_BYTES

# A stale guide's notice names the commits after the guide's head, newest first, and counts
# the rest: it is read at a glance above the guide, and one bounded `git log` writes it.
MAX_STALE_COMMITS: Final = 10
# A commit's subject as the notice shows it, as the Conversation timeline cuts one.
MAX_STALE_SUBJECT_BYTES: Final = 240
# The paths changed since the guide decide which of its steps still match the pull request.
# A change past this many paths is answered as unknown rather than read whole: every step
# is then shown with no claim either way.
MAX_STALE_PATHS: Final = 4000
# A path as `git diff --name-only -z` writes it is at most a filesystem path, 4096 bytes.
_MAX_STALE_PATH_BYTES: Final = 4096

type Prose = Annotated[str, Field(min_length=1)]
type LineNumber = Annotated[int, Field(ge=1)]


class GuideError(ValueError):
    """The PR description offers a guide we cannot use."""


class _Model(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", str_strip_whitespace=False)


class CollectionComparison(_Model):
    merge_base: Sha
    head: Sha


class CollectionReference(_Model):
    path: Prose
    side: Literal["old", "new"] | None = None
    start_line: LineNumber | None = None
    end_line: LineNumber | None = None

    @model_validator(mode="after")
    def _usable_reference(self) -> CollectionReference:
        format_pull_href(1, "files", self.path)
        if self.side is None and self.start_line is None and self.end_line is None:
            return self
        if (
            self.side is None
            or self.start_line is None
            or self.end_line is None
            or self.end_line < self.start_line
        ):
            raise ValueError("a range needs a side and ordered start_line and end_line")
        return self


class CollectionItem(_Model):
    title: Prose
    note: Prose
    references: list[CollectionReference] = Field(min_length=1, max_length=MAX_REFERENCES)


class Collection(_Model):
    """Ordered annotated items over one comparison.

    A collection has no prose of its own: the document that holds it introduces it, as a
    pull request's description introduces its guide.
    """

    comparison: CollectionComparison
    items: list[CollectionItem] = Field(min_length=1, max_length=MAX_ITEMS)


def _guide_fence(body: str) -> tuple[Token, list[str]] | None:
    """The description's one top-level guided-pr fence and the body's lines, or ``None``.

    Raises :class:`GuideError` for two such fences or one that is not closed.
    """
    if "guided-pr" not in body:
        return None
    fences = [
        token
        for token in _MARKDOWN.parse(body)
        if token.type == "fence" and token.level == 0 and token.info.strip() == "guided-pr"
    ]
    if not fences:
        return None
    if len(fences) != 1:
        raise GuideError("Use one guided-pr block in the pull request description.")
    fence = fences[0]
    mapped = fence.map
    assert mapped is not None
    lines = body.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    marker = re.escape(fence.markup[0])
    if mapped[1] <= mapped[0] + 1 or not re.fullmatch(
        rf" {{0,3}}{marker}{{{len(fence.markup)},}}[ \t]*", lines[mapped[1] - 1]
    ):
        raise GuideError("Close the guided-pr block with a matching code fence.")
    return fence, lines


def without_guide(body: str) -> str:
    """*body* without its guided-pr block: the description as the guide's introduction.

    A description whose block cannot be read keeps it, so its author sees what they wrote.
    """
    try:
        found = _guide_fence(body)
    except GuideError:
        return body
    if found is None:
        return body
    fence, lines = found
    assert fence.map is not None
    start, end = fence.map
    return "\n".join([*lines[:start], *lines[end:]]).strip("\n")


def parse_guide(body: str) -> Collection | None:
    """Read one top-level fenced SoftSchema artifact from the raw PR description."""
    found = _guide_fence(body)
    if found is None:
        return None
    fence, _ = found
    try:
        document: object = parse_yaml_text(fence.content)
    except ValueError as exc:
        raise GuideError("The guided-pr block contains invalid YAML.") from exc
    if not isinstance(document, dict) or set(document) != {"softschema", "collection"}:
        raise GuideError("The guided-pr block needs softschema metadata and a collection.")
    if document["softschema"] != {
        "contract": CONTRACT_ID,
        "envelope": _CONTRACT.envelope_key,
        "status": _CONTRACT.status,
    }:
        raise GuideError("The guided-pr block needs the enforced Collection/v1 contract.")
    result = validate_artifact(Path("guided-pr"), contract=_CONTRACT, document=document)
    if not result.ok:
        error = result.structural.errors[0]
        path = error.get("path")
        where = f" at {path}" if isinstance(path, str) and path else ""
        raise GuideError(f"The guided-pr block does not satisfy the v1 SoftSchema{where}.")
    try:
        return Collection.model_validate(result.values)
    except ValidationError as exc:
        location = ".".join(str(part) for part in exc.errors()[0]["loc"])
        raise GuideError(f"Invalid guided-pr reference at {location}.") from exc


@dataclass(frozen=True, slots=True)
class _Read:
    revision: str
    guide: Collection | None
    message: str | None


# One parse for each pull request, kept with the record revision (a hash of the record's
# content) that it read, so a Previous or Next click reads the guide the first request
# parsed and an edited description is parsed once. A guide that does not parse is kept as
# its message, since it costs as much to refuse as to read.
_READS: dict[tuple[str, str, int], _Read] = {}
_READS_LOCK: Final = threading.Lock()
_MAX_READS: Final = 16


def read_guide(key: tuple[str, str, int], revision: str, body: str) -> Collection | None:
    """:func:`parse_guide` of *body*, reused while *key*'s record has this *revision*."""
    with _READS_LOCK:
        hit = _READS.get(key)
    if hit is None or hit.revision != revision:
        try:
            hit = _Read(revision, parse_guide(body), None)
        except GuideError as exc:
            hit = _Read(revision, None, str(exc))
        with _READS_LOCK:
            if key not in _READS and len(_READS) >= _MAX_READS:
                _READS.pop(next(iter(_READS)))
            _READS[key] = hit
    if hit.message is not None:
        raise GuideError(hit.message)
    return hit.guide


def _excerpt(
    patch: FilePatch, reference: CollectionReference, budget: int
) -> tuple[str, list[dict[str, object]], int]:
    """A ranged reference as one hunk of the diff route's shape, within *budget*."""
    start, end = reference.start_line, reference.end_line
    assert start is not None and end is not None
    old_side = reference.side == "old"
    for hunk in patch.hunks:
        first, count = (
            (hunk.old_start, hunk.old_count)
            if old_side
            else (
                hunk.new_start,
                hunk.new_count,
            )
        )
        if first <= start <= end < first + count:
            state, rows, used = _hunk_rows(hunk, start, end, old_side, budget)
            return state, ([_rows_hunk(hunk, rows)] if rows else []), used
    return "range_unavailable", [], 0


def _rows_hunk(hunk: Hunk, rows: list[dict[str, object]]) -> dict[str, object]:
    """*rows* of *hunk* as a hunk of their own, in the diff model's shape (`Hunk`).

    The lines are *hunk*'s own records, so a range's hunk and a whole file's are one shape.
    A side with no line in the rows starts, as in a unified diff, at the line before them:
    an added file's range is `@@ -0,0 +1,2 @@`. A hunk with no line on a side states that
    side's start as the line before already, so its count starts one past it.
    """
    wanted = {(row["old"], row["new"]) for row in rows}
    old = hunk.old_start + (hunk.old_count == 0)
    new = hunk.new_start + (hunk.new_count == 0)
    before: tuple[int, int] | None = None
    lines: list[LineRecord] = []
    for line in hunk.lines:
        left = old if line.op is not LineOp.add else None
        right = new if line.op is not LineOp.delete else None
        if (left, right) in wanted:
            before = before or (old - 1, new - 1)
            lines.append(line)
        old += left is not None
        new += right is not None
    assert before is not None
    olds = [row["old"] for row in rows if isinstance(row["old"], int)]
    news = [row["new"] for row in rows if isinstance(row["new"], int)]
    return Hunk(
        old_start=olds[0] if olds else before[0],
        old_count=len(olds),
        new_start=news[0] if news else before[1],
        new_count=len(news),
        lines=tuple(lines),
    ).model_dump(mode="json")


def _hunk_rows(
    hunk: Hunk, start: int, end: int, old_side: bool, budget: int
) -> tuple[str, list[dict[str, object]], int]:
    """The rows of *hunk* that lie in lines *start* to *end* of one side, within *budget*.

    A replacement is shown whole. A line only the other side has, a deleted line for a new
    range or an added one for an old range, is a row when it lies inside the range or
    touches either end of it, so a changed line appears with the line it replaced.
    """
    rows: list[dict[str, object]] = []
    old, new = hunk.old_start, hunk.new_start
    size = 0
    for line in hunk.lines:
        left = old if line.op is not LineOp.add else None
        right = new if line.op is not LineOp.delete else None
        selected = old if old_side else new
        old += left is not None
        new += right is not None
        if selected < start:
            continue
        opposite = left is None if old_side else right is None
        if selected > end + opposite:
            break
        # Count JSON's escaping as well as text. Keep the wire and the render bounded
        # even on rows made entirely of control characters or empty lines.
        size += 80 + 6 * len(line.text)
        if size > budget:
            return "excerpt_too_large", [], 0
        rows.append({"old": left, "new": right, "op": line.op, "text": line.text})
    return "ready", rows, size


def _references(
    number: int,
    references: list[CollectionReference],
    changes: dict[str, FileChange],
    patches: dict[str, FilePatch],
    *,
    truncated: bool,
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    remaining = MAX_EXCERPT_BYTES
    for reference in references:
        change = changes.get(reference.path)
        href = None
        hunks: list[dict[str, object]] = []
        cut = False
        if change is None:
            state = "manifest_truncated" if truncated else "path_not_changed"
        else:
            href = format_pull_href(number, "files", reference.path)
            patch = patches.get(change.id)
            if patch is None:
                state = "diff_unavailable"
            elif reference.side is None:
                # The file's whole patch, as Changes shows it (MAX_EXCERPT_BYTES).
                state = "ready"
                hunks = [hunk.model_dump(mode="json") for hunk in patch.hunks]
                cut = patch.truncated
            else:
                state, hunks, used = _excerpt(patch, reference, remaining)
                remaining -= used
        output.append(
            {
                **reference.model_dump(),
                "state": state,
                "href": href,
                "hunks": hunks,
                "truncated": cut,
            }
        )
    return output


async def _step_references(
    store: PublishedSource, number: int, guide: Collection, step: CollectionItem
) -> list[dict[str, object]]:
    base, head = guide.comparison.merge_base, guide.comparison.head
    compared = await shared_pull_manifest(store, number, base, head)
    manifest = compared.manifest
    changes = {
        display_path(change): change
        for change in manifest.files
        if (side := change.new or change.old) is not None and side.path_b64 is None
    }
    ids = tuple(
        dict.fromkeys(
            change.id
            for ref in step.references
            if (change := changes.get(ref.path)) is not None
            and change.availability is Availability.ready
        )
    )
    patches: dict[str, FilePatch] = {}
    if ids:
        target = RepositoryStoreTarget(store.git_dir, store.object_format)
        diff = GitDiffSource(GitLocation.revision(target, head))
        patches = (await diff.hydrate(compared.resolved, ids, manifest=manifest)).patches
    return await asyncio.to_thread(
        _references, number, step.references, changes, patches, truncated=manifest.truncated
    )


async def _commits_since(location: GitLocation, old: str, new: str) -> dict[str, object]:
    """The first-parent commits *new* has and *old* does not, or why there is no answer.

    ``history`` is ``ahead`` when *old* is in *new*'s history, ``rewritten`` when it is not,
    as after a rebase or a force push, and ``unavailable`` when the store lacks *old*.
    """
    try:
        await run_git_at(["cat-file", "-e", f"{old}^{{commit}}"], location)
    except GitCommandError:
        return {"history": "unavailable", "commit_count": None, "commits": []}
    try:
        await run_git_at(["merge-base", "--is-ancestor", old, new], location)
        history = "ahead"
    except GitCommandError as exc:
        if exc.returncode != 1:
            raise
        history = "rewritten"
    span = f"{old}..{new}"
    count = await run_git_at(["rev-list", "--first-parent", "--count", span, "--"], location)
    out = await run_git_at(
        [
            "log",
            *GIT_NO_DRIVER_ARGS,
            "--first-parent",
            f"--max-count={MAX_STALE_COMMITS}",
            "--format=%H%x00%s%x00",
            span,
            "--",
        ],
        location,
        max_bytes=MAX_STALE_COMMITS * (200 + 4 * MAX_STALE_SUBJECT_BYTES),
    )
    fields = out.decode("utf-8", errors="replace").split("\0")
    commits = [
        {"sha": sha.strip(), "subject": cut_text(subject, MAX_STALE_SUBJECT_BYTES)[0]}
        for sha, subject in zip(fields[0:-1:2], fields[1::2], strict=False)
    ]
    return {"history": history, "commit_count": int(count), "commits": commits}


async def _paths_between(location: GitLocation, old: str, new: str) -> set[str] | None:
    """The paths that differ between commits *old* and *new*, or ``None`` past the bound."""
    try:
        out = await run_git_at(
            ["diff", *GIT_NO_DRIVER_ARGS, "--no-renames", "--name-only", "-z", old, new, "--"],
            location,
            max_bytes=MAX_STALE_PATHS * _MAX_STALE_PATH_BYTES,
        )
    except GitError:
        return None
    paths = {path for path in out.decode("utf-8", errors="replace").split("\0") if path}
    return paths if len(paths) <= MAX_STALE_PATHS else None


async def _staleness(
    store: PublishedSource | None, record: PullRecord, guide: Collection, *, newer: bool
) -> dict[str, object]:
    """What a stale guide was written for, what the pull request is now, and what changed.

    ``changed_paths`` are the guide's referenced paths that differ between the guide's
    comparison and the current one, at either end, and ``changed_steps`` the one-based
    steps that cite one; each is ``None`` when that cannot be read. A step that cites no
    changed path still matches the pull request.
    """
    comparison = record.comparison
    pinned = guide.comparison
    head = record.pull.head.sha
    answer: dict[str, object] = {
        "guide": pinned.model_dump(),
        "current": {"merge_base": comparison.base if comparison else None, "head": head},
        "github_newer": newer,
        "history": "unavailable",
        "commit_count": None,
        "commits": [],
        "changed_paths": None,
        "changed_steps": None,
    }
    if store is None:
        return answer
    location = GitLocation.revision(RepositoryStoreTarget(store.git_dir, store.object_format), head)
    try:
        if pinned.head == head:
            answer.update(history="ahead", commit_count=0)
        else:
            answer.update(await _commits_since(location, pinned.head, head))
        changed = (
            await _paths_between(location, pinned.head, head) if pinned.head != head else set()
        )
        if changed is not None and comparison is not None and pinned.merge_base != comparison.base:
            base = await _paths_between(location, pinned.merge_base, comparison.base)
            changed = None if base is None else changed | base
    except GitError:
        return answer
    if changed is not None:
        referenced = {ref.path for item in guide.items for ref in item.references}
        answer["changed_paths"] = sorted(referenced & changed)
        answer["changed_steps"] = [
            at
            for at, item in enumerate(guide.items, start=1)
            if any(ref.path in changed for ref in item.references)
        ]
    return answer


def _head_moved(store: PublishedSource, record: PullRecord) -> bool:
    return record_freshness(
        record, *catalog_member(store.home, store.slug, record.number), now=pulls.utc_now()
    ).head_moved


async def guided_pr(host: PullHost, number: int, step_number: int) -> dict[str, object]:
    """Return the first or selected step of this PR's guide and only its excerpts."""
    served = host.pulls
    record, _, revision = await asyncio.to_thread(
        cached_pull_record, served.home, served.slug, number
    )
    identity: dict[str, object] = {"record_revision": revision}
    if not isinstance(record, PullRecord) or revision is None:
        return {**identity, "state": "not_cached"}
    try:
        guide = await asyncio.to_thread(
            read_guide, (str(served.home), served.slug, number), revision, record.pull.body
        )
    except GuideError as exc:
        return {**identity, "state": "invalid", "message": str(exc)}
    if guide is None:
        return {
            **identity,
            "state": "description_truncated" if record.pull.body_truncated else "absent",
        }
    store = served.published
    published = store if isinstance(store, PublishedSource) else None
    comparison = record.comparison
    newer = published is not None and await asyncio.to_thread(_head_moved, published, record)
    stale = (
        newer
        or guide.comparison.head != record.pull.head.sha
        or (comparison is not None and guide.comparison.merge_base != comparison.base)
    )
    staleness = await _staleness(published, record, guide, newer=newer) if stale else None
    # A stale guide's steps are still read from its own comparison, which the store keeps:
    # the notice above them says what changed since.
    if published is None or (comparison is None and not stale):
        return (
            {**identity, "state": "stale", "stale": staleness}
            if staleness is not None
            else {**identity, "state": "comparison_unavailable"}
        )
    if step_number > len(guide.items):
        return {**identity, "state": "step_not_found"}
    step = guide.items[step_number - 1]
    try:
        references = await _step_references(published, number, guide, step)
    except (DiffSourceError, GitError):
        return (
            {**identity, "state": "stale", "stale": staleness}
            if staleness is not None
            else {**identity, "state": "comparison_unavailable"}
        )
    return {
        **identity,
        "state": "ready" if staleness is None else "stale",
        **({} if staleness is None else {"stale": staleness}),
        "comparison": guide.comparison.model_dump(),
        "step_count": len(guide.items),
        # Every step's title, so the page lists the guide's steps above the one it shows.
        "titles": [item.title for item in guide.items],
        "step": step_number,
        "title": step.title,
        "note": step.note,
        "references": references,
        # The page sets the guide's prose in a KPress article, as it sets a description, and
        # may show this tab before any description has loaded KPress's stylesheets.
        "assets": await asyncio.to_thread(kpress_adapter.document_stylesheets),
    }
