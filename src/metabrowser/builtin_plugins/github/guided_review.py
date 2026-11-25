"""Guided reviews of GitHub pull requests, and the collection format they carry.

A guided review is an author's guide to the exact comparison of a cached pull request: a
collection (`Collection`, contract `metabrowser.collection:Collection/v1`) in a
`guided-review` fence of the description. The format is general and lives here only while
guided reviews are its one carrier (docs/project/architecture/arch-collection-format.md).
"""

from __future__ import annotations

import asyncio
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Final, Literal, TypeGuard

from markdown_it import MarkdownIt
from pydantic import (
    BaseModel,
    ConfigDict,
    Discriminator,
    Field,
    Tag,
    ValidationError,
    model_validator,
)
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
    GitOutputTooLargeError,
    RepositoryStoreTarget,
    run_git_at,
)
from metabrowser.view_routes import format_pull_href

if TYPE_CHECKING:
    from collections.abc import Mapping

    from markdown_it.token import Token
    from pydantic import GetJsonSchemaHandler
    from pydantic.json_schema import JsonSchemaValue
    from pydantic_core.core_schema import CoreSchema

    from metabrowser.builtin_plugins.github.pull_record import Comparison
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
# (INITIAL_PULL_FILES in sidekick.py), in one run of the diff source. A ranged reference
# renders its lines (MAX_EXCERPT_BYTES), and a path alone its file's whole patch
# (MAX_STEP_PATCH_BYTES), or, for a file the rendered route renders, nothing at all.
MAX_REFERENCES = 8
# Every entry of a collection's items counts: an item at the top, a group, and each item in a
# group, so a group holds at most MAX_ITEMS - 1 items. A group is a title and an optional
# note, which parse as an item without its references does, so counting it as an item keeps
# the bound an upper bound on the parse: interleaved, best of nine, at a load average near
# 205 on 10 cores (2026-11-24), 40 items of MAX_REFERENCES ranged references took 139 ms,
# four groups of nine such items (40 entries) 128 ms, and one group of 39 137 ms.
# A reviewer reads a guide one item at a time, and parse_guide costs by the item: markdown-it,
# YAML, JSON Schema and pydantic, in Python that holds the GIL, take 3.3 ms an item of
# MAX_REFERENCES references and 0.6 ms a KiB of text on top. Warm, best of nine, on a
# 10-core Mac at a load average of 13 (2026-11-20): 20 items took 66 ms with the shortest
# text, 40 items 131 ms and 80 items 262 ms, and 40 items with the description filled to
# MAX_BODY_BYTES took 154 ms. The body bound alone admits 480 one-reference items, which
# took 322 ms, so this keeps the largest guide the caps admit near 150 ms. A refused block
# costs about its YAML: _outside_shape refuses a list past these caps, or an undeclared
# key, before the schema runs, which then judges each value in time linear in its size.
# YAML's cost is linear too, and steepest for deep flow nesting: ruamel's scanner keeps a
# possible simple key at each open `[` or `{` and checks them all at every token. So the
# densest block at MAX_BODY_BYTES is groups of `0,` items 61 lists deep, the deepest
# softschema's YAML depth bound admits under `items`: it took 2.69 s of thread CPU to
# refuse, where 40 titles that are long lists took 0.75 s, 64 KiB of `0, ` items 0.72 s,
# of `0,` items 1.10 s, and the largest valid guide 156 ms, best of five, interleaved, at
# a load average of 59 to 138 (2026-11-24; E1 of review E on #677), so upper bounds. A
# bound on flow nesting before YAML runs would bring the deep case near the flat ones,
# but a bracket in a note's text counts toward any bound a scan before YAML can set, so
# none is set. Before the walk, 13,000 undeclared keys there took 105 to 136 s (D1 of
# review D on #677). read_guide pays the parse once for each record revision.
MAX_ITEMS = 40
# A step's ranged excerpts share this budget, each row charged _row_cost: what JSON's
# escaping and a drawn row cost, so even rows of control characters or empty lines stay
# bounded on the wire and in the render. A single long row must fit too. Drawn by the diff
# plugin's file renderer (mountFilePatch), in headless Chrome 152 on the Guided Review page
# from a step's click to its last row laid out, median (range) of three interleaved runs
# with a discarded warm-up, at a load average near 280 on 10 cores, so upper bounds
# (2026-11-23): eight excerpts of 184 rows of 40–60 characters at 63,974 bytes of charge
# took 24 ms (24–50) with no long task, and eight of 800 one-character rows, the old shape,
# 50 ms (31–88).
MAX_EXCERPT_BYTES = MAX_BODY_BYTES
# A step's whole-file references share this budget, in _row_cost's charge too: a path alone
# shows its file's whole patch, which one hydrate run admits up to MAX_FILE_PATCH_BYTES
# (8 MiB) across the step's files, all drawn when the step renders. Measured as
# MAX_EXCERPT_BYTES was, with eight .py files, each hunk an eight-line replacement and a
# 60-line run that folds, from the click to the last row laid out: 66 KB of patch (487,010
# bytes of charge, 720 rows drawn behind 16 fold bars) took 48 ms (36–80), its longest task
# 0–53 ms; 267 KB (1,956,140 bytes of charge, 2,880 rows behind 64 fold bars) 208 ms
# (117–210), longest task 91–103 ms, settled with syntax and changed-run pairs in 368–479 ms;
# 1.07 MB 560 ms with a 388 ms task, and 8.39 MB, the hydrate bound, 9.0 s with 3.5 s tasks.
# The drawing is the cost, not the files' enrichment: one file of 1.05 MB took 510 ms with a
# 379 ms task, as eight of the same total did, though mountFilePatch enriches each file on
# its own where Changes serializes them. So this bounds the drawing just under the largest
# step measured to draw within about 200 ms here, the 1,956,140 bytes of charge. A file past
# what is left says its diff is too large to show in the step, beside its Open full diff
# link. A file the rendered route renders (Markdown, YAML, JSON) cited whole charges
# nothing here: the page draws it from its own reads, which that route's bounds and the
# comparison route's one-file read bound, as Docs and Changes draw it (_step_references).
MAX_STEP_PATCH_BYTES: Final = 1_950_000

# A stale guide's answer names the commits after the guide's head, newest first, and counts
# the rest, for an agent bringing the guide up to date; the page shows none of them. One
# bounded `git log` writes the list.
MAX_STALE_COMMITS: Final = 10
# A commit's subject as the answer carries it, as the Conversation timeline cuts one.
MAX_STALE_SUBJECT_BYTES: Final = 240
# The paths changed since the guide decide which of its steps may no longer match the pull
# request. A change past this many paths is answered as unknown rather than read whole: no
# step is then marked, and the page says some may not match.
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
    """The change a collection's references resolve against: a merge base and a head.

    A guided review needs it, since its description is not versioned with the code it
    describes. v1 requires it of every collection; a carrier without a change, such as a
    repository file, makes it optional, which is not a break.
    """

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


class CollectionGroup(_Model):
    """A titled run of items, read in its place: a title, an optional note, and its items.

    A group's items are items, never groups, so a collection nests one level. A group is
    an entry of the collection as each of its items is.
    """

    title: Prose
    note: Prose | None = None
    items: list[CollectionItem] = Field(min_length=1, max_length=MAX_ITEMS - 1)


def _entry_kind(value: object) -> str:
    """Which an entry of a collection's items is: a group has items of its own, an item none."""
    if isinstance(value, CollectionGroup) or (isinstance(value, dict) and "items" in value):
        return "group"
    return "item"


# The tags pydantic adds to an error's location inside an entry, which no field is named.
_ENTRY_TAGS: Final = frozenset({"item", "group"})


class _GroupWhenItHasItems:
    """The compiled schema's statement of :func:`_entry_kind`: an entry is a group when it
    has `items`, and an item otherwise.

    Pydantic writes the union as a `oneOf`, whose refusal jsonschema places at the entry
    alone, so a range starting at 0 would be refused at `items.0`. As an `if`, the refusal
    is at its place inside the entry, `items.0.references.0.start_line`, as before groups.
    """

    def __get_pydantic_json_schema__(
        self, schema: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        written = handler(schema)
        item, group = written.pop("oneOf")
        return {**written, "if": {"required": ["items"]}, "then": group, "else": item}


type CollectionEntry = Annotated[
    Annotated[CollectionItem, Tag("item")] | Annotated[CollectionGroup, Tag("group")],
    Discriminator(_entry_kind),
    _GroupWhenItHasItems(),
]


class Collection(_Model):
    """Ordered annotated items, each a title, a note, and the references it is about, which
    may be gathered in titled groups.

    The format is general: a guided review is one use, a collection carried in a
    `guided-review` fence and pinned to a comparison. A collection has no prose of its own:
    the document that carries it introduces it, as a pull request's description introduces
    its guide.
    """

    comparison: CollectionComparison
    items: list[CollectionEntry] = Field(min_length=1, max_length=MAX_ITEMS)

    @model_validator(mode="after")
    def _bounded(self) -> Collection:
        # No one list's bound states it, so the schema cannot (MAX_ITEMS).
        if _entry_count(self.items) > MAX_ITEMS:
            raise ValueError(f"a collection has at most {MAX_ITEMS} items and groups")
        return self

    def flat_items(self) -> list[CollectionItem]:
        """The items in reading order, a group's in its place: a guided review's steps."""
        return [
            item
            for entry in self.items
            for item in (entry.items if isinstance(entry, CollectionGroup) else [entry])
        ]


def _entry_count(entries: list[CollectionItem | CollectionGroup]) -> int:
    """Every entry MAX_ITEMS counts: each of *entries*, and each item in a group among them."""
    return len(entries) + sum(
        len(entry.items) for entry in entries if isinstance(entry, CollectionGroup)
    )


def _guide_fence(body: str) -> tuple[Token, list[str]] | None:
    """The description's one top-level guided-review fence and the body's lines, or ``None``.

    Raises :class:`GuideError` for two such fences or one that is not closed.
    """
    if "guided-review" not in body:
        return None
    fences = [
        token
        for token in _MARKDOWN.parse(body)
        if token.type == "fence" and token.level == 0 and token.info.strip() == "guided-review"
    ]
    if not fences:
        return None
    if len(fences) != 1:
        raise GuideError("Use one guided-review block in the pull request description.")
    fence = fences[0]
    mapped = fence.map
    assert mapped is not None
    lines = body.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    marker = re.escape(fence.markup[0])
    if mapped[1] <= mapped[0] + 1 or not re.fullmatch(
        rf" {{0,3}}{marker}{{{len(fence.markup)},}}[ \t]*", lines[mapped[1] - 1]
    ):
        raise GuideError("Close the guided-review block with a matching code fence.")
    return fence, lines


def _read_description(body: str) -> tuple[Collection | None, str]:
    """The guide in the raw PR description, and the description without its block.

    Without a guide the description is *body* itself. Raises :class:`GuideError` for a
    block that is not a guide, which is then the description's own text.
    """
    found = _guide_fence(body)
    if found is None:
        return None, body
    fence, lines = found
    guide = _collection(fence)
    assert fence.map is not None
    start, end = fence.map
    return guide, "\n".join([*lines[:start], *lines[end:]]).strip("\n")


def without_guide(body: str) -> str:
    """*body* without its guided-review block: the description as the guide's introduction.

    Only a block :func:`parse_guide` reads is taken out. A description whose block cannot
    be read keeps it, so its author sees what they wrote.
    """
    try:
        return _read_description(body)[1]
    except GuideError:
        return body


def parse_guide(body: str) -> Collection | None:
    """Read one top-level fenced SoftSchema artifact from the raw PR description."""
    return _read_description(body)[0]


def _collection(fence: Token) -> Collection:
    """The guide one guided-review fence holds, or :class:`GuideError` for why it is none."""
    try:
        document: object = parse_yaml_text(fence.content)
    except ValueError as exc:
        raise GuideError("The guided-review block contains invalid YAML.") from exc
    if not isinstance(document, dict) or set(document) != {"softschema", "collection"}:
        raise GuideError("The guided-review block needs softschema metadata and a collection.")
    if document["softschema"] != {
        "contract": CONTRACT_ID,
        "envelope": _CONTRACT.envelope_key,
        "status": _CONTRACT.status,
    }:
        raise GuideError("The guided-review block needs the enforced Collection/v1 contract.")
    refusal = _outside_shape(document["collection"])
    if refusal is not None:
        raise GuideError(refusal)
    result = validate_artifact(Path("guided-review"), contract=_CONTRACT, document=document)
    if not result.ok:
        raise GuideError(_schema_refusal(result.structural.errors[0].get("path")))
    try:
        return Collection.model_validate(result.values)
    except ValidationError as exc:
        location = ".".join(str(part) for part in exc.errors()[0]["loc"] if part not in _ENTRY_TAGS)
        raise GuideError(f"Invalid guided-review reference at {location}.") from exc


# The refusal of a guide past MAX_ITEMS. No one list's bound states the total, so the
# compiled schema admits such a block, and a refusal in the schema's name would send an
# author who checks the block against it nowhere (A6 of review A on #807).
_TOO_MANY: Final = f"This guide has more than {MAX_ITEMS} steps and groups."


def _outside_shape(collection: object) -> str | None:
    """The refusal of *collection* where it leaves the shape the v1 schema closes, or
    ``None`` within it.

    The shape is each object a mapping of its declared keys and each list within its
    bound. softschema's refusal of undeclared keys is quadratic in their number: it writes
    an error record for each, each with a copy of the whole mapping, so 4,000 keys took 10
    to 12 s to refuse and the body bound's 13,000 about two minutes (D1 of review D on
    #677). A list past its bound costs it a record for each element. This walk refuses both
    first, at a place the schema refuses too, the same place for a block with one problem:
    an object's for its undeclared key, a list's for its length. Which fields hold an object
    or a list of objects is written here by hand, and
    `test_the_shape_walk_reaches_every_nested_model` (tests/test_guided_review.py) fails
    when a model gains one this walk does not visit. The values inside the shape are the
    schema's to judge, at a cost linear in their size.

    An entry is a group or an item as :func:`_entry_kind` tells them apart, as the schema
    does. One bound is the models' alone, since no one list states it: MAX_ITEMS counts a
    group's items with the entries. A block past it is refused in plain words, as soon as
    the count passes it, so a group's long list is never walked; a list past its own
    bound, the entries' or a group's, passes the total too.
    """
    if not _closed(collection, Collection):
        return _schema_refusal([])
    if "comparison" in collection and not _closed(collection["comparison"], CollectionComparison):
        return _schema_refusal(["comparison"])
    if "items" not in collection:
        return None
    entries = collection["items"]
    if not isinstance(entries, list):
        return _schema_refusal(["items"])
    counted = len(entries)
    if counted > MAX_ITEMS:
        return _TOO_MANY
    for at, entry in enumerate(entries):
        if _entry_kind(entry) == "item":
            outside = _outside_item(entry, ["items", at])
        elif not _closed(entry, CollectionGroup):
            return _schema_refusal(["items", at])
        else:
            items = entry["items"]
            if not isinstance(items, list):
                return _schema_refusal(["items", at, "items"])
            counted += len(items)
            if counted > MAX_ITEMS:
                return _TOO_MANY
            places = (
                _outside_item(item, ["items", at, "items", to]) for to, item in enumerate(items)
            )
            outside = next((place for place in places if place is not None), None)
        if outside is not None:
            return _schema_refusal(outside)
    return None


def _outside_item(item: object, at: list[str | int]) -> list[str | int] | None:
    """Where *item*, an item at *at*, leaves the shape the v1 schema closes, or ``None``."""
    if not _closed(item, CollectionItem):
        return at
    if "references" not in item:
        return None
    references = item["references"]
    if not isinstance(references, list) or len(references) > MAX_REFERENCES:
        return [*at, "references"]
    for to, reference in enumerate(references):
        if not _closed(reference, CollectionReference):
            return [*at, "references", to]
    return None


def _closed(value: object, model: type[_Model]) -> TypeGuard[dict[object, object]]:
    """Whether *value* is a mapping of only *model*'s declared keys.

    A view's ``<=`` compares the sizes first, so a mapping of many keys costs nothing here.
    """
    return isinstance(value, dict) and value.keys() <= model.model_fields.keys()


def _schema_refusal(path: object) -> str:
    """The refusal of a block the v1 schema does not admit, at *path* when there is one.

    *path* is a location in the collection, as softschema's error record lists it: only
    declared keys and list indices, since the schema refuses an undeclared key at its
    object, so the message is still the code's own words.
    """
    where = f" at {'.'.join(str(part) for part in path)}" if isinstance(path, list) and path else ""
    return f"The guided-review block does not satisfy the v1 SoftSchema{where}."


@dataclass(frozen=True, slots=True)
class _Read:
    revision: str
    guide: Collection | None
    message: str | None
    # The description the page renders: without its block only when the block is a guide.
    introduction: str


# One parse for each pull request, kept with the record revision (a hash of the record's
# content) that it read, so a Previous or Next click reads the guide the first request
# parsed, the description's render reads the introduction that parse cut, and an edited
# description is parsed once. A guide that does not parse is kept as its message, since it
# costs as much to refuse as to read. Each entry holds at most two bodies of MAX_BODY_BYTES.
_READS: dict[tuple[str, str, int], _Read] = {}
_READS_LOCK: Final = threading.Lock()
_MAX_READS: Final = 16
# The pull requests a parse is under way for. A guided pull request's front page asks for
# its description's render and its guide's first step at once, so the second request waits
# for the first one's parse instead of starting its own (D2 of review D on #677).
_PARSING: dict[tuple[str, str, int], threading.Event] = {}


def _reading(key: tuple[str, str, int], revision: str, body: str) -> _Read:
    """The kept parse of *body* for *key* at *revision*: parsed once, however many ask."""
    while True:
        with _READS_LOCK:
            hit = _READS.get(key)
            if hit is not None and hit.revision == revision:
                return hit
            pending = _PARSING.get(key)
            if pending is None:
                done = _PARSING[key] = threading.Event()
                break
        # Then read the cache again: the parse may have been of another revision, or failed.
        pending.wait()
    try:
        try:
            guide, introduction = _read_description(body)
            hit = _Read(revision, guide, None, introduction)
        except GuideError as exc:
            hit = _Read(revision, None, str(exc), body)
        with _READS_LOCK:
            if key not in _READS and len(_READS) >= _MAX_READS:
                _READS.pop(next(iter(_READS)))
            _READS[key] = hit
        return hit
    finally:
        with _READS_LOCK:
            del _PARSING[key]
        done.set()


def read_guide(key: tuple[str, str, int], revision: str, body: str) -> Collection | None:
    """:func:`parse_guide` of *body*, reused while *key*'s record has this *revision*."""
    hit = _reading(key, revision, body)
    if hit.message is not None:
        raise GuideError(hit.message)
    return hit.guide


def guide_introduction(key: tuple[str, str, int], revision: str, body: str) -> str:
    """:func:`without_guide` of *body*, from the parse :func:`read_guide` keeps. Blocking."""
    return body if "guided-review" not in body else _reading(key, revision, body).introduction


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
        size += _row_cost(line)
        if size > budget:
            return "excerpt_too_large", [], 0
        rows.append({"old": left, "new": right, "op": line.op, "text": line.text})
    return "ready", rows, size


def _row_cost(line: LineRecord) -> int:
    """What one row of an excerpt or a whole patch charges its step's budget.

    JSON's escaping as well as the text: a control character is six bytes on the wire.
    """
    return 80 + 6 * len(line.text)


def _references(
    number: int,
    references: list[CollectionReference],
    changes: dict[str, FileChange],
    patches: dict[str, FilePatch],
    *,
    truncated: bool,
    too_large: frozenset[str] = frozenset(),
    documents: Mapping[str, str] | None = None,
) -> list[dict[str, object]]:
    """Each reference of a step as the page draws it: its excerpt, its file's patch, or
    the format the page draws the whole file in.

    *too_large* are the changes whose patches the diff source left out for their size,
    alone or beside the step's other files. *documents* are the files the step cites whole
    that the rendered route renders, each with its format: such a reference answers
    `rendered`, the format, and no hunks, since the page draws that file whole from the
    comparison route's one-file answer and the rendered route, within their own bounds,
    so it charges nothing to the step's budget for whole files. Every other reference
    answers `rendered` null.
    """
    output: list[dict[str, object]] = []
    remaining = MAX_EXCERPT_BYTES
    whole = MAX_STEP_PATCH_BYTES
    formats = documents or {}
    for reference in references:
        change = changes.get(reference.path)
        href = None
        hunks: list[dict[str, object]] = []
        cut = False
        rendered = formats.get(reference.path) if reference.side is None else None
        if change is None:
            state = "manifest_truncated" if truncated else "path_not_changed"
        elif rendered is not None:
            href = format_pull_href(number, "files", reference.path)
            state = "ready"
        else:
            href = format_pull_href(number, "files", reference.path)
            patch = patches.get(change.id)
            if patch is None:
                state = "patch_too_large" if change.id in too_large else "diff_unavailable"
            elif reference.side is None:
                # The file's whole patch, as Changes shows it, within the step's budget.
                used = sum(_row_cost(line) for hunk in patch.hunks for line in hunk.lines)
                if used > whole:
                    state = "patch_too_large"
                else:
                    whole -= used
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
                "rendered": rendered,
                "href": href,
                "hunks": hunks,
                "truncated": cut,
            }
        )
    return output


async def _step_references(
    store: PublishedSource, number: int, comparison: Comparison, step: CollectionItem
) -> list[dict[str, object]]:
    """The step's references, read from the pull request's current *comparison*.

    A stale guide's steps are read there too, so a guide stays readable after a push, a
    rebase, or a force push, whether or not the store still has the commits it was written
    for: a reference that still resolves shows what the pull request changes now, and one
    that does not says so in its place.

    A file the step cites whole that the rendered route renders, by that route's own rule
    on the manifest's change, both its sides (`rendered_format`), is not read here: the
    page draws it whole as the diff view does, from that file's own reads.
    """
    # The rendered route's module, imported with the step's read rather than this module:
    # the description's render imports this module, and never needs the projections.
    from metabrowser.builtin_plugins.github.pull_rendered_diff import rendered_format

    base, head = comparison.base, comparison.head
    # The record's own comparison is the pull request's kept manifest (pull_manifest.py),
    # the one Changes reads.
    compared = await shared_pull_manifest(store, number, base, head)
    manifest = compared.manifest
    changes = {
        display_path(change): change
        for change in manifest.files
        if (side := change.new or change.old) is not None and side.path_b64 is None
    }
    documents = {
        ref.path: rendered
        for ref in step.references
        if ref.side is None
        and (change := changes.get(ref.path)) is not None
        and (rendered := rendered_format(change)) is not None
    }
    ranged = {ref.path for ref in step.references if ref.side is not None}
    wanted: dict[str, None] = {}
    skipped: set[str] = set()
    for ref in step.references:
        change = changes.get(ref.path)
        if change is None or change.availability is not Availability.ready:
            continue
        if ref.side is None and ref.path in documents:
            continue
        # A file whose changed lines alone charge past a step's whole files is never drawn
        # whole, so it is not read for that: every row charges at least 80 bytes.
        lines = (change.additions or 0) + (change.deletions or 0)
        if ref.path not in ranged and 80 * lines > MAX_STEP_PATCH_BYTES:
            skipped.add(change.id)
        else:
            wanted[change.id] = None
    patches: dict[str, FilePatch] = {}
    too_large: frozenset[str] = frozenset(skipped)
    if wanted:
        target = RepositoryStoreTarget(store.git_dir, store.object_format)
        diff = GitDiffSource(GitLocation.revision(target, head))
        # One run, as Changes asks for its first files. A file past its bound alone, or past
        # what the run had room for beside the others, is too large to show in a step, whose
        # whole files share a budget far below the run's (MAX_STEP_PATCH_BYTES).
        hydrated = await diff.hydrate(compared.resolved, tuple(wanted), manifest=manifest)
        patches = dict(hydrated.patches)
        too_large |= {*hydrated.too_large, *hydrated.deferred}
    return await asyncio.to_thread(
        _references,
        number,
        step.references,
        changes,
        patches,
        truncated=manifest.truncated,
        too_large=too_large,
        documents=documents,
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
    try:
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
    except GitOutputTooLargeError:
        # Git prints a subject whole, so one long enough passes the bound, which is sized
        # for subjects as the answer cuts them: the commits are then counted, not listed.
        return {"history": history, "commit_count": int(count), "commits": []}
    fields = out.decode("utf-8", errors="replace").split("\0")
    commits = [
        {"sha": sha.strip(), "subject": cut_text(subject, MAX_STALE_SUBJECT_BYTES)[0]}
        for sha, subject in zip(fields[0:-1:2], fields[1::2], strict=False)
    ]
    return {"history": history, "commit_count": int(count), "commits": commits}


async def _paths_between(location: GitLocation, old: str, new: str) -> set[str] | None:
    """The paths that differ between commits *old* and *new*, or ``None`` past the bound.

    Git is stopped at the first path past MAX_STALE_PATHS, which the byte bound alone does
    not do: it admits 399,609 paths of 40 bytes, which took 207 ms to decode and split on
    the event loop, where counting NULs to the stop takes 0.08 ms (best of five at a load
    average of 181 on 10 cores, 2026-11-24; D3 of review D on #677). What is left, at most
    MAX_STALE_PATHS paths of up to 4,095 bytes, took 27 ms to split, so a thread does it.
    """
    written = 0

    def past_the_bound(chunk: bytes) -> bool:
        nonlocal written
        written += chunk.count(b"\0")
        return written > MAX_STALE_PATHS

    try:
        out = await run_git_at(
            ["diff", *GIT_NO_DRIVER_ARGS, "--no-renames", "--name-only", "-z", old, new, "--"],
            location,
            max_bytes=MAX_STALE_PATHS * _MAX_STALE_PATH_BYTES,
            stop_when=past_the_bound,
        )
    except GitError:
        # GitOutputCutError among them, which past_the_bound ends the run with.
        return None
    paths = await asyncio.to_thread(_split_paths, out)
    return paths if len(paths) <= MAX_STALE_PATHS else None


def _split_paths(out: bytes) -> set[str]:
    return {path for path in out.decode("utf-8", errors="replace").split("\0") if path}


async def _pins_compare(location: GitLocation, pinned: CollectionComparison) -> bool | None:
    """Whether the guide's ``merge_base`` is an ancestor of its ``head``, as a merge base is.

    ``None`` when the store lacks either commit, which then says nothing about the pins.
    """
    try:
        await run_git_at(["merge-base", "--is-ancestor", pinned.merge_base, pinned.head], location)
    except GitCommandError as exc:
        return False if exc.returncode == 1 else None
    return True


async def _staleness(
    store: PublishedSource | None, record: PullRecord, guide: Collection, *, newer: bool
) -> dict[str, object]:
    """What a stale guide was written for, what the pull request is now, and what changed.

    ``changed_paths`` are the guide's referenced paths whose content differs between the
    guide's comparison and the current one, at either end, compared path by path with no
    rename detection, and ``changed_steps`` the one-based steps that cite one; each is
    ``None`` when that cannot be read, as when the store lacks the guide's head after a
    force push. A step that cites no changed path cites no file whose content changed. Its
    excerpts are the current diff's all the same, which can draw a file another way, as
    when the diff now pairs it with a deleted file as a rename. With *newer*, GitHub reports
    a head this copy lacks, so what changed is unknown: the commits since are this copy's,
    and neither list is read.

    Raises :class:`GuideError` for pins that do not name a comparison: a ``merge_base``
    the store has that is not an ancestor of the guide's ``head``.
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
        if answer["history"] != "unavailable" and await _pins_compare(location, pinned) is False:
            raise GuideError(
                "The guided-review block's merge_base is not the merge base of its head."
            )
        if newer:
            return answer
        changed = (
            await _paths_between(location, pinned.head, head) if pinned.head != head else set()
        )
        if changed is not None and comparison is not None and pinned.merge_base != comparison.base:
            base = await _paths_between(location, pinned.merge_base, comparison.base)
            changed = None if base is None else changed | base
    except GitError:
        return answer
    if changed is not None:
        referenced = {ref.path for item in guide.flat_items() for ref in item.references}
        answer["changed_paths"] = sorted(referenced & changed)
        answer["changed_steps"] = [
            at
            for at, item in enumerate(guide.flat_items(), start=1)
            if any(ref.path in changed for ref in item.references)
        ]
    return answer


def _head_moved(store: PublishedSource, record: PullRecord) -> bool:
    return record_freshness(
        record, *catalog_member(store.home, store.slug, record.number), now=pulls.utc_now()
    ).head_moved


def _outline(guide: Collection) -> tuple[list[dict[str, object]], list[int | None]]:
    """The guide in reading order, as the route answers it, and each step's group.

    The outline is a tree: a group node holds its steps, and a step outside a group is a
    node of its own. Steps are numbered 1 to the step count through the groups, as
    ``step=<k>`` and ``changed_steps`` number them. Each step's group is the index of its
    group's node in the outline, or ``None`` outside one.
    """
    outline: list[dict[str, object]] = []
    groups: list[int | None] = []

    def step(item: CollectionItem, group: int | None) -> dict[str, object]:
        groups.append(group)
        return {"kind": "step", "step": len(groups), "title": item.title}

    for entry in guide.items:
        if isinstance(entry, CollectionGroup):
            at = len(outline)
            children = [step(item, at) for item in entry.items]
            outline.append(
                {"kind": "group", "title": entry.title, "note": entry.note, "children": children}
            )
        else:
            outline.append(step(entry, None))
    return outline, groups


async def guided_review(host: PullHost, number: int, step_number: int) -> dict[str, object]:
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
        if record.pull.body_truncated:
            # The record's bound cut the description, so the block it read is not the one
            # on GitHub: the cut is the cause, not the author's block.
            return {**identity, "state": "description_truncated"}
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
    try:
        staleness = await _staleness(published, record, guide, newer=newer) if stale else None
    except GuideError as exc:
        return {**identity, "state": "invalid", "message": str(exc)}
    # A stale guide's diagnostics ride on every answer, a refusal's too, for an agent that
    # brings the guide up to date; the page says only that the guide may not match.
    diagnostics: dict[str, object] = {} if staleness is None else {"stale": staleness}
    if published is None or comparison is None:
        return {**identity, "state": "comparison_unavailable", **diagnostics}
    steps = guide.flat_items()
    if step_number > len(steps):
        return {**identity, "state": "step_not_found", **diagnostics}
    step = steps[step_number - 1]
    try:
        references = await _step_references(published, number, comparison, step)
    except (DiffSourceError, GitError):
        return {**identity, "state": "comparison_unavailable", **diagnostics}
    outline, groups = _outline(guide)
    return {
        **identity,
        "state": "ready" if staleness is None else "stale",
        **diagnostics,
        # The comparison the excerpts are read from: the pull request's current one.
        "comparison": {"merge_base": comparison.base, "head": comparison.head},
        "step_count": len(steps),
        # Every step's title, so the page names each step it can move to.
        "titles": [item.title for item in steps],
        # The guide's groups and steps, which the page lists above the step it shows.
        "outline": outline,
        "step": step_number,
        "group": groups[step_number - 1],
        "title": step.title,
        "note": step.note,
        "references": references,
        # The page sets the guide's prose in a KPress article, as it sets a description, and
        # may show this tab before any description has loaded KPress's stylesheets.
        "assets": await asyncio.to_thread(kpress_adapter.document_stylesheets),
    }
