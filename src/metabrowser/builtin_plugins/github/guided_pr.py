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

from metabrowser.builtin_plugins.github import pulls
from metabrowser.builtin_plugins.github.pull_catalog import catalog_member
from metabrowser.builtin_plugins.github.pull_freshness import record_freshness
from metabrowser.builtin_plugins.github.pull_manifest import shared_pull_manifest
from metabrowser.builtin_plugins.github.pull_record import MAX_BODY_BYTES, PullRecord, Sha
from metabrowser.builtin_plugins.github.pull_route import cached_pull_record
from metabrowser.cache.acquire import PublishedSource
from metabrowser.diff.adapters.base import DiffSourceError
from metabrowser.diff.adapters.git import GitDiffSource, display_path
from metabrowser.diff.format import Availability, LineOp
from metabrowser.git.process import GitError, GitLocation, RepositoryStoreTarget
from metabrowser.view_routes import format_pull_href

if TYPE_CHECKING:
    from metabrowser.builtin_plugins.github.pull_route import PullHost
    from metabrowser.diff.format import FileChange, FilePatch, Hunk

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
# at 1280×900 on the Guided PR page (2026-11-18). A single long row must fit too.
MAX_EXCERPT_BYTES = MAX_BODY_BYTES

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
    comparison: CollectionComparison
    summary: Prose
    overview: Prose
    items: list[CollectionItem] = Field(min_length=1, max_length=MAX_ITEMS)


def parse_guide(body: str) -> Collection | None:
    """Read one top-level fenced SoftSchema artifact from the raw PR description."""
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
    last = body.replace("\r\n", "\n").replace("\r", "\n").split("\n")[mapped[1] - 1]
    marker = re.escape(fence.markup[0])
    if mapped[1] <= mapped[0] + 1 or not re.fullmatch(
        rf" {{0,3}}{marker}{{{len(fence.markup)},}}[ \t]*", last
    ):
        raise GuideError("Close the guided-pr block with a matching code fence.")
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
            return _hunk_rows(hunk, start, end, old_side, budget)
    return "range_unavailable", [], 0


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
        rows: list[dict[str, object]] = []
        if change is None:
            state = "manifest_truncated" if truncated else "path_not_changed"
        else:
            href = format_pull_href(number, "files", reference.path)
            patch = patches.get(change.id)
            if reference.side is None:
                state = "file"
            elif patch is None:
                state = "diff_unavailable"
            else:
                state, rows, used = _excerpt(patch, reference, remaining)
                remaining -= used
        output.append(
            {
                **reference.model_dump(),
                "state": state,
                "href": href,
                "rows": rows,
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
            if ref.side is not None
            and (change := changes.get(ref.path)) is not None
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
    comparison = record.comparison
    if guide.comparison.head != record.pull.head.sha or (
        comparison is not None and guide.comparison.merge_base != comparison.base
    ):
        return {**identity, "state": "stale"}
    if not isinstance(store, PublishedSource) or comparison is None:
        return {**identity, "state": "comparison_unavailable"}
    if await asyncio.to_thread(_head_moved, store, record):
        return {**identity, "state": "stale"}
    if step_number > len(guide.items):
        return {**identity, "state": "step_not_found"}
    step = guide.items[step_number - 1]
    try:
        references = await _step_references(store, number, guide, step)
    except (DiffSourceError, GitError):
        return {**identity, "state": "comparison_unavailable"}
    return {
        **identity,
        "state": "ready",
        "summary": guide.summary,
        "overview": guide.overview,
        "comparison": guide.comparison.model_dump(),
        "step_count": len(guide.items),
        "step": step_number,
        "title": step.title,
        "note": step.note,
        "references": references,
    }
