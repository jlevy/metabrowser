from __future__ import annotations

import contextlib
import copy
import itertools
import json
import re
import threading
from collections.abc import Iterator
from pathlib import Path
from types import UnionType
from typing import Annotated, Any, TypeAliasType, Union, cast, get_args, get_origin

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
    CollectionComparison,
    CollectionGroup,
    CollectionItem,
    CollectionReference,
    GuideError,
    _excerpt,  # pyright: ignore[reportPrivateUsage]
    _Files,  # pyright: ignore[reportPrivateUsage]
    _hunk_rows,  # pyright: ignore[reportPrivateUsage]
    _outline,  # pyright: ignore[reportPrivateUsage]
    _outside_shape,  # pyright: ignore[reportPrivateUsage]
    _references,  # pyright: ignore[reportPrivateUsage]
    _schema_refusal,  # pyright: ignore[reportPrivateUsage]
    parse_guide,
    parse_stack_guide,
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
    steps = guide.flat_items()
    assert [step.title for step in steps] == ["Read the request first", "Follow the worker"]
    assert steps[0].references[0].end_line == 5


# A block that cannot be read: YAML that does not parse, and a block outside the format.
_BROKEN = {"guided-review": "not: [yaml\n", "stack-review": "x: 1\n"}


@pytest.mark.parametrize("stack_first", [False, True], ids=["guide first", "stack first"])
@pytest.mark.parametrize(
    "broken", [None, "guided-review", "stack-review"], ids=["both read", "guide", "stack"]
)
def test_a_broken_block_of_one_kind_never_hides_the_other(
    broken: str | None, stack_first: bool
) -> None:
    """A description can carry its pull request's guide and a stack's, each read on its own:
    a block of one kind that cannot be read refuses that kind alone, in either order, and
    stays in the introduction, from which a block that reads is taken out (A9 of review A
    on #838)."""

    def block(name: str) -> str:
        body = _GUIDE.removeprefix("```guided-review\n").removesuffix("```")
        return f"```{name}\n{_BROKEN[name] if name == broken else body}```"

    kinds = ["stack-review", "guided-review"] if stack_first else ["guided-review", "stack-review"]
    body = f"Intro.\n\n{block(kinds[0])}\n\nMiddle.\n\n{block(kinds[1])}\n\nTail.\n"
    for name, parse in (("guided-review", parse_guide), ("stack-review", parse_stack_guide)):
        if name == broken:
            with pytest.raises(GuideError):
                parse(body)
        else:
            read = parse(body)
            assert read is not None and len(read.flat_items()) == 2, name
    introduction = without_guide(body)
    for name in kinds:
        assert (f"```{name}" in introduction) == (name == broken), name
    assert [part for part in ("Intro.", "Middle.", "Tail.") if part in introduction] == [
        "Intro.",
        "Middle.",
        "Tail.",
    ]


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


PUBLISHED_GUIDE = (
    Path(__file__).parent / "fixtures" / "guided-review" / "published-without-groups.txt"
)


def test_a_published_guide_without_groups_reads_as_it_was_written() -> None:
    """A guide published before groups existed, four of the steps #785's description posted,
    kept byte for byte, reads as it did: every entry is a step, in its order, with its notes
    and references, so a guide without groups needs no change."""
    parsed = parse_guide(PUBLISHED_GUIDE.read_text("utf-8"))
    assert parsed is not None
    assert all(type(entry) is CollectionItem for entry in parsed.items)
    steps = parsed.flat_items()
    assert steps == parsed.items
    assert [step.title for step in steps] == [
        "Keystone: the check before publishing is a route",
        "Keystone: a guide is the reviewer's agenda, one step or run per concern",
        "Document: the skill's new section",
        "Change: the changelog fragment and the plans index",
    ]
    assert [len(step.references) for step in steps] == [2, 3, 1, 2]
    assert steps[0].note.startswith("Decided: the draft check is a GitHub plugin route,")


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


# What a guide past MAX_ITEMS is told, in its own words: the schema admits a block whose
# lists are each within their bounds, so a refusal in its name would not say what is wrong.
TOO_MANY = f"This guide has more than {MAX_ITEMS} steps and groups."


def test_a_guide_may_have_at_most_max_items_items() -> None:
    assert parse_guide(_guide_of(MAX_ITEMS)) is not None
    with pytest.raises(GuideError) as refused:
        parse_guide(_guide_of(MAX_ITEMS + 1))
    assert str(refused.value) == TOO_MANY


_STEP = "{{title: Step {n}, note: Check it., references: [{{path: a.py}}]}}"


def _entries_of(*entries: str) -> str:
    """A guide whose items are *entries*, each one YAML entry of the list."""
    one = _GUIDE.split("  items:\n")[0]
    return one + "  items:\n" + "".join(f"    - {entry}\n" for entry in entries) + "```"


def _group(title: str, steps: range, note: str | None = None) -> str:
    """A group of the steps numbered by *steps*, as one flow-style entry."""
    said = "" if note is None else f", note: {note}"
    items = ", ".join(_STEP.format(n=n) for n in steps)
    return f"{{title: {title}{said}, items: [{items}]}}"


def test_a_guide_groups_its_steps_one_level_deep() -> None:
    """Groups and steps mix in any order, a group's note is optional, and the steps are
    read in order through the groups: a guide's steps 1 to n."""
    guide = parse_guide(
        _entries_of(
            _group("Decisions", range(1, 3), note="Read these first."),
            _STEP.format(n=3),
            _group("Testing", range(4, 5)),
        )
    )
    assert guide is not None
    assert [type(entry) for entry in guide.items] == [
        CollectionGroup,
        CollectionItem,
        CollectionGroup,
    ]
    first, _, last = guide.items
    assert isinstance(first, CollectionGroup) and isinstance(last, CollectionGroup)
    assert (first.title, first.note, last.note) == ("Decisions", "Read these first.", None)
    assert [step.title for step in guide.flat_items()] == [f"Step {n}" for n in range(1, 5)]
    # A guide without groups is a guide of steps, as before.
    plain = parse_guide(_GUIDE)
    assert plain is not None and plain.flat_items() == plain.items


def test_the_outline_numbers_steps_through_groups_not_by_entry() -> None:
    """A group of two steps after another group of two, with a step between: the outline
    numbers the steps 1 to 5 through the groups, as ``step=<k>`` reads them, where numbering
    by entry would give each group's steps one number (A3 of review A on #807). Each step's
    group is its group's index in the outline."""
    guide = parse_guide(
        _entries_of(_group("A", range(1, 3)), _STEP.format(n=3), _group("B", range(4, 6)))
    )
    assert guide is not None
    outline, groups = _outline(guide)
    numbered = [
        [
            (child["step"], child["title"])
            for child in cast(list[dict[str, object]], node["children"])
        ]
        if node["kind"] == "group"
        else (node["step"], node["title"])
        for node in outline
    ]
    assert numbered == [
        [(1, "Step 1"), (2, "Step 2")],
        (3, "Step 3"),
        [(4, "Step 4"), (5, "Step 5")],
    ]
    assert groups == [0, 0, None, 2, 2]


def test_max_items_counts_each_group_and_its_steps() -> None:
    """MAX_ITEMS bounds every entry, a group and each of its steps alike, since the parse
    costs by the entry. No one list states the total, so the walk refuses it before the
    schema runs, saying what is wrong; a group's own list past its bound is past the total
    too."""
    full = MAX_ITEMS - 1
    whole = parse_guide(_entries_of(_group("All", range(full))))
    assert whole is not None and len(whole.flat_items()) == full
    half = MAX_ITEMS // 2
    steps = [_STEP.format(n=n) for n in range(half)]
    mixed = parse_guide(_entries_of(_group("Some", range(half - 1)), *steps))
    assert mixed is not None and len(mixed.flat_items()) == MAX_ITEMS - 1
    for body in (
        _entries_of(_group("All", range(full + 1))),
        _entries_of(_group("Some", range(half - 1)), *steps, _STEP.format(n=0)),
        _entries_of(*steps, _group("Some", range(half))),
    ):
        with pytest.raises(GuideError) as refused:
            parse_guide(body)
        assert str(refused.value) == TOO_MANY
    # The models state the total too, for a collection made in code.
    item = CollectionItem(title="t", note="n", references=[CollectionReference(path="a.py")])
    with pytest.raises(ValueError, match="at most 40 items and groups"):
        Collection(
            comparison=CollectionComparison(merge_base="a" * 40, head="b" * 40),
            items=[CollectionGroup(title="g", items=[item] * full), item],
        )


@pytest.mark.parametrize(
    ("entry", "refusal"),
    [
        # An empty group is refused, as an empty guide is.
        ("{title: Empty, items: []}", "does not satisfy the v1 SoftSchema at items.0.items"),
        # A group holds steps only: groups nest one level.
        (
            f"{{title: Outer, items: [{_group('Inner', range(1))}]}}",
            "does not satisfy the v1 SoftSchema at items.0.items.0",
        ),
        # A group has items and no references, and a step references and no items.
        (
            "{title: Both, items: [], references: [{path: a.py}]}",
            "does not satisfy the v1 SoftSchema at items.0",
        ),
        ("{title: Neither, note: n}", "does not satisfy the v1 SoftSchema at items.0"),
        (
            f"{{title: Extra, extra: 1, items: [{_STEP.format(n=1)}]}}",
            "does not satisfy the v1 SoftSchema at items.0",
        ),
        # A refusal inside a group's step is at its own place, as a step's outside one is.
        (
            "{title: G, items: [{title: t, note: n, references: "
            "[{path: a.py, side: new, start_line: 0, end_line: 1}]}]}",
            "does not satisfy the v1 SoftSchema at items.0.items.0.references.0.start_line",
        ),
        (
            "{title: G, items: [{title: t, note: n, references: [{path: ../a.py}]}]}",
            "Invalid guided-review reference at items.0.items.0.references.0",
        ),
    ],
    ids=["empty", "nested", "both", "neither", "undeclared", "range", "path"],
)
def test_a_group_is_refused_at_its_place(entry: str, refusal: str) -> None:
    with pytest.raises(GuideError) as refused:
        parse_guide(_entries_of(entry))
    assert str(refused.value).endswith(f"{refusal}.")


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


def _cite(reference: str) -> str:
    """The guide with its second step citing *reference* alone."""
    return _GUIDE.replace("{path: worker.py}", reference)


@pytest.mark.parametrize(
    ("reference", "kind"),
    [
        ("{path: worker.py}", "file"),
        ("{path: worker.py, side: old, start_line: 1, end_line: 1}", "file"),
        ("{pull: 805}", "pull"),
        ("{pull: 805, path: docs/plan.md}", "pull_file"),
        ('{commit: "' + "c" * 40 + '"}', "commit"),
        ('{commit: "' + "c" * 64 + '"}', "commit"),
        # A null field is absent, in the schema as in the model.
        ("{path: worker.py, commit: null}", "file"),
        (
            "{path: worker.py, side: new, start_line: 1, end_line: 2, pull: null, commit: null}",
            "file",
        ),
        ("{path: worker.py, side: new, start_line: 1, end_line: 2, pull: null}", "file"),
        ("{pull: 805, path: null, side: null, start_line: null, end_line: null}", "pull"),
        ('{commit: "' + "c" * 40 + '", path: null, pull: null, side: null}', "commit"),
    ],
)
def test_a_reference_is_of_the_kind_its_fields_name(reference: str, kind: str) -> None:
    guide = parse_guide(_cite(reference))
    assert guide is not None
    step = guide.items[1]
    assert isinstance(step, CollectionItem)
    assert step.references[0].kind == kind


@pytest.mark.parametrize(
    "reference",
    [
        "{path: worker.py}",
        "{path: worker.py, side: new, start_line: 1, end_line: 2}",
        "{pull: 805}",
        "{pull: 805, path: docs/plan.md}",
        '{commit: "' + "c" * 40 + '"}',
    ],
)
def test_a_reference_the_route_answers_parses_back_as_the_same_reference(reference: str) -> None:
    """The route answers a reference's every field, null where its kind has none
    (`**reference.model_dump()` in `_references`), so an author or agent may copy a
    cited reference back from an answer into a guide."""

    def cited(body: str) -> CollectionReference:
        guide = parse_guide(_cite(body))
        assert guide is not None
        step = guide.items[1]
        assert isinstance(step, CollectionItem)
        return step.references[0]

    first = cited(reference)
    answered = json.dumps(first.model_dump())
    assert "null" in answered
    assert cited(answered) == first


@pytest.mark.parametrize(
    ("reference", "where"),
    [
        # A range moves with the file it is in, and another pull request's file is not
        # pinned by this guide, so it takes none.
        ("{pull: 805, path: docs/plan.md, side: new, start_line: 1, end_line: 2}", "end_line"),
        ("{pull: 805, side: new}", "side"),
        # A commit is cited alone.
        ('{commit: "' + "c" * 40 + '", path: worker.py}', "path"),
        ('{commit: "' + "c" * 40 + '", pull: 805}', "pull"),
        ('{commit: "' + "c" * 40 + '", start_line: 1}', "start_line"),
        # A commit by its full SHA, and a pull request by its number.
        ('{commit: "ccccccc"}', "commit"),
        ("{pull: 0}", "pull"),
        ('{pull: "805"}', "pull"),
        # A reference names a file, a pull request, or a commit.
        ("{side: new, start_line: 1, end_line: 1}", None),
        ("{}", None),
    ],
)
def test_a_reference_of_no_kind_is_refused_where_it_goes_wrong(
    reference: str, where: str | None
) -> None:
    with pytest.raises(GuideError) as refused:
        parse_guide(_cite(reference))
    place = "items.1.references.0" + (f".{where}" if where else "")
    assert str(refused.value) == (
        f"The guided-review block does not satisfy the v1 SoftSchema at {place}."
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


def _schema_said(where: str) -> str:
    """The schema's refusal of a block, at *where* when it is one."""
    return f"The guided-review block does not satisfy the v1 SoftSchema{where}."


@pytest.mark.parametrize(
    ("body", "refusal"),
    [
        (_at_the_bound(f"{{{_COMPARISON}, items: [{_ITEM}], ", _keys(), "}"), _schema_said("")),
        (
            _at_the_bound(
                f"{{comparison: {{merge_base: {_SHA}, head: {_SHA}, ",
                _keys(),
                f"}}, items: [{_ITEM}]}}",
            ),
            _schema_said(" at comparison"),
        ),
        (
            _at_the_bound(
                f"{{{_COMPARISON}, items: [{{title: t, note: n, references: [{{path: a.py}}], ",
                _keys(),
                "}]}",
            ),
            _schema_said(" at items.0"),
        ),
        (
            _at_the_bound(
                f"{{{_COMPARISON}, items: [{{title: t, note: n, references: [{{path: a.py, ",
                _keys(),
                "}]}]}",
            ),
            _schema_said(" at items.0.references.0"),
        ),
        (
            _at_the_bound(f"{{{_COMPARISON}, items: [", itertools.repeat("{}, "), "{}]}"),
            TOO_MANY,
        ),
        (_at_the_bound(f"{{{_COMPARISON}, items: [", itertools.repeat("0, "), "0]}"), TOO_MANY),
        (_at_the_bound(f"{{{_COMPARISON}, items: {{", _keys(), "}}"), _schema_said(" at items")),
        (
            _at_the_bound(
                f"{{{_COMPARISON}, items: [{{title: t, note: n, references: [",
                itertools.repeat("{path: a.py}, "),
                "{path: a.py}]}]}",
            ),
            _schema_said(" at items.0.references"),
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
    monkeypatch: pytest.MonkeyPatch, body: str, refusal: str
) -> None:
    """softschema writes a record for each undeclared key, each with a copy of the whole
    mapping, and checks MAX_ITEMS and MAX_REFERENCES in the same pass, so a description
    at the body bound took about two minutes to refuse (D1 of review D on #677). Each such
    shape is refused before softschema runs, at a place softschema refuses too, the same
    place for a block with one problem, and a list of more entries than MAX_ITEMS in words
    of its own."""
    validated: list[object] = []
    real = guided_review.validate_artifact

    def validating(*args: Any, **kwargs: Any) -> Any:
        validated.append(kwargs["document"])
        return real(*args, **kwargs)

    monkeypatch.setattr(guided_review, "validate_artifact", validating)
    with pytest.raises(GuideError) as refused:
        parse_guide(body)
    assert str(refused.value) == refusal
    assert validated == []
    # A block within the shape still reaches it.
    assert parse_guide(_GUIDE) is not None
    assert len(validated) == 1


def _models(annotation: object) -> tuple[type[BaseModel], ...]:
    """The models *annotation* holds: a model, or each model of a union, through type
    aliases, `Annotated`, and `None`."""
    while isinstance(annotation, TypeAliasType) or get_origin(annotation) is Annotated:
        annotation = (
            annotation.__value__
            if isinstance(annotation, TypeAliasType)
            else get_args(annotation)[0]
        )
    if get_origin(annotation) in (Union, UnionType):
        return tuple(model for option in get_args(annotation) for model in _models(option))
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return (annotation,)
    return ()


def _nested(field: FieldInfo) -> tuple[tuple[type[BaseModel], ...], int | None] | None:
    """The models a field holds and, when it holds a list of them, the list's bound."""
    annotation = cast(object, field.annotation)
    models = _models(annotation)
    if models:
        assert len(models) == 1, "an object field holds one model"
        return models, None
    if get_origin(annotation) is list:
        (inner,) = get_args(annotation)
        models = _models(inner)
        if models:
            bounds = [getattr(item, "max_length", None) for item in field.metadata]
            bound = next((value for value in bounds if isinstance(value, int)), None)
            assert bound is not None, f"a list of {models[0].__name__} declares no max_length"
            return models, bound
    return None


def _places(
    model: type[BaseModel], at: list[str | int]
) -> Iterator[tuple[list[str | int], int | None, type[BaseModel], int | None]]:
    """Each field reachable from *model* that holds a model or a list of models: its place,
    the index in the list of :func:`_skeleton` that holds each model of the list, the
    model, and the list's bound."""
    for name, field in model.model_fields.items():
        nested = _nested(field)
        if nested is not None:
            models, bound = nested
            for index, inner in enumerate(models):
                yield [*at, name], None if bound is None else index, inner, bound
                yield from _places(inner, [*at, name] if bound is None else [*at, name, index])


def _skeleton(model: type[BaseModel]) -> dict[str, object]:
    """A mapping of *model* inside the walk's shape: its nested models, and nothing else. A
    list holds one of each model it may."""
    document: dict[str, object] = {}
    for name, field in model.model_fields.items():
        nested = _nested(field)
        if nested is not None:
            models, bound = nested
            document[name] = (
                _skeleton(models[0]) if bound is None else [_skeleton(inner) for inner in models]
            )
    return document


def _node(document: object, place: list[str | int]) -> Any:
    node: Any = document
    for part in place:
        node = node[part]
    return node


def _entries(document: dict[str, Any]) -> int:
    """What MAX_ITEMS counts in *document*: its entries, and the items of a group among them."""
    entries = document["items"]
    return len(entries) + sum(len(entry["items"]) for entry in entries if "items" in entry)


def test_the_shape_walk_reaches_every_nested_model() -> None:
    """The walk names by hand which fields hold an object or a list of objects. A nested
    model it did not visit would take an undeclared key past it to softschema's quadratic
    refusal (E2 of review E on #677), so each one reachable from Collection is refused at
    its own place: an object for an undeclared key, and a list one past its bound. A list
    at its bound is within the shape unless MAX_ITEMS, which counts a group's items with
    the entries, refuses it in words of its own."""
    places = list(_places(Collection, []))
    # The search finds today's six, so it would find a seventh.
    found = [(place, inner) for place, _, inner, _ in places]
    assert found == [
        (["comparison"], CollectionComparison),
        (["items"], CollectionItem),
        (["items", 0, "references"], CollectionReference),
        (["items"], CollectionGroup),
        (["items", 1, "items"], CollectionItem),
        (["items", 1, "items", 0, "references"], CollectionReference),
    ]
    assert _outside_shape(_skeleton(Collection)) is None
    for place, index, inner, bound in places:
        at = place if index is None else [*place, index]
        document = copy.deepcopy(_skeleton(Collection))
        _node(document, at)["undeclared"] = 0
        assert _outside_shape(document) == _schema_refusal(at)
        if bound is not None:
            for count in (bound, bound + 1):
                document = copy.deepcopy(_skeleton(Collection))
                _node(document, place[:-1])[place[-1]] = [_skeleton(inner)] * count
                if _entries(document) > MAX_ITEMS:
                    assert _outside_shape(document) == TOO_MANY
                else:
                    past = count > bound
                    assert _outside_shape(document) == (_schema_refusal(place) if past else None)


@pytest.fixture
def parses(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """Each body the guide cache reads, with the cache empty."""
    asked: list[str] = []
    real = guided_review._read_description  # pyright: ignore[reportPrivateUsage]

    def counting(body: str) -> guided_review._Description:  # pyright: ignore[reportPrivateUsage]
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

    def slow(body: str) -> guided_review._Description:  # pyright: ignore[reportPrivateUsage]
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


def _files_of(path: str) -> str:
    return f"/pull/7/files/{path}"


def _states(
    references: list[CollectionReference],
    changes: dict[str, FileChange],
    patches: dict[str, FilePatch],
    *,
    truncated: bool = False,
) -> list[str]:
    shown = _references(_files_of, references, _Files(changes, patches, truncated))
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


def _whole(
    references: list[CollectionReference],
    *,
    patches: dict[str, FilePatch],
    too_large: frozenset[str] = frozenset(),
) -> list[str]:
    changes = {path: _change(path, at) for at, path in enumerate(("a.py", "b.py", "c.py"), 1)}
    files = _Files(changes, patches, too_large=too_large)
    return [str(entry["state"]) for entry in _references(_files_of, references, files)]


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
    assert _whole([*whole, ranged], patches=patches) == [
        "ready",
        "patch_too_large",
        "ready",
    ]
    alone = {"file-1": _long_row_patch("file-1", MAX_STEP_PATCH_BYTES // 6)}
    assert _whole(whole[:1], patches=alone) == ["patch_too_large"]
    # No patch: the diff source left it out for its size, or could not read it.
    assert _whole(whole, patches={}, too_large=frozenset({"file-1"})) == [
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
        _files_of,
        [CollectionReference(path="a.py")],
        _Files({"a.py": _change("a.py", 1)}, {"file-1": patch}),
    )
    assert shown[0]["state"] == "ready"
    assert shown[0]["truncated"] is True
    hunks = shown[0]["hunks"]
    assert isinstance(hunks, list)
    assert [(hunk["old_start"], hunk["new_start"], len(hunk["lines"])) for hunk in hunks] == [
        (1, 1, 5),
        (9, 10, 1),
    ]


def test_a_deleted_file_reference_has_no_new_side() -> None:
    change = _change("a.py", 1).model_copy(update={"kind": ChangeKind.deleted, "new": None})
    patch = FilePatch(
        file_id=change.id,
        truncated=False,
        hunks=(
            Hunk(
                old_start=1,
                old_count=1,
                new_start=0,
                new_count=0,
                lines=(LineRecord(op=LineOp.delete, text="old"),),
            ),
        ),
    )
    [shown] = _references(
        _files_of, [CollectionReference(path="a.py")], _Files({"a.py": change}, {change.id: patch})
    )
    assert shown["state"] == "ready"
    assert shown["deleted"] is True


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
