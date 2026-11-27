"""Guided reviews of GitHub pull requests and of their native stacks, and the collection
format they carry.

A guided review is an author's guide to the exact comparison of a cached pull request: a
collection (`Collection`, contract `metabrowser.collection:Collection/v1`) in a
`guided-review` fence of the description. A stack's guide is the same record in a
`stack-review` fence of a member's description, pinned to the stack's combined comparison
(`stack_guided_review`). The format is general and lives here only while guided reviews
are its one carrier (docs/project/architecture/arch-collection-format.md).
"""

from __future__ import annotations

import asyncio
import re
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import partial
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
from metabrowser.builtin_plugins.github.pull_manifest import (
    kept_pull_manifest,
    shared_pull_manifest,
)
from metabrowser.builtin_plugins.github.pull_record import (
    MAX_BODY_BYTES,
    PullRecord,
    Sha,
    cut_text,
)
from metabrowser.builtin_plugins.github.pull_route import (
    cached_pull_record,
    comparison_route,
    image_route,
    rendered_route,
)
from metabrowser.builtin_plugins.github.pull_text_render import render_text
from metabrowser.cache.acquire import PublishedSource
from metabrowser.cache.paths import MAX_PULL_REQUEST_NUMBER
from metabrowser.diff.adapters.base import DiffSourceError
from metabrowser.diff.adapters.git import GitDiffSource, display_path
from metabrowser.diff.format import Availability, Hunk, LineOp, LineRecord
from metabrowser.diff.markdown_projection_worker import InertRenderRefused, RefusalCode
from metabrowser.git.process import (
    GIT_NO_DRIVER_ARGS,
    GitCommandError,
    GitError,
    GitLocation,
    GitOutputTooLargeError,
    RepositoryStoreTarget,
    run_git_at,
)
from metabrowser.http_caching import store_tag
from metabrowser.view_routes import format_commit_href, format_pull_href, format_stack_href

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping, Sequence

    from markdown_it.token import Token
    from pydantic import GetJsonSchemaHandler
    from pydantic.config import JsonDict
    from pydantic.json_schema import JsonSchemaValue
    from pydantic_core.core_schema import CoreSchema

    from metabrowser.builtin_plugins.diff.comparison_cache import ResolvedManifest
    from metabrowser.builtin_plugins.github.pull_list import ListedRepository
    from metabrowser.builtin_plugins.github.pull_route import PullHost
    from metabrowser.builtin_plugins.github.pull_stacks import NativeStack
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
# The blocks a description may carry, one of each: the pull request's own guide, and the
# guide of a native stack the pull request is a member of.
GUIDE_FENCE: Final = "guided-review"
STACK_FENCE: Final = "stack-review"

# Each item hydrates at most as many paths as the measured first paint of Changes
# (INITIAL_PULL_FILES in sidekick.py), in one run of the diff source. A ranged reference
# renders its lines (MAX_EXCERPT_BYTES), and a path alone its file's whole patch
# (MAX_STEP_PATCH_BYTES), or, for a file the rendered route renders, nothing at all.
# A `{pull, path}` reads its own pull request's kept manifest instead and runs the diff
# source once for each pull request, so a step citing files of several pull requests
# makes at most this many runs, and never lists a comparison (_pull_files); a `{pull}`
# reads a record and a catalog row, and every `{commit}` of a step shares one bounded
# `git log` (_commit_targets). The worst cases, on this repository's own cache with the
# carrier #838, interleaved, best and median of nine, at a load average near 120 on
# 10 cores (2026-11-25, timing _step_references): eight `{path}` of the carrier took
# 36/38 ms; eight `{pull, path}` in eight pull requests with kept manifests 213/265 ms,
# and with none kept (`not_cached`) 9/11 ms, where listing one cold comparison instead
# cost 68/80 ms for each pull request; eight `{pull}` 5/5 ms; eight `{commit}` 23/27 ms,
# against 157/171 ms for eight separate `git log` runs.
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
# A commit's subject as the answer carries it, as the Conversation timeline cuts one: a
# stale guide's commits', and a `{commit}` reference's.
MAX_STALE_SUBJECT_BYTES: Final = 240
# One commit's line of `git log`, its ID or date and its subject, at most the subject's
# bound written in four-byte characters, as `_commits_since` sizes each of its lines.
_MAX_COMMIT_ROW_BYTES: Final = 200 + 4 * MAX_STALE_SUBJECT_BYTES
# A commit's line without its subject: a 64-hex ID, a time in epoch seconds, and their NULs.
_MAX_COMMIT_ID_ROW_BYTES: Final = 128
# The paths changed since the guide decide which of its steps may no longer match the pull
# request. A change past this many paths is answered as unknown rather than read whole: no
# step is then marked, and the page says some may not match.
MAX_STALE_PATHS: Final = 4000
# A path as `git diff --name-only -z` writes it is at most a filesystem path, 4096 bytes.
_MAX_STALE_PATH_BYTES: Final = 4096
# The rendered notes kept with a guide's parse (`_Read.notes`), in characters of HTML, so a
# step read again, after a reload or from another page, takes its note from here and not
# from the Markdown child. A note is a text of the description, so a guide's notes total at
# most MAX_BODY_BYTES; measured through the child (`render_text` in pull_text_render.py) at a
# load average near 386 on 10 cores (2026-11-24), a note's inert HTML was 1.0 to 1.2 times
# its text for the four notes of tests/fixtures/guided-review/, and, for 64 KiB of one
# construct, 2.8 times for emphasis, 13 for links, and 27 for images, the largest found. So
# this keeps every note of a guide whose notes fill its description at up to four times
# their text, and a guide written to expand further only up to it, which bounds the
# _MAX_READS kept parses at 4 MiB of notes. A note past it renders again each time it is
# read: KPress keeps the render by its key, and the child reduces it to the allowlist again.
_MAX_KEPT_NOTE_CHARS: Final = 4 * MAX_BODY_BYTES
# What a guide's note is called where it renders (`render_text`): its log name and its key.
_NOTE_PART: Final = "guided-review-note"

# Why a note's render did not come, as the pull-markdown route answers a text's: the Markdown
# child's refusal, or KPress's failure.
type NoteRefusal = RefusalCode | Literal["render_failed"]

type Prose = Annotated[str, Field(min_length=1)]
type LineNumber = Annotated[int, Field(ge=1)]
type PullNumber = Annotated[int, Field(ge=1, le=MAX_PULL_REQUEST_NUMBER)]


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


type ReferenceKind = Literal["file", "pull_file", "pull", "commit"]

# The fields a kind of reference does not take, stated in the compiled schema as an `if` on
# the field that names the kind, as groups' `if` on `items` is (`_GroupWhenItHasItems`), so
# a refusal keeps its place: `{commit, path}` is refused at `references.0.path`, and a
# reference that names nothing at `references.0`. A null field is absent, as the model
# reads it, so each `if` holds only for a value of its field, and a field a kind does not
# take may be null: a reference the route answers, which names every field and nulls those
# its kind lacks, parses back as the same kind. `CollectionReference._usable_reference`
# states the same for a reference made in code.
_RANGE: Final = ("side", "start_line", "end_line")


# A value, of any type: the field's own schema refuses one of the wrong type, at the field.
_VALUE: Final[JsonDict] = {"not": {"type": "null"}}


def _forbidden(*fields: str) -> JsonDict:
    return {"properties": {name: {"type": "null"} for name in fields}}


_REFERENCE_KINDS: Final[JsonDict] = {
    "if": {"required": ["commit"], "properties": {"commit": _VALUE}},
    "then": _forbidden("path", "pull", *_RANGE),
    "else": {
        "if": {"required": ["pull"], "properties": {"pull": _VALUE}},
        "then": _forbidden(*_RANGE),
        "else": {"required": ["path"]},
    },
}


class CollectionReference(_Model):
    """What an item is about, one of four kinds, each spelled one way.

    - `{path}`, a file of the carrier's comparison, whole, or with a `side` and an
      inclusive line range;
    - `{pull, path}`, a file as pull request `pull` changes it, whole, in that pull
      request's current comparison, which the collection does not pin, so a range into it
      would come to point at other lines;
    - `{pull}`, a pull request;
    - `{commit}`, a commit, by its full ID.

    Every kind is valid in every carrier, and a carrier resolves each from what it has
    cached, fetching nothing.
    """

    model_config = ConfigDict(json_schema_extra=_REFERENCE_KINDS)

    path: Prose | None = None
    side: Literal["old", "new"] | None = None
    start_line: LineNumber | None = None
    end_line: LineNumber | None = None
    pull: PullNumber | None = None
    commit: Sha | None = None

    @property
    def kind(self) -> ReferenceKind:
        if self.commit is not None:
            return "commit"
        if self.pull is None:
            return "file"
        return "pull" if self.path is None else "pull_file"

    @property
    def ranged(self) -> bool:
        return self.side is not None or self.start_line is not None or self.end_line is not None

    @model_validator(mode="after")
    def _usable_reference(self) -> CollectionReference:
        if self.commit is not None:
            if self.path is not None or self.pull is not None or self.ranged:
                raise ValueError("a commit reference names its commit alone")
            return self
        if self.pull is not None and self.ranged:
            raise ValueError("a pull request's file takes no range")
        if self.path is None:
            if self.pull is None:
                raise ValueError("a reference names a path, a pull request, or a commit")
            return self
        format_pull_href(1, "files", self.path)
        if not self.ranged:
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


def _guide_fence(body: str, name: str = GUIDE_FENCE) -> tuple[Token, list[str]] | None:
    """The description's one top-level fence named *name* and the body's lines, or ``None``.

    Raises :class:`GuideError` for two such fences or one that is not closed.
    """
    if name not in body:
        return None
    fences = [
        token
        for token in _MARKDOWN.parse(body)
        if token.type == "fence" and token.level == 0 and token.info.strip() == name
    ]
    if not fences:
        return None
    if len(fences) != 1:
        raise GuideError(f"Use one {name} block in the pull request description.")
    fence = fences[0]
    mapped = fence.map
    assert mapped is not None
    lines = body.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    marker = re.escape(fence.markup[0])
    if mapped[1] <= mapped[0] + 1 or not re.fullmatch(
        rf" {{0,3}}{marker}{{{len(fence.markup)},}}[ \t]*", lines[mapped[1] - 1]
    ):
        raise GuideError(f"Close the {name} block with a matching code fence.")
    return fence, lines


@dataclass(frozen=True, slots=True)
class _Description:
    """What a description carries: each block's guide, or why it is none, and the
    description without the blocks that read as guides."""

    guide: Collection | None
    message: str | None
    stack: Collection | None
    stack_message: str | None
    introduction: str


def carries_guide(body: str) -> bool:
    """Whether *body* may hold a guide's block of either kind: the cheap test before a parse."""
    return GUIDE_FENCE in body or STACK_FENCE in body


def _read_description(body: str) -> _Description:
    """The guides in the raw PR description, each or why it is none, and the description
    without the blocks that are guides.

    Without a block the description is *body* itself. A block that is not a guide stays in
    the introduction, so its author sees what they wrote, and does not keep the other block
    from being read.
    """
    found: dict[str, tuple[Collection | None, str | None]] = {}
    cut: list[tuple[int, int]] = []
    # The body's lines as a fence found them, which a cut indexes.
    lines: list[str] = []
    for name in (GUIDE_FENCE, STACK_FENCE):
        try:
            fenced = _guide_fence(body, name)
            if fenced is None:
                found[name] = (None, None)
                continue
            fence, lines = fenced
            found[name] = (_collection(fence, name), None)
        except GuideError as exc:
            found[name] = (None, str(exc))
            continue
        assert fence.map is not None
        cut.append((fence.map[0], fence.map[1]))
    introduction = body
    if cut:
        kept = [line for at, line in enumerate(lines) if not any(a <= at < b for a, b in cut)]
        introduction = "\n".join(kept).strip("\n")
    (guide, message), (stack, stack_message) = found[GUIDE_FENCE], found[STACK_FENCE]
    return _Description(guide, message, stack, stack_message, introduction)


def without_guide(body: str) -> str:
    """*body* without its guide blocks: the description as the guide's introduction.

    Only a block :func:`parse_guide` or :func:`parse_stack_guide` reads is taken out. A
    block that cannot be read stays, so its author sees what they wrote.
    """
    return _read_description(body).introduction


def parse_guide(body: str) -> Collection | None:
    """Read one top-level fenced SoftSchema artifact from the raw PR description."""
    read = _read_description(body)
    if read.message is not None:
        raise GuideError(read.message)
    return read.guide


def parse_stack_guide(body: str) -> Collection | None:
    """Read the description's one top-level `stack-review` block, as :func:`parse_guide`
    reads its guide."""
    read = _read_description(body)
    if read.stack_message is not None:
        raise GuideError(read.stack_message)
    return read.stack


def _collection(fence: Token, name: str = GUIDE_FENCE) -> Collection:
    """The guide one fence named *name* holds, or :class:`GuideError` for why it is none."""
    try:
        document: object = parse_yaml_text(fence.content)
    except ValueError as exc:
        raise GuideError(f"The {name} block contains invalid YAML.") from exc
    if not isinstance(document, dict) or set(document) != {"softschema", "collection"}:
        raise GuideError(f"The {name} block needs softschema metadata and a collection.")
    if document["softschema"] != {
        "contract": CONTRACT_ID,
        "envelope": _CONTRACT.envelope_key,
        "status": _CONTRACT.status,
    }:
        raise GuideError(f"The {name} block needs the enforced Collection/v1 contract.")
    refusal = _outside_shape(document["collection"])
    if refusal is not None:
        raise GuideError(refusal)
    result = validate_artifact(
        Path(name), contract=_CONTRACT, document=document, require=("structural",)
    )
    if not result.ok:
        raise GuideError(_schema_refusal(result.structural.errors[0].get("path"), name))
    try:
        return Collection.model_validate(result.values)
    except ValidationError as exc:
        location = ".".join(str(part) for part in exc.errors()[0]["loc"] if part not in _ENTRY_TAGS)
        raise GuideError(f"Invalid {name} reference at {location}.") from exc


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


def _schema_refusal(path: object, name: str = GUIDE_FENCE) -> str:
    """The refusal of a block the v1 schema does not admit, at *path* when there is one.

    *path* is a location in the collection, as softschema's error record lists it: only
    declared keys and list indices, since the schema refuses an undeclared key at its
    object, so the message is still the code's own words.
    """
    where = f" at {'.'.join(str(part) for part in path)}" if isinstance(path, list) and path else ""
    return f"The {name} block does not satisfy the v1 SoftSchema{where}."


@dataclass(frozen=True, slots=True)
class _Read:
    revision: str
    guide: Collection | None
    message: str | None
    # The description the page renders: without each block only when the block is a guide.
    introduction: str
    # The description's stack guide (`stack-review`), or why its block is none.
    stack: Collection | None = None
    stack_message: str | None = None
    # Each note's inert HTML, by its text, once it rendered (`_rendered_note`), within
    # _MAX_KEPT_NOTE_CHARS. Only the event loop reads or writes it.
    notes: dict[str, str] = field(default_factory=dict[str, str])


# One parse for each pull request, kept with the record revision (a hash of the record's
# content) that it read, so a Previous or Next click reads the guide the first request
# parsed, the description's render reads the introduction that parse cut, and an edited
# description is parsed once. A guide that does not parse is kept as its message, since it
# costs as much to refuse as to read. Each entry holds at most two bodies of MAX_BODY_BYTES,
# and its notes' renders, at most _MAX_KEPT_NOTE_CHARS.
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
        read = _read_description(body)
        hit = _Read(
            revision,
            read.guide,
            read.message,
            read.introduction,
            read.stack,
            read.stack_message,
        )
        with _READS_LOCK:
            if key not in _READS and len(_READS) >= _MAX_READS:
                _READS.pop(next(iter(_READS)))
            _READS[key] = hit
        return hit
    finally:
        with _READS_LOCK:
            del _PARSING[key]
        done.set()


def _kept_read(key: tuple[str, str, int], revision: str, body: str) -> _Read:
    """The kept parse of a readable guide, or a description without one. Blocking.

    Raises :class:`GuideError` when the description's guided-review block is not a guide.
    """
    hit = _reading(key, revision, body)
    if hit.message is not None:
        raise GuideError(hit.message)
    return hit


def read_guide(key: tuple[str, str, int], revision: str, body: str) -> Collection | None:
    """:func:`parse_guide` of *body*, reused while *key*'s record has this *revision*."""
    return _kept_read(key, revision, body).guide


def guide_introduction(key: tuple[str, str, int], revision: str, body: str) -> str:
    """:func:`without_guide` of *body*, from the parse :func:`read_guide` keeps. Blocking."""
    return _reading(key, revision, body).introduction if carries_guide(body) else body


def stack_guide_carrier(
    home: Path, slug: str, members: Sequence[tuple[int, PullRecord | None, str | None]]
) -> tuple[int, str] | None:
    """The member whose description carries the stack's guide, and its record revision: the
    top-most of *members*, `(number, record, revision)` bottom first, whose description
    has a `stack-review` block, readable or not, so a block that cannot be read is found and
    says why. ``None`` when no member's cached description has one. Blocking: a description
    is parsed only when it names the block, and that parse is kept as a guide's is."""
    for number, record, revision in reversed(members):
        if record is None or revision is None or STACK_FENCE not in record.pull.body:
            continue
        hit = _reading((str(home), slug, number), revision, record.pull.body)
        if hit.stack is not None or hit.stack_message is not None:
            return number, revision
    return None


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


@dataclass(frozen=True, slots=True)
class _Files:
    """What one comparison offers a step's file references: its changed files by path, the
    patches read for the step, the changes left out for their size, alone or beside the
    step's other files, the files the page draws whole with each one's format, and whether
    the listing was cut short."""

    changes: Mapping[str, FileChange]
    patches: Mapping[str, FilePatch] = field(default_factory=dict[str, "FilePatch"])
    truncated: bool = False
    too_large: frozenset[str] = frozenset()
    documents: Mapping[str, str] = field(default_factory=dict[str, str])


@dataclass(frozen=True, slots=True)
class _PullFiles:
    """A pull request's current comparison, which its `{pull, path}` references read: its
    files, and its pins and routes, which the page draws a document from; or, in *state*,
    why there are none, `not_cached` or `comparison_unavailable`."""

    files: _Files | None
    comparison: dict[str, object] | None
    state: str | None = None


@dataclass(slots=True)
class _Budget:
    """A step's two budgets, which its references draw on in order, in every comparison
    they read: what is left of MAX_EXCERPT_BYTES for its ranges, and of
    MAX_STEP_PATCH_BYTES for its whole files."""

    excerpts: int
    whole: int


# What a `{pull}` or a `{commit}` resolves to: its state, its address, and what the row
# names, or None.
type _Target = tuple[str, str | None, dict[str, object] | None]


def _file_answer(
    reference: CollectionReference, files: _Files, href: str | None, budget: _Budget
) -> dict[str, object]:
    """A file reference as the page draws it: its excerpt, its file's patch, or the format
    the page draws the whole file in, within *budget*.

    A file the step cites whole that the rendered route renders, one of *files*'
    documents, answers `rendered`, its format, and no hunks, since the page draws it whole
    from the comparison route's one-file answer and the rendered route, within their own
    bounds, so it charges nothing to the step's budget for whole files. Every other
    reference answers `rendered` null.
    """
    path = reference.path
    assert path is not None
    change = files.changes.get(path)
    rendered = None if reference.ranged else files.documents.get(path)
    hunks: list[dict[str, object]] = []
    cut = False
    if change is None:
        state = "manifest_truncated" if files.truncated else "path_not_changed"
        href = None
    elif rendered is not None:
        state = "ready"
    elif (patch := files.patches.get(change.id)) is None:
        state = "patch_too_large" if change.id in files.too_large else "diff_unavailable"
    elif not reference.ranged:
        # The file's whole patch, as Changes shows it, within the step's budget.
        used = sum(_row_cost(line) for hunk in patch.hunks for line in hunk.lines)
        if used > budget.whole:
            state = "patch_too_large"
        else:
            budget.whole -= used
            state = "ready"
            hunks = [hunk.model_dump(mode="json") for hunk in patch.hunks]
            cut = patch.truncated
    else:
        state, hunks, used = _excerpt(patch, reference, budget.excerpts)
        budget.excerpts -= used
    return {
        "state": state,
        "rendered": rendered,
        "href": href,
        "hunks": hunks,
        "truncated": cut,
        **({"deleted": True} if change is not None and change.new is None else {}),
    }


def _references(
    href: Callable[[str], str],
    references: Sequence[CollectionReference],
    files: _Files,
    *,
    pulls: Mapping[int, _PullFiles] | None = None,
    targets: Mapping[int, _Target] | None = None,
) -> list[dict[str, object]]:
    """Each reference of a step as the page draws it, in its order.

    A `{path}` reads *files*, the carrier's comparison, and its address is *href* of its
    path; a `{pull, path}` reads its pull request's comparison in *pulls*, and answers that
    comparison too, which the page draws a document from; a `{pull}` and a `{commit}` are
    their entry of *targets*, by the reference's place in the step. Every answer has every
    field, null where its kind has none.
    """
    budget = _Budget(MAX_EXCERPT_BYTES, MAX_STEP_PATCH_BYTES)
    output: list[dict[str, object]] = []
    for at, reference in enumerate(references):
        kind = reference.kind
        comparison: dict[str, object] | None = None
        target: dict[str, object] | None = None
        if kind == "file":
            assert reference.path is not None
            answer = _file_answer(reference, files, href(reference.path), budget)
        elif kind == "pull_file":
            assert reference.pull is not None and reference.path is not None
            pulled = (pulls or {}).get(reference.pull)
            # The file in that pull request's Changes, which loads the pull request when this
            # copy has not read it.
            address = format_pull_href(reference.pull, "files", reference.path)
            if pulled is None or pulled.files is None:
                state = pulled.state if pulled is not None else None
                answer = {
                    "state": state or "comparison_unavailable",
                    "rendered": None,
                    "href": address,
                    "hunks": [],
                    "truncated": False,
                }
            else:
                answer = _file_answer(reference, pulled.files, address, budget)
                comparison = pulled.comparison
        else:
            state, address, target = (targets or {}).get(at, ("not_cached", None, None))
            answer = {
                "state": state,
                "rendered": None,
                "href": address,
                "hunks": [],
                "truncated": False,
            }
        output.append(
            {
                "kind": kind,
                **reference.model_dump(),
                **answer,
                # A `{pull, path}`'s comparison, that pull request's pins and routes; null
                # for every other kind, which the step's own comparison answers.
                "comparison": comparison,
                # What a `{pull}` or a `{commit}` names on its row; null for a file.
                "target": target,
            }
        )
    return output


@dataclass(frozen=True, slots=True)
class _Carrier:
    """What a guide's references resolve against: the store and the pull requests cached
    beside it, the carrier's comparison, the address of a file of it on the carrier's page,
    and the stack a `{pull}` is placed in first.

    *manifest* lists the carrier's comparison, and is asked only by a step that cites one
    of its files. A `{pull}` in more than one stack is placed in *stack* when it is a
    member, else in the first stack that holds *pull*, else in the first that holds it.
    *links* is where a commit's page reads Git when that is not the store, a served
    checkout's (:func:`_commit_targets`), and ``None`` on a mirror.
    """

    store: PublishedSource
    home: Path
    slug: str
    head: str
    manifest: Callable[[], Awaitable[ResolvedManifest]]
    href: Callable[[str], str]
    repository: ListedRepository | None = None
    stack: int | None = None
    pull: int | None = None
    links: GitLocation | None = None


async def _read_files(
    store: PublishedSource,
    compared: ResolvedManifest,
    head: str,
    references: Sequence[CollectionReference],
) -> _Files:
    """The files of *compared*, the comparison to *head*, that *references* cite, and the
    patches they need, read in one run of the diff source.

    A file cited whole that the rendered route renders, by that route's own rule on the
    manifest's change, both its sides (`rendered_format`), is not read here: the page draws
    it whole as the diff view does, from that file's own reads.
    """
    # The rendered route's module, imported with the step's read rather than this module:
    # the description's render imports this module, and never needs the projections.
    # Importing it after pull_markdown.py took 164 to 364 ms over three runs (2026-11-25,
    # load average near 212 on 10 cores). No test holds this boundary yet (mb-iqlb).
    from metabrowser.builtin_plugins.github.pull_rendered_diff import rendered_format

    manifest = compared.manifest
    changes = {
        display_path(change): change
        for change in manifest.files
        if (side := change.new or change.old) is not None and side.path_b64 is None
    }
    cited = [(ref, ref.path) for ref in references if ref.path is not None]
    documents = {
        path: rendered
        for ref, path in cited
        if not ref.ranged
        and (change := changes.get(path)) is not None
        and (rendered := rendered_format(change)) is not None
    }
    ranged = {path for ref, path in cited if ref.ranged}
    wanted: dict[str, None] = {}
    skipped: set[str] = set()
    for ref, path in cited:
        change = changes.get(path)
        if change is None or change.availability is not Availability.ready:
            continue
        if not ref.ranged and path in documents:
            continue
        # A file whose changed lines alone charge past a step's whole files is never drawn
        # whole, so it is not read for that: every row charges at least 80 bytes.
        lines = (change.additions or 0) + (change.deletions or 0)
        if path not in ranged and 80 * lines > MAX_STEP_PATCH_BYTES:
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
    return _Files(changes, patches, manifest.truncated, too_large, documents)


async def _pull_files(
    carrier: _Carrier, references: Sequence[CollectionReference]
) -> dict[int, _PullFiles]:
    """Each pull request the step's `{pull, path}` references cite, at its record's current
    comparison: its kept manifest, the one its Changes reads, and the patches its cited
    files need, one run of the diff source for each pull request.

    A pull request with no record answers `not_cached`, as does one with no manifest kept
    for its record's comparison, which is listed here only by its own page, when the reader
    opens it: a refresh keeps one (`prepare_pull_manifest`), and listing a whole comparison
    on this request, once for each pull request a step cites, is what `MAX_REFERENCES`
    leaves out. One whose record has no comparison, or whose comparison the store cannot
    read now, answers `comparison_unavailable`.
    """
    cited: dict[int, list[CollectionReference]] = {}
    for ref in references:
        if ref.kind == "pull_file" and ref.pull is not None:
            cited.setdefault(ref.pull, []).append(ref)
    found: dict[int, _PullFiles] = {}
    store = carrier.store
    for number, refs in cited.items():
        record, _, _ = await asyncio.to_thread(
            cached_pull_record, carrier.home, carrier.slug, number
        )
        if not isinstance(record, PullRecord):
            found[number] = _PullFiles(None, None, "not_cached")
            continue
        comparison = record.comparison
        if comparison is None:
            found[number] = _PullFiles(None, None, "comparison_unavailable")
            continue
        base, head = comparison.base, comparison.head
        compared = await asyncio.to_thread(kept_pull_manifest, store, number, base, head)
        if compared is None:
            found[number] = _PullFiles(None, None, "not_cached")
            continue
        try:
            files = await _read_files(store, compared, head, refs)
        except (DiffSourceError, GitError):
            found[number] = _PullFiles(None, None, "comparison_unavailable")
            continue
        tag = store_tag(store.git_dir)
        found[number] = _PullFiles(
            files,
            {
                "merge_base": base,
                "head": head,
                "route": comparison_route(record, store=tag),
                "image_route": image_route(number, base, head, store=tag),
                "rendered_route": rendered_route(number, base, head, store=tag),
            },
        )
    return found


def _stack_place(
    stacks: Sequence[NativeStack], number: int, within: int | None
) -> dict[str, int | bool] | None:
    """Pull request *number*'s place in stack *within*, the guide's own, when it is a
    member, else in the first stack that holds it, as `{number, place, count, own}`, or
    ``None`` in none. *own* says the place is in the guide's own stack, which goes without
    saying, so its row shows the position bare, and another stack's it names
    (`namedStackPosition` in pull-stacks.js; docs/design-system.md, "Stacks")."""
    holding = [stack for stack in stacks if number in stack.pulls]
    if not holding:
        return None
    stack = next((stack for stack in holding if stack.number == within), holding[0])
    return {
        "number": stack.number,
        "place": stack.pulls.index(number) + 1,
        "count": len(stack.pulls),
        "own": stack.number == within,
    }


def _pull_targets(carrier: _Carrier, cited: Sequence[tuple[int, int]]) -> dict[int, _Target]:
    """Each `{pull}` of *cited*, by its place in the step and its number: its title, state,
    and author, from its cached record or else its catalog row, and its place in its stack, from
    the stack snapshot, or `not_cached` when this copy knows neither. Blocking and bounded:
    the snapshot once, and a record and a catalog row for each, through their parse caches.
    """
    from metabrowser.builtin_plugins.github.pull_stack import member_state, snapshot_stacks

    stacks = snapshot_stacks(carrier.repository) if carrier.repository is not None else ()
    within = carrier.stack
    if within is None and carrier.pull is not None:
        within = next((stack.number for stack in stacks if carrier.pull in stack.pulls), None)
    found: dict[int, _Target] = {}
    for at, number in cited:
        record, _, _ = cached_pull_record(carrier.home, carrier.slug, number)
        held = record if isinstance(record, PullRecord) else None
        row = catalog_member(carrier.home, carrier.slug, number)[1]
        href = format_pull_href(number)
        if held is None and row is None:
            found[at] = ("not_cached", href, None)
            continue
        title = held.pull.title if held is not None else row.title if row is not None else None
        # Its author follows its number wherever it is named (docs/design-system.md, "Authors
        # Follow Pull Requests").
        author = held.pull.author if held is not None else row.author if row is not None else None
        avatar = (
            held.pull.author_avatar_url
            if held is not None
            else row.author_avatar_url
            if row is not None
            else None
        )
        state = member_state(
            held,
            row.state if row is not None else None,
            row.draft if row is not None else False,
            row.merged if row is not None else False,
        )
        place = _stack_place(stacks, number, within)
        found[at] = (
            "ready",
            href,
            {"title": title, "state": state, "stack": place, "author": author, "avatar": avatar},
        )
    return found


async def _commit_targets(
    location: GitLocation, commits: Sequence[str], links: GitLocation | None
) -> dict[str, _Target]:
    """Each `{commit}` a step cites, by its ID: its subject, cut as a stale guide's commits'
    are, and when it was committed, or `commit_unavailable` when the store has no such
    commit. Its address is `/commit/<sha>`, whose page reads the commit where the session
    reads Git, *links* when that is not the store: on a served checkout, a commit the store
    holds and the checkout does not, as a pull request's branch the store alone fetched,
    is answered with no address, and its row says it is not in this checkout.

    One `git log` over every ID, and one more at *links* over those found, each bounded by
    its commits, a line each as :func:`_commits_since` sizes one. Git prints a subject
    whole, so a run past its bound is read again for the commits and times alone, and
    names no subject.
    The time is read as epoch seconds and written in UTC with a `Z`, as GitHub writes a
    time, since `%cI` keeps the committer's offset and Git 2.43 writes UTC's as `+00:00`.
    """
    wanted = list(dict.fromkeys(commits))
    if not wanted:
        return {}
    try:
        rows = await _commit_rows(location, wanted, "%H%x00%ct%x00%s", _MAX_COMMIT_ROW_BYTES)
        if rows is None:
            rows = await _commit_rows(location, wanted, "%H%x00%ct%x00", _MAX_COMMIT_ID_ROW_BYTES)
    except GitError:
        rows = None
    found = {row[0]: row for row in rows or () if len(row) == 3 and row[0] in wanted}
    shown = set(found)
    if links is not None and found:
        try:
            present = await _commit_rows(links, list(found), "%H", _MAX_COMMIT_ID_ROW_BYTES)
        except GitError:
            # What the session's Git holds is unknown: the commit's page says what it can.
            present = None
        if present is not None:
            shown = {row[0] for row in present}
    targets: dict[str, _Target] = {}
    for commit in wanted:
        row = found.get(commit)
        if row is None:
            targets[commit] = ("commit_unavailable", None, None)
            continue
        _, when, subject = row
        targets[commit] = (
            "ready",
            format_commit_href(commit) if commit in shown else None,
            {
                "subject": cut_text(subject, MAX_STALE_SUBJECT_BYTES)[0] or None,
                "committed_at": _utc_text(when),
            },
        )
    return targets


async def _commit_rows(
    location: GitLocation, commits: Sequence[str], fields: str, row_bytes: int
) -> list[list[str]] | None:
    """`git log`'s *fields*, separated by `%x00`, of each of *commits* that *location* holds
    as a commit, in no order, or ``None`` past *row_bytes* a commit. An ID that names no
    commit, missing or another kind of object, is left out (`--ignore-missing`), never
    refused. A line a commit: a subject is its first paragraph on one line.

    One run reads every ID. A Git that fails that run for one ID instead of leaving it out
    would leave the step with no commit at all, so a failed run is read again one ID a run,
    the separate runs whose cost is measured beside MAX_REFERENCES, and an ID whose own run
    fails is left out. The first run's error is raised only when every ID's run fails too,
    as when *location* cannot be read."""
    try:
        return await _log_rows(location, commits, fields, row_bytes)
    except GitCommandError as failed:
        if len(commits) < 2:
            raise
        rows: list[list[str]] = []
        read = False
        for commit in commits:
            try:
                found = await _log_rows(location, [commit], fields, row_bytes)
            except GitCommandError:
                continue
            if found is None:
                return None
            read = True
            rows.extend(found)
        if not read:
            raise failed
        return rows


async def _log_rows(
    location: GitLocation, commits: Sequence[str], fields: str, row_bytes: int
) -> list[list[str]] | None:
    """One `git log` of :func:`_commit_rows`, over *commits*."""
    try:
        out = await run_git_at(
            [
                "log",
                *GIT_NO_DRIVER_ARGS,
                "--no-walk=unsorted",
                "--ignore-missing",
                f"--format=tformat:{fields}",
                *commits,
                "--",
            ],
            location,
            max_bytes=len(commits) * row_bytes,
        )
    except GitOutputTooLargeError:
        return None
    lines = out.decode("utf-8", errors="replace").split("\n")
    return [line.split("\0") for line in lines if line]


def _links(links: GitLocation | None, store: PublishedSource) -> GitLocation | None:
    """*links*, where the session reads Git, or ``None`` when that is *store* itself, as on
    a mirror, where a commit the store holds is one its page reads."""
    if links is None or (links.target is not None and links.target.git_dir == store.git_dir):
        return None
    return links


def _utc_text(epoch: str) -> str | None:
    """*epoch*, Git's `%ct`, as an ISO 8601 UTC time, or ``None`` when it is not a time."""
    try:
        return datetime.fromtimestamp(int(epoch), tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, OverflowError, OSError):
        return None


async def _step_references(carrier: _Carrier, step: CollectionItem) -> list[dict[str, object]]:
    """The step's references, each read from what this copy has cached: a `{path}` from the
    carrier's current comparison, a `{pull, path}` from that pull request's, a `{pull}` from
    its record or catalog row, and a `{commit}` from the store. Nothing is fetched.

    A stale guide's steps are read there too, so a guide stays readable after a push, a
    rebase, or a force push, whether or not the store still has the commits it was written
    for: a reference that still resolves shows what the change is now, and one that does
    not says so in its place.

    Raises ``DiffSourceError`` or ``GitError`` when the store cannot list the carrier's
    comparison for the step's files; a `{pull, path}` whose comparison it cannot list says
    so in its place.
    """
    references = [_carried(ref, carrier.pull) for ref in step.references]
    files = _Files({})
    own = [ref for ref in references if ref.kind == "file"]
    if own:
        files = await _read_files(carrier.store, await carrier.manifest(), carrier.head, own)
    pulls = await _pull_files(carrier, references)
    targets: dict[int, _Target] = {}
    asked = [(at, ref.pull) for at, ref in enumerate(references) if ref.kind == "pull"]
    if asked:
        targets.update(
            await asyncio.to_thread(
                _pull_targets, carrier, [(at, number) for at, number in asked if number]
            )
        )
    store = carrier.store
    location = GitLocation.revision(
        RepositoryStoreTarget(store.git_dir, store.object_format), carrier.head
    )
    cited = {at: ref.commit for at, ref in enumerate(references) if ref.commit is not None}
    if cited:
        commits = await _commit_targets(location, list(cited.values()), carrier.links)
        targets.update({at: commits[commit] for at, commit in cited.items()})
    return await asyncio.to_thread(
        _references, carrier.href, references, files, pulls=pulls, targets=targets
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
            max_bytes=MAX_STALE_COMMITS * _MAX_COMMIT_ROW_BYTES,
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


async def _pinned_past(
    location: GitLocation,
    pinned: CollectionComparison,
    kept: tuple[str, str],
    current: tuple[str, str],
) -> bool:
    """Whether a guide pinned to *pinned* was written for a later comparison than the kept
    pair *kept*, `(merge_base, head)`: the stack's *current* pair, or one whose head comes
    after the kept head. Read at the kept pair, such a guide would look rewritten.

    A head the store lacks, or one that is not after the kept head, is not past it: what
    such a guide's pins say is the staleness read's to report (:func:`_staleness`).
    """
    pins = (pinned.merge_base, pinned.head)
    if pins == kept:
        return False
    if pins == current:
        return True
    if pinned.head == kept[1]:
        return False
    try:
        await run_git_at(["merge-base", "--is-ancestor", kept[1], pinned.head], location)
    except GitCommandError:
        return False
    return True


async def _staleness(
    store: PublishedSource | None,
    current: tuple[str | None, str],
    guide: Collection,
    *,
    newer: bool,
    name: str = GUIDE_FENCE,
    own: int | None = None,
) -> dict[str, object]:
    """What a stale guide was written for, what its comparison is now, and what changed.

    *current* is that comparison's merge base, or ``None`` when the carrier has no
    comparison, and its head: a pull request's, or a stack's pair. *name* is the block's,
    which a refusal names.

    ``changed_paths`` are the guide's referenced paths whose content differs between the
    guide's comparison and the current one, at either end, compared path by path with no
    rename detection, and ``changed_steps`` the one-based steps that cite one; each is
    ``None`` when that cannot be read, as when the store lacks the guide's head after a
    force push. A step that cites no changed path cites no file whose content changed. Its
    excerpts are the current diff's all the same, which can draw a file another way, as
    when the diff now pairs it with a deleted file as a rename. With *newer*, GitHub reports
    a head this copy lacks, for the pull request or for a member of the stack, so what
    changed is unknown: the commits since are this copy's, and neither list is read. *own*
    is the guide's own pull request, whose `{pull, path}` is a `{path}` (:func:`_carried`);
    a stack's guide has none.

    Raises :class:`GuideError` for pins that do not name a comparison: a ``merge_base``
    the store has that is not an ancestor of the guide's ``head``.
    """
    pinned = guide.comparison
    base, head = current
    answer: dict[str, object] = {
        "guide": pinned.model_dump(),
        "current": {"merge_base": base, "head": head},
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
            raise GuideError(f"The {name} block's merge_base is not the merge base of its head.")
        if newer:
            return answer
        changed = (
            await _paths_between(location, pinned.head, head) if pinned.head != head else set()
        )
        if changed is not None and base is not None and pinned.merge_base != base:
            moved = await _paths_between(location, pinned.merge_base, base)
            changed = None if moved is None else changed | moved
    except GitError:
        return answer
    if changed is not None:
        # Only a file of the guide's own comparison can be out of date: a `{pull, path}`
        # follows its pull request, and a pull request or a commit is what it is.
        cited = [_own_paths(item, own) for item in guide.flat_items()]
        answer["changed_paths"] = sorted(set().union(*cited) & changed)
        answer["changed_steps"] = [
            at for at, paths in enumerate(cited, start=1) if not paths.isdisjoint(changed)
        ]
    return answer


def _carried(reference: CollectionReference, own: int | None) -> CollectionReference:
    """*reference* as the guide of pull request *own* reads it: a `{pull, path}` that names
    *own* is a file of the guide's own comparison, its `{path}`, read at the guide's pins
    and marked when a push changes it."""
    if reference.kind == "pull_file" and reference.pull == own:
        return reference.model_copy(update={"pull": None})
    return reference


def _own_paths(item: CollectionItem, own: int | None) -> set[str]:
    """The files of the guide's own comparison that *item* cites, its `{path}` references'
    and those of a `{pull, path}` that names *own*, the guide's own pull request."""
    return {
        ref.path
        for ref in (_carried(ref, own) for ref in item.references)
        if ref.kind == "file" and ref.path is not None
    }


def _head_moved(store: PublishedSource, record: PullRecord) -> bool:
    # Whether the head moved is the catalog row's to say; the status decides nothing of it.
    member = catalog_member(store.home, store.slug, record.number)
    return record_freshness(record, *member, status=None, now=pulls.utc_now()).head_moved


# What a step's answer waits for its notes, measured 2026-11-25 at a load average of 224 to
# 240 on 10 cores, on step 1 of the `markdown` guide in tests/github_pull_fixture.py, its
# note and its group's, two renders, each sample with a fresh child: 17 to 31 ms with the
# child started and idle, as on a served page, which starts it with its first pull read
# (`start_for_pages`); 21 to 124 ms with four 8 KiB texts asked just before it, as a pull
# page asks for its description and comments; 0.37 to 1.30 s behind four 64 KiB texts,
# the record's bound for one; and 0.49 to 1.33 s for a one-shot `--api` call, whose first
# render starts the child. A step read again takes its notes from `_Read.notes` and waits
# for none. The child's deadline and admission limit bound the rest
# (`_MAX_RENDERS` in markdown_projection_worker.py).
async def _rendered_note(
    read: _Read, note: str, number: int, link_base: str
) -> tuple[str | None, NoteRefusal | None]:
    """*note* as inert HTML, rendered as the description is, or ``None`` and why when its
    render is refused or fails: the code the pull-markdown route answers a text's refusal
    with. The page then shows the note as typed, with the line a description's refusal
    says (`textRefusalNote` in pull-page.js).

    The render is the description's own path (`render_text` in pull_text_render.py): KPress
    in its sanitized mode, then the inert allowlist against the pull request's page, in the
    Markdown child under its deadline. A render is kept with *read* while
    :data:`_MAX_KEPT_NOTE_CHARS` holds it, and a refusal is not: the child keeps one that is
    the note's doing, its deadline or a renderer that exited on it, by the note's text, and
    answers it again at once, and one that is not, a busy renderer or one that could not
    start, renders when the step is read again.
    """
    kept = read.notes.get(note)
    if kept is not None:
        return kept, None
    try:
        html = await render_text(note, number=number, part=_NOTE_PART, link_base=link_base)
    except InertRenderRefused as refused:
        return None, refused.code
    except (kpress_adapter.KPressInvalidRequestError, kpress_adapter.KPressRenderError):
        return None, "render_failed"
    if sum(map(len, read.notes.values())) + len(html) <= _MAX_KEPT_NOTE_CHARS:
        read.notes[note] = html
    return html, None


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


async def guided_review(
    host: PullHost,
    number: int,
    step_number: int,
    repository: ListedRepository | None = None,
    links: GitLocation | None = None,
) -> dict[str, object]:
    """Return the first or selected step of this PR's guide and only its excerpts.

    *repository* is the served repository, whose stack snapshot places a `{pull}` reference
    in its stack; without it, a `{pull}` names no place. *links* is where the session reads
    Git, which a `{commit}`'s page reads (:func:`_commit_targets`).
    """
    served = host.pulls
    record, _, revision = await asyncio.to_thread(
        cached_pull_record, served.home, served.slug, number
    )
    identity: dict[str, object] = {"record_revision": revision}
    if not isinstance(record, PullRecord) or revision is None:
        return {**identity, "state": "not_cached"}
    try:
        read = await asyncio.to_thread(
            _kept_read, (str(served.home), served.slug, number), revision, record.pull.body
        )
    except GuideError as exc:
        if record.pull.body_truncated:
            # The record's bound cut the description, so the block it read is not the one
            # on GitHub: the cut is the cause, not the author's block.
            return {**identity, "state": "description_truncated"}
        return {**identity, "state": "invalid", "message": str(exc)}
    guide = read.guide
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
        staleness = (
            await _staleness(
                published,
                (comparison.base if comparison else None, record.pull.head.sha),
                guide,
                newer=newer,
                own=number,
            )
            if stale
            else None
        )
    except GuideError as exc:
        return {**identity, "state": "invalid", "message": str(exc)}
    if published is None or comparison is None:
        # A stale guide's diagnostics ride on every answer, a refusal's too, for an agent
        # that brings the guide up to date.
        stale_part = {} if staleness is None else {"stale": staleness}
        return {**identity, "state": "comparison_unavailable", **stale_part}
    carrier = _Carrier(
        store=published,
        home=served.home,
        slug=served.slug,
        head=comparison.head,
        # The record's own comparison is the pull request's kept manifest (pull_manifest.py),
        # the one Changes reads.
        manifest=partial(shared_pull_manifest, published, number, comparison.base, comparison.head),
        href=partial(format_pull_href, number, "files"),
        repository=repository,
        pull=number,
        links=_links(links, published),
    )
    return await _step_answer(
        identity,
        _Shown(read, guide, staleness, number, record.pull.html_url),
        carrier,
        {"merge_base": comparison.base, "head": comparison.head},
        step_number,
    )


@dataclass(frozen=True, slots=True)
class _Shown:
    """A guide being answered: its kept parse, the guide, what is out of date, and the
    member whose description carries it, whose page its notes' links resolve against."""

    read: _Read
    guide: Collection
    staleness: dict[str, object] | None
    number: int
    link_base: str


async def _step_answer(
    identity: dict[str, object],
    shown: _Shown,
    carrier: _Carrier,
    comparison: dict[str, object],
    step_number: int,
) -> dict[str, object]:
    """One step of *shown*'s guide and only its excerpts, read against *carrier*, whose
    current comparison is *comparison*: a pull request's or a stack's."""
    guide = shown.guide
    staleness = shown.staleness
    # A stale guide's diagnostics ride on every answer, a refusal's too, for an agent that
    # brings the guide up to date; the page says only that the guide may not match.
    diagnostics: dict[str, object] = {} if staleness is None else {"stale": staleness}
    steps = guide.flat_items()
    if step_number > len(steps):
        return {**identity, "state": "step_not_found", **diagnostics}
    step = steps[step_number - 1]
    try:
        references = await _step_references(carrier, step)
    except (DiffSourceError, GitError):
        return {**identity, "state": "comparison_unavailable", **diagnostics}
    outline, groups = _outline(guide)
    group = groups[step_number - 1]
    opened = None if group is None else guide.items[group]
    # A group's note shows above its first step alone, so only that step renders it.
    group_note = (
        opened.note
        if isinstance(opened, CollectionGroup) and groups.index(group) == step_number - 1
        else None
    )
    read, number, link_base = shown.read, shown.number, shown.link_base
    note_html, note_refusal = await _rendered_note(read, step.note, number, link_base)
    group_note_html, group_note_refusal = (
        (None, None)
        if group_note is None
        else await _rendered_note(read, group_note, number, link_base)
    )
    return {
        **identity,
        "state": "ready" if staleness is None else "stale",
        **diagnostics,
        # The comparison the excerpts are read from: a pull request's current one, or the
        # stack's pair the page asked at, else its current one.
        "comparison": comparison,
        "step_count": len(steps),
        # Every step's title, so the page names each step it can move to.
        "titles": [item.title for item in steps],
        # The guide's groups and steps, which the page lists above the step it shows.
        "outline": outline,
        "step": step_number,
        "group": group,
        "title": step.title,
        "note": step.note,
        # The note as inert HTML, rendered as the description is, or null when its render was
        # refused, and the page shows `note` as typed. A title stays plain text.
        "note_html": note_html,
        # Why the note's render was refused, as the pull-markdown route answers a text's
        # `code`, or null: the page says it under the typed note, and keeps no answer whose
        # renderer was busy or could not start, so the step is read again.
        "note_refusal": note_refusal,
        # The note of the group this step opens, rendered so, or null when the step opens no
        # group with a note or its render was refused; the outline has the note as written.
        "group_note_html": group_note_html,
        # Why that render was refused, as `note_refusal` says it.
        "group_note_refusal": group_note_refusal,
        "references": references,
        # The page sets the guide's prose in a KPress article, as it sets a description, and
        # may show this tab before any description has loaded KPress's stylesheets.
        "assets": await asyncio.to_thread(kpress_adapter.document_stylesheets),
    }


async def stack_guided_review(
    repository: ListedRepository | None,
    published: PublishedSource | None,
    reader: str | None,
    stack: int,
    step_number: int,
    links: GitLocation | None = None,
    drawn: tuple[str, str, str] | None = None,
) -> dict[str, object]:
    """Return the first or selected step of native stack *stack*'s guide and only its
    excerpts, in the envelope a pull request's guide has.

    The guide is the `stack-review` block of the top-most member whose description has one
    (:func:`stack_guide_carrier`), and the answer names that member as ``carrier``, its
    page, which the notes' links were made absolute against, as ``carrier_url``, and its
    record's revision as ``record_revision``. Its references are read against a combined
    comparison of the stack, the one its page's Diff summary, Docs, and Changes draw, and its pins
    against that comparison's pair: the bottom member's merge base and the top member's
    head. *drawn* names the comparison the page draws, by its two commits and its key, as
    ``stack-comparison`` takes it: the stack's current pair, or one the stack route gave
    before and keeps (:func:`retained_stack_pair`), so a page reads its guide at the
    comparison it shows until the reader takes the new one. Without *drawn*, the current
    pair. A pair neither names is `stack_moved`, as is a kept pair the guide's pins are past
    (:func:`_pinned_past`), since the member that carries the guide moved and its author
    pinned it again: it was written for a later comparison than the one drawn. Kept pairs
    that cannot be read now are `stack_unavailable` with the reason
    ``snapshot_unavailable``. A stack this copy cannot
    pair is `stack_unavailable`, with the stack route's ``reason``, and one with a member
    not read yet is `not_cached`, since that member may carry the guide. Runs no ``gh`` and
    no fetch.
    """
    from metabrowser.builtin_plugins.github.pull_stack import combined, read_stack
    from metabrowser.builtin_plugins.github.pull_stack_retained import retained_stack_pair

    identity: dict[str, object] = {
        "stack": stack,
        "carrier": None,
        "carrier_url": None,
        "record_revision": None,
    }
    read = await read_stack(repository, published, stack, reader)
    if read.reason is not None:
        return {**identity, "state": "stack_unavailable", "reason": read.reason}
    pair = read.pair
    if pair is None or published is None:
        return {**identity, "state": "not_cached"}
    members = [(member.number, member.record, member.revision) for member in read.members]
    found = await asyncio.to_thread(stack_guide_carrier, published.home, published.slug, members)
    if found is None:
        return {**identity, "state": "absent"}
    number, revision = found
    record = next(member.record for member in read.members if member.number == number)
    assert record is not None
    identity.update(carrier=number, carrier_url=record.pull.html_url, record_revision=revision)
    hit = await asyncio.to_thread(
        _reading, (str(published.home), published.slug, number), revision, record.pull.body
    )
    if hit.stack is None:
        if record.pull.body_truncated:
            return {**identity, "state": "description_truncated"}
        return {**identity, "state": "invalid", "message": hit.stack_message}
    guide = hit.stack
    # GitHub reports a head past a member's record: what changed is this copy's to say. A
    # pair kept from before is read in the store as it was, whatever moved since.
    newer = any(member.moved for member in read.members)
    if drawn is not None and (pair.base, pair.head, pair.digest) != drawn:
        kept = await asyncio.to_thread(retained_stack_pair, published, stack, reader, *drawn)
        if kept == "unknown":
            return {**identity, "state": "stack_unavailable", "reason": "snapshot_unavailable"}
        if kept is None:
            return {**identity, "state": "stack_moved"}
        location = GitLocation.revision(
            RepositoryStoreTarget(published.git_dir, published.object_format), kept.head
        )
        if await _pinned_past(
            location, guide.comparison, (kept.base, kept.head), (pair.base, pair.head)
        ):
            return {**identity, "state": "stack_moved"}
        pair, newer = kept, False
    stale = newer or guide.comparison.head != pair.head or guide.comparison.merge_base != pair.base
    try:
        staleness = (
            await _staleness(
                published, (pair.base, pair.head), guide, newer=newer, name=STACK_FENCE
            )
            if stale
            else None
        )
    except GuideError as exc:
        return {**identity, "state": "invalid", "message": str(exc)}

    async def manifest() -> ResolvedManifest:
        return (await combined(published, pair)).manifest

    carrier = _Carrier(
        store=published,
        home=published.home,
        slug=published.slug,
        head=pair.head,
        manifest=manifest,
        href=partial(format_stack_href, stack, "changes"),
        repository=repository,
        stack=stack,
        links=_links(links, published),
    )
    return await _step_answer(
        identity,
        _Shown(hit, guide, staleness, number, record.pull.html_url),
        carrier,
        {"merge_base": pair.base, "head": pair.head},
        step_number,
    )
