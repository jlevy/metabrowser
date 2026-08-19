"""Pydantic implementation of File Diff Format v1.

The checked-in JSON Schema is the authority; these models implement it,
and the conformance corpus (run from ``tests/test_file_diff_format.py``)
is what keeps this implementation and the browser one in agreement.
Field meanings live in ``docs/project/architecture/file-diff-format/``.

Follows the ``plugin_loader/manifest.py`` idiom: ``BaseModel`` with
``extra="forbid"``, and structural rules that the schema states as
``allOf`` conditionals become model validators here.
"""

from __future__ import annotations

import json
from enum import StrEnum
from functools import cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

FILE_DIFF_SCHEMA = "file-diff-v1"
FILE_DIFF_SCHEMA_VERSION = 1

_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "file-diff-format"


class ChangeKind(StrEnum):
    """Git status letters A D M R C T U, spelled out."""

    added = "added"
    deleted = "deleted"
    modified = "modified"
    renamed = "renamed"
    copied = "copied"
    type_changed = "type_changed"
    unmerged = "unmerged"


class EntryType(StrEnum):
    file = "file"
    symlink = "symlink"
    submodule = "submodule"


class FileMode(StrEnum):
    """Git file modes; the strings are git's octal spellings."""

    regular = "100644"
    executable = "100755"
    symlink = "120000"
    gitlink = "160000"


class Availability(StrEnum):
    """Declared gaps in applicability, never an ambiguous empty body."""

    ready = "ready"
    deferred = "deferred"
    binary = "binary"
    too_large = "too_large"
    timed_out = "timed_out"
    failed = "failed"
    stale = "stale"
    unsupported = "unsupported"


class SnapshotKind(StrEnum):
    commit = "commit"
    tree = "tree"
    # `index_` because a StrEnum member named `index` shadows str.index;
    # the wire value is still "index".
    index_ = "index"
    worktree = "worktree"
    patch = "patch"
    empty = "empty"


class BasePolicy(StrEnum):
    direct = "direct"
    merge_base = "merge_base"
    first_parent = "first_parent"


class LineOp(StrEnum):
    context = "context"
    add = "add"
    delete = "del"


class ContentRefKind(StrEnum):
    git_object = "git_object"
    inline = "inline"
    empty = "empty"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ContentRef(_Model):
    kind: ContentRefKind
    oid: str | None = Field(default=None, pattern=r"^[0-9a-f]{40,64}$")
    inline_b64: str | None = None
    generation: str | None = None

    @model_validator(mode="after")
    def _kind_requirements(self) -> ContentRef:
        if self.kind is ContentRefKind.git_object and self.oid is None:
            raise ValueError("git_object content requires an oid")
        if self.kind is ContentRefKind.inline and self.inline_b64 is None:
            raise ValueError("inline content requires inline_b64")
        return self


class EntrySide(_Model):
    path: str
    path_b64: str | None = None
    entry_type: EntryType
    mode: FileMode
    content: ContentRef
    size: int | None = Field(default=None, ge=0)


class FileChange(_Model):
    id: str = Field(min_length=1)
    kind: ChangeKind
    old: EntrySide | None = None
    new: EntrySide | None = None
    similarity: int | None = Field(default=None, ge=0, le=100)
    binary: bool
    availability: Availability
    additions: int | None = Field(default=None, ge=0)
    deletions: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _sides_for_kind(self) -> FileChange:
        kind = self.kind
        if kind is ChangeKind.added and (self.old is not None or self.new is None):
            raise ValueError("added requires new and forbids old")
        if kind is ChangeKind.deleted and (self.new is not None or self.old is None):
            raise ValueError("deleted requires old and forbids new")
        if kind in (ChangeKind.modified, ChangeKind.type_changed, ChangeKind.unmerged) and (
            self.old is None or self.new is None
        ):
            raise ValueError(f"{kind.value} requires both sides")
        if kind in (ChangeKind.renamed, ChangeKind.copied) and (
            self.old is None or self.new is None or self.similarity is None
        ):
            raise ValueError(f"{kind.value} requires both sides and a similarity score")
        return self


class Totals(_Model):
    files: int = Field(ge=0)
    additions: int | None = Field(ge=0)
    deletions: int | None = Field(ge=0)
    exact: bool


class ChangeSetManifest(_Model):
    files: tuple[FileChange, ...]
    totals: Totals
    truncated: bool
    cursor: str | None = None

    @model_validator(mode="after")
    def _cursor_iff_truncated(self) -> ChangeSetManifest:
        if (self.cursor is not None) != self.truncated:
            raise ValueError("cursor must be non-null exactly when truncated is true")
        return self


class LineRecord(_Model):
    op: LineOp
    text: str
    text_b64: str | None = None
    no_newline: bool = False


class Hunk(_Model):
    old_start: int = Field(ge=0)
    old_count: int = Field(ge=0)
    new_start: int = Field(ge=0)
    new_count: int = Field(ge=0)
    heading: str | None = None
    lines: tuple[LineRecord, ...]

    @model_validator(mode="after")
    def _counts_match_lines(self) -> Hunk:
        old = sum(1 for line in self.lines if line.op is not LineOp.add)
        new = sum(1 for line in self.lines if line.op is not LineOp.delete)
        if old != self.old_count or new != self.new_count:
            raise ValueError(
                f"hunk counts disagree with lines: header says -{self.old_count}/+{self.new_count},"
                f" lines say -{old}/+{new}"
            )
        return self


class FilePatch(_Model):
    file_id: str = Field(min_length=1)
    hunks: tuple[Hunk, ...]
    truncated: bool


class SourceInfo(_Model):
    name: str = Field(min_length=1)
    version: str | None = None


class SnapshotRef(_Model):
    kind: SnapshotKind
    id: str | None = None
    symbolic: str | None = None
    generation: str | None = None


class DiffOptions(_Model):
    context: int = Field(ge=0)
    rename_detection: bool
    rename_similarity: int | None = Field(default=None, ge=0, le=100)
    algorithm: str | None = None


class ResolvedComparison(_Model):
    comparison_id: str = Field(min_length=1)
    source: SourceInfo
    kind: str = Field(pattern=r"^content$")
    base_policy: BasePolicy
    left: SnapshotRef
    right: SnapshotRef
    options: DiffOptions
    warnings: tuple[str, ...] = ()


class ChangeSetDocument(_Model):
    schema_: str = Field(alias="schema", pattern=r"^file-diff-v1$")
    schema_version: int
    resolved: ResolvedComparison
    manifest: ChangeSetManifest
    patches: dict[str, FilePatch]

    @model_validator(mode="after")
    def _document_invariants(self) -> ChangeSetDocument:
        if self.schema_version != FILE_DIFF_SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version {self.schema_version}")
        known = {change.id for change in self.manifest.files}
        for file_id, patch in self.patches.items():
            if file_id != patch.file_id:
                raise ValueError(f"patch keyed {file_id!r} carries file_id {patch.file_id!r}")
            if file_id not in known:
                raise ValueError(f"patch {file_id!r} has no manifest entry")
        return self


@cache
def load_schema() -> dict[str, Any]:
    """The checked-in JSON Schema, the format's authority."""
    raw = (_DATA_DIR / "file-diff.schema.json").read_text(encoding="utf-8")
    return json.loads(raw)


@cache
def load_conformance_corpus() -> dict[str, Any]:
    raw = (_DATA_DIR / "file-diff-conformance.json").read_text(encoding="utf-8")
    return json.loads(raw)


def validate_document(document: dict[str, Any]) -> ChangeSetDocument:
    """Corpus entry point: parse-or-raise for one document."""
    return ChangeSetDocument.model_validate(document)


def dump_document(document: ChangeSetDocument) -> dict[str, Any]:
    """The wire projection: plain data, by alias, without None noise.

    ``exclude_none`` drops optional-and-absent fields, which is right for
    ``similarity`` or ``path_b64`` — but the format makes line totals
    *required and nullable* (null means "not computed", a different fact
    from absent), so those keys are restored explicitly.
    """
    dumped = document.model_dump(mode="json", by_alias=True, exclude_none=True)
    totals = dumped["manifest"]["totals"]
    totals.setdefault("additions", None)
    totals.setdefault("deletions", None)
    for change in dumped["manifest"]["files"]:
        change.setdefault("additions", None)
        change.setdefault("deletions", None)
    return dumped
