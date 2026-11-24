from __future__ import annotations

import contextlib
import copy
import itertools
import re
import threading
from collections.abc import Iterator
from pathlib import Path
from types import UnionType
from typing import Any, TypeAliasType, Union, cast, get_args, get_origin

import pytest
from pydantic import BaseModel
from pydantic.fields import FieldInfo
from softschema.compile import compile_model

from metabrowser.builtin_plugins.github import guided_review
from metabrowser.builtin_plugins.github.guided_review import (
    CONTRACT_ID,
    MAX_EXCERPT_BYTES,
    MAX_ITEMS,
    MAX_STEP_PATCH_BYTES,
    SCHEMA_PATH,
    Collection,
    CollectionReference,
    GuideError,
    _excerpt,  # pyright: ignore[reportPrivateUsage]
    _hunk_rows,  # pyright: ignore[reportPrivateUsage]
    _outside_shape,  # pyright: ignore[reportPrivateUsage]
    _references,  # pyright: ignore[reportPrivateUsage]
    parse_guide,
    read_guide,
    without_guide,
)
from metabrowser.builtin_plugins.github.pull_record import MAX_BODY_BYTES
from metabrowser.diff.format import (
    Availability,
    ChangeKind,
    ContentRef,
    ContentRefKind,
    EntrySide,
    EntryType,
    FileChange,
    FileMode,
    FilePatch,
    Hunk,
    LineOp,
    LineRecord,
)

_GUIDE = """```guided-review
softschema:
  contract: metabrowser.collection:Collection/v1
  envelope: collection
  status: enforced
collection:
  comparison:
    merge_base: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    head: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  items:
    - title: Read the request first
      note: Does the request wait for the worker?
      references:
        - {path: read.py, side: new, start_line: 2, end_line: 5}
    - title: Follow the worker
      note: Check the publication boundary.
      references:
        - {path: worker.py}
```"""


def test_parses_an_ordered_guide_from_the_description() -> None:
    guide = parse_guide(f"An ordinary PR description.\r\n\r\n{_GUIDE}")
    assert guide is not None
    assert [step.title for step in guide.items] == ["Read the request first", "Follow the worker"]
    assert guide.items[0].references[0].end_line == 5


def test_the_description_without_its_guide_is_the_guides_introduction() -> None:
    body = f"Explain the feature.\r\n\r\n{_GUIDE}\r\n\r\nThen merge it."
    assert without_guide(body) == "Explain the feature.\n\n\nThen merge it."
    assert without_guide(_GUIDE) == ""
    # A block that cannot be read stays, so its author sees what they wrote: two blocks, an
    # unclosed one, invalid YAML, another contract, and a field the contract lacks.
    for kept in (
        f"{_GUIDE}\n\n{_GUIDE}",
        _GUIDE.removesuffix("```"),
        _GUIDE.replace("  items:\n", "  items: [\n"),
        _GUIDE.replace("Collection/v1", "Collection/v9"),
        _GUIDE.replace("start_line: 2", "start_line: 2, extra: 3"),
        "No guide here.",
    ):
        with pytest.raises(GuideError) if "guided-review" in kept else contextlib.nullcontext():
            parse_guide(kept)
        assert without_guide(f"Explain it.\n\n{kept}") == f"Explain it.\n\n{kept}"
    # An example of a block, inside another fence, is the description's own text.
    example = f"````markdown\n{_GUIDE}\n````"
    assert without_guide(example) == example


def test_the_user_guides_example_block_is_a_guide() -> None:
    """The block docs/reviewing-pull-requests.md gives authors to copy reads as a guide once
    its two placeholders are filled (B17 of review B on #677)."""
    guide = Path(__file__).parents[1] / "docs" / "reviewing-pull-requests.md"
    found = re.search(
        r"\n````markdown\n(```guided-review\n.*?\n```)\n````\n", guide.read_text("utf-8"), re.S
    )
    assert found is not None
    example = found[1]
    for placeholder, sha in (
        ("<full merge-base commit ID>", "a" * 40),
        ("<full PR head commit ID>", "b" * 40),
    ):
        assert placeholder in example
        example = example.replace(placeholder, sha)
    parsed = parse_guide(example)
    assert parsed is not None
    assert [step.title for step in parsed.items] == ["Inspect the request path"]


def test_ignores_the_marker_inside_an_example_of_markdown() -> None:
    assert parse_guide(f"````markdown\n{_GUIDE}\n````") is None


def test_packaged_schema_matches_the_model() -> None:
    compiled = compile_model(Collection, SCHEMA_PATH, contract_id=CONTRACT_ID, check_only=True)
    assert not compiled.drift, compiled.drift_diff


@pytest.mark.parametrize(
    "body",
    [
        _GUIDE.removesuffix("```"),
        f"{_GUIDE}\n\n{_GUIDE}",
        _GUIDE.replace("end_line: 5", "end_line: 1"),
        _GUIDE.replace("path: read.py", "path: ../read.py"),
        _GUIDE.replace("start_line: 2", "start_line: true"),
        _GUIDE.replace("start_line: 2", "start_line: 2, extra: 3"),
        # The description introduces the guide; the collection has no prose of its own.
        _GUIDE.replace("  items:\n", "  summary: Explain the feature.\n  items:\n"),
        _GUIDE.replace("status: enforced", "status: soft"),
        _GUIDE.replace("Collection/v1", "Collection/v2"),
    ],
)
def test_rejects_malformed_guide_blocks(body: str) -> None:
    with pytest.raises(GuideError):
        parse_guide(body)


def _guide_of(items: int) -> str:
    one = _GUIDE.split("  items:\n")[0]
    step = "    - title: Step {n}\n      note: Check it.\n      references:\n        - {{path: a.py}}\n"
    return one + "  items:\n" + "".join(step.format(n=n) for n in range(items)) + "```"


def test_a_guide_may_have_at_most_max_items_items() -> None:
    assert parse_guide(_guide_of(MAX_ITEMS)) is not None
    with pytest.raises(GuideError, match=r"does not satisfy the v1 SoftSchema at items\.$"):
        parse_guide(_guide_of(MAX_ITEMS + 1))


@pytest.mark.parametrize(
    ("edit", "where"),
    [
        # softschema's own refusals, at the path its error record lists (D5 of review D).
        (('aaaa"\n    head', 'AAAA"\n    head'), " at comparison.merge_base"),
        (("- title: Read the request first\n      note:", "- note:"), " at items.0"),
        (("start_line: 2", "start_line: 0"), " at items.0.references.0.start_line"),
        # The shape the walk refuses before the schema, at the same place.
        (("start_line: 2", "start_line: 2, extra: 3"), " at items.0.references.0"),
        (("  items:\n", "  summary: Explain the feature.\n  items:\n"), ""),
    ],
)
def test_a_schema_refusal_says_where(edit: tuple[str, str], where: str) -> None:
    body = _GUIDE.replace(*edit)
    assert body != _GUIDE
    with pytest.raises(GuideError) as refused:
        parse_guide(body)
    assert (
        str(refused.value) == f"The guided-review block does not satisfy the v1 SoftSchema{where}."
    )


_SHA = "a" * 40
_HEADER = _GUIDE.split("collection:\n")[0] + "collection:\n"
_ITEM = "{title: t, note: n, references: [{path: a.py}]}"


def _keys() -> Iterator[str]:
    return (f"k{n}: 0, " for n in itertools.count())


def _at_the_bound(collection: str, units: Iterator[str], end: str) -> str:
    """A description of a flow-style *collection* that *units* fill to MAX_BODY_BYTES."""
    parts = [f"{_HEADER}  {collection}"]
    size = len(parts[0]) + len(end) + len("\n```")
    for unit in units:
        if size + len(unit) > MAX_BODY_BYTES:
            break
        parts.append(unit)
        size += len(unit)
    body = "".join(parts) + end + "\n```"
    assert MAX_BODY_BYTES - 32 < len(body.encode()) <= MAX_BODY_BYTES
    return body


_COMPARISON = f"comparison: {{merge_base: {_SHA}, head: {_SHA}}}"


@pytest.mark.parametrize(
    ("body", "where"),
    [
        (_at_the_bound(f"{{{_COMPARISON}, items: [{_ITEM}], ", _keys(), "}"), ""),
        (
            _at_the_bound(
                f"{{comparison: {{merge_base: {_SHA}, head: {_SHA}, ",
                _keys(),
                f"}}, items: [{_ITEM}]}}",
            ),
            " at comparison",
        ),
        (
            _at_the_bound(
                f"{{{_COMPARISON}, items: [{{title: t, note: n, references: [{{path: a.py}}], ",
                _keys(),
                "}]}",
            ),
            " at items.0",
        ),
        (
            _at_the_bound(
                f"{{{_COMPARISON}, items: [{{title: t, note: n, references: [{{path: a.py, ",
                _keys(),
                "}]}]}",
            ),
            " at items.0.references.0",
        ),
        (
            _at_the_bound(f"{{{_COMPARISON}, items: [", itertools.repeat("{}, "), "{}]}"),
            " at items",
        ),
        (_at_the_bound(f"{{{_COMPARISON}, items: [", itertools.repeat("0, "), "0]}"), " at items"),
        (_at_the_bound(f"{{{_COMPARISON}, items: {{", _keys(), "}}"), " at items"),
        (
            _at_the_bound(
                f"{{{_COMPARISON}, items: [{{title: t, note: n, references: [",
                itertools.repeat("{path: a.py}, "),
                "{path: a.py}]}]}",
            ),
            " at items.0.references",
        ),
    ],
    ids=[
        "collection keys",
        "comparison keys",
        "item keys",
        "reference keys",
        "empty items",
        "zero items",
        "items a mapping",
        "references",
    ],
)
def test_a_block_outside_the_schemas_shape_never_reaches_the_schema(
    monkeypatch: pytest.MonkeyPatch, body: str, where: str
) -> None:
    """softschema writes a record for each undeclared key, each with a copy of the whole
    mapping, and checks MAX_ITEMS and MAX_REFERENCES in the same pass, so a description
    at the body bound took about two minutes to refuse (D1 of review D on #677). Each such
    shape is refused before softschema runs, at a place softschema refuses too, the same
    place for a block with one problem."""
    validated: list[object] = []
    real = guided_review.validate_artifact

    def validating(*args: Any, **kwargs: Any) -> Any:
        validated.append(kwargs["document"])
        return real(*args, **kwargs)

    monkeypatch.setattr(guided_review, "validate_artifact", validating)
    with pytest.raises(GuideError) as refused:
        parse_guide(body)
    assert (
        str(refused.value) == f"The guided-review block does not satisfy the v1 SoftSchema{where}."
    )
    assert validated == []
    # A block within the shape still reaches it.
    assert parse_guide(_GUIDE) is not None
    assert len(validated) == 1


def _nested(field: FieldInfo) -> tuple[type[BaseModel], int | None] | None:
    """The model a field holds and, when it holds a list of them, the list's bound."""
    annotation = cast(object, field.annotation)
    while isinstance(annotation, TypeAliasType):
        annotation = annotation.__value__
    if get_origin(annotation) in (Union, UnionType):
        options = [arg for arg in get_args(annotation) if arg is not type(None)]
        annotation = options[0] if len(options) == 1 else None
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation, None
    if get_origin(annotation) is list:
        (inner,) = get_args(annotation)
        if isinstance(inner, type) and issubclass(inner, BaseModel):
            bounds = [getattr(item, "max_length", None) for item in field.metadata]
            bound = next((value for value in bounds if isinstance(value, int)), None)
            assert bound is not None, f"a list of {inner.__name__} declares no max_length"
            return inner, bound
    return None


def _places(
    model: type[BaseModel], at: list[str | int]
) -> Iterator[tuple[list[str | int], type[BaseModel], int | None]]:
    """Each field reachable from *model* that holds a model or a list of models."""
    for name, field in model.model_fields.items():
        nested = _nested(field)
        if nested is not None:
            inner, bound = nested
            yield [*at, name], inner, bound
            yield from _places(inner, [*at, name] if bound is None else [*at, name, 0])


def _skeleton(model: type[BaseModel]) -> dict[str, object]:
    """A mapping of *model* inside the walk's shape: its nested models, and nothing else."""
    document: dict[str, object] = {}
    for name, field in model.model_fields.items():
        nested = _nested(field)
        if nested is not None:
            inner, bound = nested
            document[name] = _skeleton(inner) if bound is None else [_skeleton(inner)]
    return document


def _node(document: object, place: list[str | int]) -> Any:
    node: Any = document
    for part in place:
        node = node[part]
    return node


def test_the_shape_walk_reaches_every_nested_model() -> None:
    """The walk names by hand which fields hold an object or a list of objects. A nested
    model it did not visit would take an undeclared key past it to softschema's quadratic
    refusal (E2 of review E on #677), so each one reachable from Collection is refused at
    its own place: an object for an undeclared key, and a list one past its bound."""
    places = list(_places(Collection, []))
    # The search finds today's three, so it would find a fourth.
    found = [place for place, _, _ in places]
    assert all(known in found for known in (["comparison"], ["items"], ["items", 0, "references"]))
    assert _outside_shape(_skeleton(Collection)) is None
    for place, inner, bound in places:
        objects = [place] if bound is None else [[*place, 0]]
        for at in objects:
            document = copy.deepcopy(_skeleton(Collection))
            _node(document, at)["undeclared"] = 0
            assert _outside_shape(document) == at
        if bound is not None:
            for count, refused in ((bound, None), (bound + 1, place)):
                document = copy.deepcopy(_skeleton(Collection))
                _node(document, place[:-1])[place[-1]] = [_skeleton(inner)] * count
                assert _outside_shape(document) == refused


@pytest.fixture
def parses(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """Each body the guide cache reads, with the cache empty."""
    asked: list[str] = []
    real = guided_review._read_description  # pyright: ignore[reportPrivateUsage]

    def counting(body: str) -> tuple[Collection | None, str]:
        asked.append(body)
        return real(body)

    guided_review._READS.clear()  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(guided_review, "_read_description", counting)
    yield asked
    guided_review._READS.clear()  # pyright: ignore[reportPrivateUsage]


def test_a_guide_is_parsed_once_for_each_record_revision(parses: list[str]) -> None:
    key = ("home", "octo-demo", 7)
    first = read_guide(key, "one", _GUIDE)
    assert first is not None
    assert read_guide(key, "one", _GUIDE) is first
    assert read_guide(key, "one", _GUIDE) is first
    assert len(parses) == 1
    # An edited description is a new revision: parsed again, and the old one is replaced.
    assert read_guide(key, "two", _GUIDE) is not first
    assert len(parses) == 2
    # Another pull request has a guide of its own.
    read_guide(("home", "octo-demo", 8), "one", _GUIDE)
    assert len(parses) == 3


def test_a_refused_guide_is_refused_from_the_cache_too(parses: list[str]) -> None:
    key = ("home", "octo-demo", 7)
    broken = _GUIDE.replace("status: enforced", "status: soft")
    messages = []
    for _ in range(3):
        with pytest.raises(GuideError) as refused:
            read_guide(key, "one", broken)
        messages.append(str(refused.value))
    assert len(parses) == 1
    assert len(set(messages)) == 1 and messages[0]
    # A description without a guide is cached as that.
    assert read_guide(key, "two", "No guide here.") is None
    assert read_guide(key, "two", "No guide here.") is None
    assert len(parses) == 2


def test_two_reads_of_one_revision_share_one_parse(
    parses: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A guided pull request's front page asks for its description's render and its guide's
    first step at once, so the second read waits for the first one's parse rather than
    starting its own (D2 of review D on #677)."""
    key = ("home", "octo-demo", 7)
    parsing = threading.Event()
    finish = threading.Event()
    counting = guided_review._read_description  # pyright: ignore[reportPrivateUsage]

    def slow(body: str) -> tuple[Collection | None, str]:
        parsing.set()
        finish.wait(timeout=30)
        return counting(body)

    monkeypatch.setattr(guided_review, "_read_description", slow)
    answers: list[Collection | None] = []

    def read() -> None:
        answers.append(read_guide(key, "one", _GUIDE))

    readers = [threading.Thread(target=read) for _ in range(2)]
    readers[0].start()
    assert parsing.wait(timeout=30)
    readers[1].start()
    readers[1].join(timeout=0.2)
    assert readers[1].is_alive()
    finish.set()
    for reader in readers:
        reader.join(timeout=30)
    assert len(parses) == 1
    assert len(answers) == 2
    assert answers[0] is not None and answers[0] is answers[1]
    # Another revision parses again, once the first parse is done.
    assert read_guide(key, "two", _GUIDE) is not answers[0]
    assert len(parses) == 2


def test_the_guide_cache_keeps_its_most_recent_pull_requests(
    parses: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(guided_review, "_MAX_READS", 2)
    for number in (1, 2, 3):
        read_guide(("home", "octo-demo", number), "one", _GUIDE)
    assert len(guided_review._READS) == 2  # pyright: ignore[reportPrivateUsage]
    assert ("home", "octo-demo", 1) not in guided_review._READS  # pyright: ignore[reportPrivateUsage]


# old: a b d    new: a B c d    (b replaced by B, c added after it)
_REPLACED = Hunk(
    old_start=1,
    old_count=3,
    new_start=1,
    new_count=4,
    lines=(
        LineRecord(op=LineOp.context, text="a"),
        LineRecord(op=LineOp.delete, text="b"),
        LineRecord(op=LineOp.add, text="B"),
        LineRecord(op=LineOp.add, text="c"),
        LineRecord(op=LineOp.context, text="d"),
    ),
)


def _shown(start: int, end: int, *, old_side: bool) -> list[str]:
    state, rows, _ = _hunk_rows(_REPLACED, start, end, old_side, 10_000)
    assert state == "ready"
    return [f"{row['op']}:{row['text']}" for row in rows]


@pytest.mark.parametrize(
    ("start", "end", "old_side", "shown"),
    [
        # A new range shows the deleted line that sits inside it, or at either end.
        (1, 1, False, ["context:a", "del:b"]),
        (2, 2, False, ["del:b", "add:B"]),
        (2, 3, False, ["del:b", "add:B", "add:c"]),
        (3, 3, False, ["add:c"]),
        (4, 4, False, ["context:d"]),
        (1, 4, False, ["context:a", "del:b", "add:B", "add:c", "context:d"]),
        # An old range shows the added lines that sit inside it, or at either end.
        (1, 1, True, ["context:a"]),
        (2, 2, True, ["del:b", "add:B", "add:c"]),
        (3, 3, True, ["add:B", "add:c", "context:d"]),
        (1, 3, True, ["context:a", "del:b", "add:B", "add:c", "context:d"]),
    ],
)
def test_an_excerpt_shows_a_replacement_whole(
    start: int, end: int, old_side: bool, shown: list[str]
) -> None:
    assert _shown(start, end, old_side=old_side) == shown


def test_a_deleted_line_has_an_old_number_and_no_new_one() -> None:
    _, rows, _ = _hunk_rows(_REPLACED, 2, 2, False, 10_000)
    assert [(row["old"], row["new"], row["op"]) for row in rows] == [
        (2, None, LineOp.delete),
        (None, 2, LineOp.add),
    ]


def test_an_excerpt_past_its_budget_is_refused_not_cut() -> None:
    # Each row costs 80 bytes and 6 for each character of its text.
    cost = 80 + 6
    state, rows, used = _hunk_rows(_REPLACED, 1, 4, False, cost * 5)
    assert (state, len(rows), used) == ("ready", 5, cost * 5)
    assert _hunk_rows(_REPLACED, 1, 4, False, cost * 5 - 1) == ("excerpt_too_large", [], 0)


def _change(
    path: str, number: int, *, availability: Availability = Availability.ready
) -> FileChange:
    side = EntrySide(
        path=path,
        entry_type=EntryType.file,
        mode=FileMode.regular,
        content=ContentRef(kind=ContentRefKind.empty),
    )
    return FileChange(
        id=f"file-{number}",
        kind=ChangeKind.modified,
        old=side,
        new=side,
        binary=False,
        availability=availability,
    )


def _long_row_patch(file_id: str, characters: int) -> FilePatch:
    hunk = Hunk(
        old_start=1,
        old_count=0,
        new_start=1,
        new_count=1,
        lines=(LineRecord(op=LineOp.add, text="x" * characters),),
    )
    return FilePatch(file_id=file_id, hunks=(hunk,), truncated=False)


def _states(
    references: list[CollectionReference],
    changes: dict[str, FileChange],
    patches: dict[str, FilePatch],
    *,
    truncated: bool = False,
) -> list[str]:
    shown = _references(7, references, changes, patches, truncated=truncated)
    return [str(entry["state"]) for entry in shown]


def test_a_step_names_what_became_of_each_reference() -> None:
    new = {"side": "new", "start_line": 1, "end_line": 1}
    references = [
        CollectionReference(path="whole.py"),
        CollectionReference(path="a.py", **new),  # pyright: ignore[reportArgumentType]
        CollectionReference(path="b.py", side="old", start_line=3, end_line=4),
        CollectionReference(path="cut.py", **new),  # pyright: ignore[reportArgumentType]
        CollectionReference(path="gone.py", **new),  # pyright: ignore[reportArgumentType]
    ]
    changes = {
        "whole.py": _change("whole.py", 1),
        "a.py": _change("a.py", 2),
        "b.py": _change("b.py", 3),
        "cut.py": _change("cut.py", 4),
    }
    patches = {
        "file-1": _long_row_patch("file-1", 3),
        "file-2": _long_row_patch("file-2", 3),
        "file-3": _long_row_patch("file-3", 3),
    }
    # cut.py is changed, but its patch was not hydrated; gone.py is not in the comparison.
    assert _states(references, changes, patches) == [
        "ready",
        "ready",
        "range_unavailable",
        "diff_unavailable",
        "path_not_changed",
    ]
    # A manifest cut short says that, not that the path was not changed.
    assert _states(references, changes, patches, truncated=True)[-1] == "manifest_truncated"


def test_a_steps_excerpts_share_one_budget() -> None:
    # One row of this length costs 80 + 6 * 7000 bytes, over half of MAX_EXCERPT_BYTES, so
    # the second excerpt of the step is the one refused, and the first stays whole.
    characters = MAX_EXCERPT_BYTES // 2 // 6 + 1
    new = {"side": "new", "start_line": 1, "end_line": 1}
    references = [
        CollectionReference(path="a.py", **new),  # pyright: ignore[reportArgumentType]
        CollectionReference(path="b.py", **new),  # pyright: ignore[reportArgumentType]
    ]
    changes = {"a.py": _change("a.py", 1), "b.py": _change("b.py", 2)}
    patches = {
        "file-1": _long_row_patch("file-1", characters),
        "file-2": _long_row_patch("file-2", characters),
    }
    assert _states(references, changes, patches) == ["ready", "excerpt_too_large"]
    # One row past the whole budget is refused on its own.
    only = [CollectionReference(path="a.py", **new)]  # pyright: ignore[reportArgumentType]
    big = {"file-1": _long_row_patch("file-1", MAX_EXCERPT_BYTES // 6 + 1)}
    assert _states(only, changes, big) == ["excerpt_too_large"]


def _whole(references: list[CollectionReference], **kwargs: object) -> list[str]:
    changes = {path: _change(path, at) for at, path in enumerate(("a.py", "b.py", "c.py"), 1)}
    return [str(entry["state"]) for entry in _references(7, references, changes, **kwargs)]  # pyright: ignore[reportArgumentType]


def test_a_steps_whole_files_share_one_budget() -> None:
    """A path alone draws its file's whole patch, all of a step's within
    MAX_STEP_PATCH_BYTES; its excerpts have their own budget. A file the diff source left
    out for its size says so, not that its diff is unavailable (B4 and B13 of review B on
    #677)."""
    half = MAX_STEP_PATCH_BYTES // 2 // 6 + 1
    whole = [CollectionReference(path="a.py"), CollectionReference(path="b.py")]
    ranged = CollectionReference(path="c.py", side="new", start_line=1, end_line=1)
    patches = {
        "file-1": _long_row_patch("file-1", half),
        "file-2": _long_row_patch("file-2", half),
        "file-3": _long_row_patch("file-3", 3),
    }
    assert _whole([*whole, ranged], patches=patches, truncated=False) == [
        "ready",
        "patch_too_large",
        "ready",
    ]
    alone = {"file-1": _long_row_patch("file-1", MAX_STEP_PATCH_BYTES // 6)}
    assert _whole(whole[:1], patches=alone, truncated=False) == ["patch_too_large"]
    # No patch: the diff source left it out for its size, or could not read it.
    assert _whole(whole, patches={}, truncated=False, too_large=frozenset({"file-1"})) == [
        "patch_too_large",
        "diff_unavailable",
    ]


def test_a_file_with_no_range_shows_its_whole_patch() -> None:
    """A reference that names a file alone shows every hunk of its patch, as Changes does,
    and says when the diff source cut the patch short."""

    second = Hunk(
        old_start=9,
        old_count=1,
        new_start=10,
        new_count=1,
        lines=(LineRecord(op=LineOp.context, text="z"),),
    )
    patch = FilePatch(file_id="file-1", hunks=(_REPLACED, second), truncated=True)
    shown = _references(
        7,
        [CollectionReference(path="a.py")],
        {"a.py": _change("a.py", 1)},
        {"file-1": patch},
        truncated=False,
    )
    assert shown[0]["state"] == "ready"
    assert shown[0]["truncated"] is True
    hunks = shown[0]["hunks"]
    assert isinstance(hunks, list)
    assert [(hunk["old_start"], hunk["new_start"], len(hunk["lines"])) for hunk in hunks] == [
        (1, 1, 5),
        (9, 10, 1),
    ]


@pytest.mark.parametrize(
    ("start", "end", "old_side", "header"),
    [
        # A range's own lines, numbered from where they are in the file.
        (1, 4, False, (1, 3, 1, 4)),
        (2, 2, False, (2, 1, 2, 1)),
        # Added lines alone start their old side at the line before them, as git does.
        (3, 3, False, (2, 0, 3, 1)),
        # A deleted line alone does the same on its new side.
        (2, 2, True, (2, 1, 2, 2)),
    ],
)
def test_a_range_is_one_hunk_numbered_as_in_the_file(
    start: int, end: int, old_side: bool, header: tuple[int, int, int, int]
) -> None:
    reference = CollectionReference(
        path="a.py", side="old" if old_side else "new", start_line=start, end_line=end
    )
    patch = FilePatch(file_id="file-1", hunks=(_REPLACED,), truncated=False)
    state, hunks, _ = _excerpt(patch, reference, 10_000)
    assert state == "ready"
    (hunk,) = hunks
    assert (hunk["old_start"], hunk["old_count"], hunk["new_start"], hunk["new_count"]) == header
    # Its lines are the diff model's own records, as a whole file's hunks are.
    lines = hunk["lines"]
    assert isinstance(lines, list)
    assert all(
        isinstance(line, dict) and set(line) == {"op", "text", "text_b64", "no_newline"}
        for line in lines
    )


@pytest.mark.parametrize(("start", "end", "header"), [(1, 2, (0, 0, 1, 2)), (2, 3, (0, 0, 2, 2))])
def test_a_range_of_an_added_file_starts_its_old_side_at_zero(
    start: int, end: int, header: tuple[int, int, int, int]
) -> None:
    """An added file's hunk is `@@ -0,0 +1,3 @@`: its old start is already the line before."""
    added = Hunk(
        old_start=0,
        old_count=0,
        new_start=1,
        new_count=3,
        lines=tuple(LineRecord(op=LineOp.add, text=text) for text in "xyz"),
    )
    reference = CollectionReference(path="new.py", side="new", start_line=start, end_line=end)
    patch = FilePatch(file_id="file-1", hunks=(added,), truncated=False)
    state, hunks, _ = _excerpt(patch, reference, 10_000)
    assert state == "ready"
    (hunk,) = hunks
    assert (hunk["old_start"], hunk["old_count"], hunk["new_start"], hunk["new_count"]) == header
