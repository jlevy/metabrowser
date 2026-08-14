"""Wire-shape definitions for the browser tree API.

Single source of truth for the JSON payload shape returned by
``/api/tree`` (file/dir nodes) and ``/api/recent`` (clustered
dir/file rows). Two producers — :func:`metabrowser.tree._dir_tree`
(filesystem walk) and :func:`metabrowser.tree._build_inventory_tree`
(InventoryIndex read) — must emit values that satisfy these
TypedDicts. The SPA's ``renderTreeNodes`` reads the same shape.

Why this exists
---------------

Two historical contract bugs motivate a type-checked envelope:

1. ``children: undefined``: ``_build_inventory_tree`` emitted dirs
   without the ``children`` key when the depth cap kicked in;
   the SPA's ``Array.isArray(node.children)`` check fell through
   to the lazy-stub branch, so empty dirs spun forever.
2. ``mtime: null`` on empty finalized dirs: the SPA's
   ``formatAge`` rendered the pending-skeleton pulse for
   genuinely empty dirs that should have shown nothing.

The :func:`validate_tree_node` helper is invoked from the
matching tests (``test_browser_wire_shape.py``) on every shape
the two producers can emit, so future drift fails the suite.

Convention
----------

* TypedDicts use ``total=False`` for keys whose presence is
  conditional (``gitignored``, ``empty``, ``compressed``, …).
* The ``children`` key on directory nodes is **always present**
  even when ``None`` (lazy-load sentinel) — that's the contract
  the SPA's ``Array.isArray`` check relies on.
* The ``mtime`` key:
  - On **files**: always a real ``int | float`` (never ``None``).
  - On **dirs**: ``None`` means "walker still finalizing" → the
    SPA renders a pulsing skeleton.
    ``0.0`` means "finalized + genuinely empty" → no age text.
    Any other value is the newest-descendant mtime in seconds.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal, NotRequired, TypedDict, cast

from metabrowser.file_type_filters import FILE_TYPE_FAMILIES, family_for_extension


class FileNode(TypedDict, total=False):
    """A file leaf in the tree response.

    ``name`` / ``path`` / ``type`` / ``size`` / ``mtime`` are
    required; the rest are conditional. Listed via ``total=False``
    so the runtime validator below only enforces presence on the
    required keys (TypedDicts can't mix required and optional in
    pre-3.11 syntax without ``Required[]`` / ``NotRequired[]``).
    """

    name: str
    path: str
    type: Literal["file"]
    size: int
    mtime: float
    # Conditional fields (server emits when applicable):
    #
    # ``ext`` is the index's compound-tail extension (".min.js",
    # ".runbook.md"), the unit the navigation type filter and its tally
    # both key on. Distinct from ``logical_ext``, which means "the
    # inner extension of a compressed artifact" and drives icon
    # dispatch — a ``foo.jsonl.gz`` carries both, and they differ.
    ext: str
    logical_ext: str
    compressed: bool
    compression: Literal["gzip", "zlib"]
    gitignored: bool


class DirNode(TypedDict, total=False):
    """A directory node in the tree response.

    ``children`` is required and may be ``None`` (lazy-load
    sentinel past the depth cap) or a list. The SPA's
    ``Array.isArray(node.children)`` check distinguishes the two.

    Aggregates (``total_files`` / ``total_size`` / ``mtime``) are
    optional-typed but must always appear with at least ``None``.
    The walker emits ``None`` while finalizing the subtree; the
    SPA renders the cell as a pulsing skeleton until an
    ``fs.change`` op overwrites it.
    """

    name: str
    path: str
    type: Literal["dir"]
    children: list[Any] | None  # list[FileNode | DirNode] | None — recursion not supported
    total_files: int | None
    total_size: int | None
    mtime: float | None
    # Conditional fields:
    has_children: bool
    gitignored: bool
    empty: bool


# Required-key sets used by the runtime validator. A TypedDict
# itself doesn't carry "required" reflection in pre-3.11 form, so
# the gate sets are spelled out here. Keep these in sync with the
# class bodies above.
_FILE_REQUIRED: frozenset[str] = frozenset({"name", "path", "type", "size", "mtime"})
_DIR_REQUIRED: frozenset[str] = frozenset(
    {"name", "path", "type", "children", "total_files", "total_size", "mtime"}
)


def validate_tree_node(node: dict[str, Any], *, _path: str = "") -> None:
    """Raise :class:`AssertionError` if *node* doesn't match the
    contract in :class:`FileNode` / :class:`DirNode`. Recurses
    into ``children``.

    Tests call this on every shape the two tree producers
    (``_dir_tree``, ``_build_inventory_tree``) can emit — see
    ``test_browser_wire_shape.py``. A failure means the wire
    shape has drifted; either the producer is wrong or the
    TypedDict needs to extend.
    """

    assert isinstance(node, dict), f"node is not a dict at {_path!r}: {type(node).__name__}"
    assert "type" in node, f"missing 'type' at {_path!r}"
    kind = node["type"]
    if kind == "file":
        _validate_file(node, _path=_path)
    elif kind == "dir":
        _validate_dir(node, _path=_path)
    else:
        raise AssertionError(f"unknown node type {kind!r} at {_path!r}")


def _validate_file(node: dict[str, Any], *, _path: str) -> None:
    missing = _FILE_REQUIRED - node.keys()
    assert not missing, f"file node at {_path!r} missing keys: {sorted(missing)}"
    assert isinstance(node["name"], str), f"file.name not str at {_path!r}"
    assert isinstance(node["path"], str), f"file.path not str at {_path!r}"
    assert node["type"] == "file"
    assert isinstance(node["size"], int), f"file.size not int at {_path!r}: {node['size']!r}"
    # Files always carry a concrete mtime; ``None`` is reserved
    # for dirs whose walker hasn't finalized yet.
    assert isinstance(node["mtime"], (int, float)), (
        f"file.mtime not numeric at {_path!r}: {node['mtime']!r} "
        f"(None on a file is a contract violation — was a dir node mistakenly tagged?)"
    )


def _validate_dir(node: dict[str, Any], *, _path: str) -> None:
    missing = _DIR_REQUIRED - node.keys()
    assert not missing, (
        f"dir node at {_path!r} missing keys: {sorted(missing)}. "
        # ``children`` was once elided when the depth cap kicked in.
        # Check this branch first since the SPA's
        # ``Array.isArray(children)`` rendering relies on the key
        # always being present.
        f"Wire contract: ``children`` must always be present "
        f"(may be ``None``) so the SPA's Array.isArray check can branch."
    )
    assert isinstance(node["name"], str), f"dir.name not str at {_path!r}"
    assert isinstance(node["path"], str), f"dir.path not str at {_path!r}"
    assert node["type"] == "dir"

    children = node["children"]
    if children is not None:
        assert isinstance(children, list), f"dir.children not list/None at {_path!r}"
        for i, child in enumerate(children):
            validate_tree_node(
                child, _path=f"{_path}/{node['name']}#{i}" if _path else f"{node['name']}#{i}"
            )

    # Aggregates: int | None. ``None`` is the walker-pending signal.
    for agg in ("total_files", "total_size"):
        v = node[agg]
        assert v is None or isinstance(v, int), f"dir.{agg} not int|None at {_path!r}: {v!r}"
    mtime = node["mtime"]
    assert mtime is None or isinstance(mtime, (int, float)), (
        f"dir.mtime not numeric|None at {_path!r}: {mtime!r}"
    )

    # Conditional flags must be the right type when present.
    if "gitignored" in node:
        assert isinstance(node["gitignored"], bool), f"dir.gitignored not bool at {_path!r}"
    if "empty" in node:
        assert isinstance(node["empty"], bool), f"dir.empty not bool at {_path!r}"
    if "has_children" in node:
        assert isinstance(node["has_children"], bool), f"dir.has_children not bool at {_path!r}"


class RollupFileNode(TypedDict):
    """A file leaf in a `/api/rollup` node tree. All keys required;
    `mtime` is always numeric (state lives on directories)."""

    name: str
    path: str
    type: Literal["file"]
    size: int
    mtime: float
    ext: str
    gitignored: bool


class RollupRest(TypedDict):
    """Aggregate bucket for children past the per-directory `top` cap."""

    dirs: int
    files: int
    size: int
    unignored_files: int
    unignored_size: int


class RollupDirNode(TypedDict):
    """A directory node in a `/api/rollup` response.

    Unlike tree nodes, aggregates are always numeric — partial scans
    are flagged by ``state: "pending"`` instead of null tallies, so the
    treemap can lay out whatever is indexed so far. ``children`` is
    required and ``None`` past the emission depth (totals stay
    full-subtree); ``rest`` appears only when children were capped.
    """

    name: str
    path: str
    type: Literal["dir"]
    state: Literal["pending", "complete"]
    total_files: int
    total_size: int
    unignored_files: int
    unignored_size: int
    mtime: float
    gitignored: bool
    dominant_ext: str
    children: list[Any] | None
    rest: NotRequired[RollupRest]


type ExtensionTallyRow = tuple[str, int, int, int, int]


class NavigationTallies(TypedDict):
    """One complete-index pass backing root navigation filters."""

    summary: dict[str, int]
    extensions: list[list[object]]
    canonical_extensions: list[list[object]]
    type_families: list[list[object]]
    type_presets: list[list[object]]
    recency_tallies: list[list[object]]


class TypeFamilyTally(TypedDict):
    """One semantic family and its conserved canonical-extension children."""

    id: str
    all_files: int
    all_bytes: int
    unignored_files: int
    unignored_bytes: int
    extensions: list[ExtensionTallyRow]


class TypeTallies(TypedDict):
    """Bounded top-level semantic and ungrouped rollup populations."""

    families: list[TypeFamilyTally]
    extensions: list[ExtensionTallyRow]


class RollupResult(TypedDict):
    """Inventory rollup before route metadata is attached."""

    node: RollupDirNode
    ext_tallies: list[ExtensionTallyRow]
    type_tallies: TypeTallies


class RollupEnvelope(TypedDict):
    """Complete `/api/rollup` response, including cold-index state."""

    root: str
    path: str
    node: RollupDirNode | None
    ext_tallies: list[ExtensionTallyRow]
    type_tallies: TypeTallies
    index_status: str
    indexed_files: int
    max_files: int
    truncated: bool


_ROLLUP_FILE_REQUIRED: frozenset[str] = frozenset(
    {"name", "path", "type", "size", "mtime", "ext", "gitignored"}
)
_ROLLUP_DIR_REQUIRED: frozenset[str] = frozenset(
    {
        "name",
        "path",
        "type",
        "state",
        "total_files",
        "total_size",
        "unignored_files",
        "unignored_size",
        "mtime",
        "gitignored",
        "dominant_ext",
        "children",
    }
)
_ROLLUP_REST_REQUIRED: frozenset[str] = frozenset(
    {"dirs", "files", "size", "unignored_files", "unignored_size"}
)


def validate_rollup_node(node: Mapping[str, Any], *, _path: str = "") -> None:
    """Raise :class:`AssertionError` if *node* doesn't match
    :class:`RollupFileNode` / :class:`RollupDirNode`. Recurses into
    ``children``. Route tests call this on every emitted shape."""

    assert isinstance(node, dict), f"rollup node not a dict at {_path!r}"
    kind = node.get("type")
    if kind == "file":
        missing = _ROLLUP_FILE_REQUIRED - node.keys()
        assert not missing, f"rollup file at {_path!r} missing keys: {sorted(missing)}"
        assert isinstance(node["size"], int)
        assert isinstance(node["mtime"], (int, float))
        assert isinstance(node["ext"], str)
        assert isinstance(node["gitignored"], bool)
        return
    assert kind == "dir", f"unknown rollup node type {kind!r} at {_path!r}"
    missing = _ROLLUP_DIR_REQUIRED - node.keys()
    assert not missing, f"rollup dir at {_path!r} missing keys: {sorted(missing)}"
    assert node["state"] in ("pending", "complete"), f"bad state at {_path!r}: {node['state']!r}"
    for agg_key in ("total_files", "total_size", "unignored_files", "unignored_size"):
        assert isinstance(node[agg_key], int), f"rollup dir.{agg_key} not int at {_path!r}"
    assert node["unignored_files"] <= node["total_files"], f"unignored > total at {_path!r}"
    assert node["unignored_size"] <= node["total_size"], f"unignored > total at {_path!r}"
    assert isinstance(node["mtime"], (int, float)), f"rollup dir.mtime not numeric at {_path!r}"
    assert isinstance(node["dominant_ext"], str)
    if "rest" in node:
        rest = node["rest"]
        missing_rest = _ROLLUP_REST_REQUIRED - rest.keys()
        assert not missing_rest, f"rollup rest at {_path!r} missing keys: {sorted(missing_rest)}"
        for rest_key in _ROLLUP_REST_REQUIRED:
            assert isinstance(rest[rest_key], int), f"rest.{rest_key} not int at {_path!r}"
    children = node["children"]
    if children is not None:
        assert isinstance(children, list), f"rollup dir.children not list/None at {_path!r}"
        for i, child in enumerate(children):
            child_path = f"{_path}/{node['name']}#{i}" if _path else f"{node['name']}#{i}"
            validate_rollup_node(child, _path=child_path)


def validate_extension_tallies(rows: Sequence[Sequence[object]]) -> None:
    """Assert the compact five-cell tally contract and its population invariants."""

    seen: set[str] = set()
    for index, row in enumerate(rows):
        assert len(row) == 5, f"extension tally row {index} must have five cells"
        key = row[0]
        assert isinstance(key, str), f"extension tally key {index} must be a string"
        assert key not in seen, f"duplicate extension tally key: {key!r}"
        seen.add(key)
        if key == "":
            assert index == len(rows) - 1, "the Other tally must be final"
        raw_values = row[1:]
        assert all(
            isinstance(value, int) and not isinstance(value, bool) for value in raw_values
        ), f"extension tally values must be integers at row {index}"
        values = cast(tuple[int, int, int, int], tuple(raw_values))
        assert all(value >= 0 for value in values), (
            f"extension tally values must be nonnegative at row {index}"
        )
        assert values[2] <= values[0], f"unignored files exceed all files at row {index}"
        assert values[3] <= values[1], f"unignored bytes exceed all bytes at row {index}"


def validate_type_tallies(raw: object, node: Mapping[str, Any]) -> None:
    """Assert semantic hierarchy, catalog identity, and root conservation."""

    assert isinstance(raw, dict), "type tallies must be an object"
    assert set(raw) == {"families", "extensions"}
    families = raw["families"]
    extensions = raw["extensions"]
    assert isinstance(families, list)
    assert isinstance(extensions, list)
    validate_extension_tallies(extensions)

    known_family_ids = {family.id for family in FILE_TYPE_FAMILIES}
    seen_family_ids: set[str] = set()
    top_level_totals = [sum(row[column] for row in extensions) for column in range(1, 5)]
    for index, family in enumerate(families):
        assert isinstance(family, dict), f"type family tally {index} must be an object"
        assert set(family) == {
            "id",
            "all_files",
            "all_bytes",
            "unignored_files",
            "unignored_bytes",
            "extensions",
        }
        family_id = family["id"]
        assert isinstance(family_id, str) and family_id in known_family_ids
        assert family_id not in seen_family_ids, f"duplicate type family tally: {family_id!r}"
        seen_family_ids.add(family_id)
        child_rows = family["extensions"]
        assert isinstance(child_rows, list)
        validate_extension_tallies(child_rows)
        for row in child_rows:
            match = family_for_extension(cast(str, row[0]))
            assert match is not None
            assert match.family.id == family_id
            assert match.canonical_extension == row[0]
        metrics = [
            family["all_files"],
            family["all_bytes"],
            family["unignored_files"],
            family["unignored_bytes"],
        ]
        assert all(isinstance(value, int) and not isinstance(value, bool) for value in metrics)
        assert all(cast(int, value) >= 0 for value in metrics)
        assert metrics[2] <= metrics[0]
        assert metrics[3] <= metrics[1]
        child_totals = [sum(row[column] for row in child_rows) for column in range(1, 5)]
        assert child_totals == metrics, f"type family children do not sum to {family_id!r}"
        for metric_index, value in enumerate(metrics):
            top_level_totals[metric_index] += cast(int, value)

    for row in extensions:
        key = cast(str, row[0])
        if key not in ("", "(none)"):
            assert family_for_extension(key) is None, f"known family member emitted raw: {key!r}"
    assert top_level_totals == [
        node["total_files"],
        node["total_size"],
        node["unignored_files"],
        node["unignored_size"],
    ]


def validate_rollup_result(result: Mapping[str, Any]) -> None:
    """Assert one inventory result and the equality of root and tally totals."""

    assert set(result) == {"node", "ext_tallies", "type_tallies"}
    node = result["node"]
    assert isinstance(node, dict)
    validate_rollup_node(node)
    rows = result["ext_tallies"]
    assert isinstance(rows, list)
    validate_extension_tallies(rows)
    column_totals = [sum(row[column] for row in rows) for column in range(1, 5)]
    assert column_totals == [
        node["total_files"],
        node["total_size"],
        node["unignored_files"],
        node["unignored_size"],
    ]
    validate_type_tallies(result["type_tallies"], node)


def validate_rollup_envelope(envelope: Mapping[str, Any]) -> None:
    """Assert route metadata plus either a valid result or an empty cold envelope."""

    assert isinstance(envelope.get("root"), str)
    assert isinstance(envelope.get("path"), str)
    assert envelope.get("index_status") in ("idle", "scanning", "done", "truncated", "failed")
    for key in ("indexed_files", "max_files"):
        value = envelope.get(key)
        assert isinstance(value, int) and not isinstance(value, bool) and value >= 0
    assert isinstance(envelope.get("truncated"), bool)
    node = envelope.get("node")
    rows = envelope.get("ext_tallies")
    type_tallies = envelope.get("type_tallies")
    assert isinstance(rows, list)
    assert isinstance(type_tallies, dict)
    if node is None:
        assert rows == [], "a cold rollup cannot advertise tallies"
        assert type_tallies == {"families": [], "extensions": []}
        return
    validate_rollup_result({"node": node, "ext_tallies": rows, "type_tallies": type_tallies})


__all__ = [
    "DirNode",
    "ExtensionTallyRow",
    "FileNode",
    "NavigationTallies",
    "RollupDirNode",
    "RollupEnvelope",
    "RollupFileNode",
    "RollupRest",
    "RollupResult",
    "TypeFamilyTally",
    "TypeTallies",
    "validate_extension_tallies",
    "validate_rollup_envelope",
    "validate_rollup_node",
    "validate_rollup_result",
    "validate_tree_node",
    "validate_type_tallies",
]
