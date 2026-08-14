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
from metabrowser.file_type_registry import load_file_type_registry
from metabrowser.settings import (
    ROLLUP_FILE_TYPE_FILENAME_LIMIT,
    ROLLUP_FILE_TYPE_REMAINING_LIMIT,
)


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
    # ``ext`` is the index's bounded compound-tail extension (".min.js",
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
    file_type_registry: FileTypeRegistryIdentity
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


class FileTypeMeasure(TypedDict):
    """One population's conserved file and apparent-byte measures."""

    files: int
    bytes: int


type FileTypePopulationMetrics = dict[str, FileTypeMeasure]


class FileTypeRegistryIdentity(TypedDict):
    """Registry identity required to interpret a breakdown."""

    schema_version: int
    revision: int
    fingerprint: str


class FileTypeExtensionBreakdown(TypedDict):
    extension: str
    metrics: FileTypePopulationMetrics


class FileTypeFilenameBreakdown(TypedDict):
    basename: str
    metrics: FileTypePopulationMetrics


class FileTypeOthersBreakdown(TypedDict):
    metrics: FileTypePopulationMetrics
    omitted_distinct_values: int


class FileTypeFamilyBreakdown(TypedDict):
    id: str
    metrics: FileTypePopulationMetrics
    extensions: list[FileTypeExtensionBreakdown]


class FileTypeGroupBreakdown(TypedDict):
    id: str
    families: list[FileTypeFamilyBreakdown]


class FileTypeNoExtensionBreakdown(TypedDict):
    metrics: FileTypePopulationMetrics
    filenames: list[FileTypeFilenameBreakdown]
    others: FileTypeOthersBreakdown | None


class FileTypeRemainingBreakdown(TypedDict):
    metrics: FileTypePopulationMetrics
    extensions: list[FileTypeExtensionBreakdown]
    others: FileTypeOthersBreakdown | None


class FileTypeBreakdown(TypedDict):
    """Complete File Rollup Format directory partition."""

    schema: Literal["file-type-breakdown-v1"]
    registry: FileTypeRegistryIdentity
    metrics: FileTypePopulationMetrics
    groups: list[FileTypeGroupBreakdown]
    no_extension: FileTypeNoExtensionBreakdown
    remaining_types: FileTypeRemainingBreakdown


class RollupResult(TypedDict):
    """Inventory rollup before route metadata is attached."""

    node: RollupDirNode
    ext_tallies: list[ExtensionTallyRow]
    type_tallies: TypeTallies
    file_type_breakdown: FileTypeBreakdown


class RollupEnvelope(TypedDict):
    """Complete `/api/rollup` response, including cold-index state."""

    root: str
    path: str
    node: RollupDirNode | None
    ext_tallies: list[ExtensionTallyRow]
    type_tallies: TypeTallies
    file_type_breakdown: FileTypeBreakdown | None
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


def _validated_population_metrics(raw: object) -> dict[str, tuple[int, int]]:
    assert isinstance(raw, dict), "file-type metrics must be an object"
    assert set(raw) == {"all", "unignored"}
    result: dict[str, tuple[int, int]] = {}
    for population, measure in raw.items():
        assert isinstance(population, str)
        assert isinstance(measure, dict)
        assert set(measure) == {"files", "bytes"}
        files = measure["files"]
        size = measure["bytes"]
        assert isinstance(files, int) and not isinstance(files, bool) and files >= 0
        assert isinstance(size, int) and not isinstance(size, bool) and size >= 0
        result[population] = (files, size)
    assert result["unignored"][0] <= result["all"][0]
    assert result["unignored"][1] <= result["all"][1]
    return result


def _sum_population_metrics(
    rows: Sequence[dict[str, tuple[int, int]]],
) -> dict[str, tuple[int, int]]:
    return {
        population: (
            sum(row[population][0] for row in rows),
            sum(row[population][1] for row in rows),
        )
        for population in ("all", "unignored")
    }


def validate_file_type_breakdown(raw: object, node: Mapping[str, Any]) -> None:
    """Assert file-rollup identity, hierarchy, bounds, and conservation."""

    assert isinstance(raw, dict), "file-type breakdown must be an object"
    assert set(raw) == {
        "schema",
        "registry",
        "metrics",
        "groups",
        "no_extension",
        "remaining_types",
    }
    assert raw["schema"] == "file-type-breakdown-v1"
    registry = raw["registry"]
    assert isinstance(registry, dict)
    assert set(registry) == {"schema_version", "revision", "fingerprint"}
    assert registry["schema_version"] == 1
    active_registry = load_file_type_registry()
    assert registry["revision"] == active_registry.revision
    assert registry["fingerprint"] == active_registry.fingerprint
    root_metrics = _validated_population_metrics(raw["metrics"])
    assert root_metrics == {
        "all": (node["total_files"], node["total_size"]),
        "unignored": (node["unignored_files"], node["unignored_size"]),
    }

    groups = raw["groups"]
    assert isinstance(groups, list)
    family_metrics: list[dict[str, tuple[int, int]]] = []
    seen_groups: set[str] = set()
    seen_families: set[str] = set()
    known_families = {family.id: family for family in FILE_TYPE_FAMILIES}
    emitted_group_ids: list[str] = []
    for group in groups:
        assert isinstance(group, dict) and set(group) == {"id", "families"}
        group_id = group["id"]
        assert isinstance(group_id, str) and group_id not in seen_groups
        seen_groups.add(group_id)
        emitted_group_ids.append(group_id)
        families = group["families"]
        assert isinstance(families, list) and families
        emitted_family_ids: list[str] = []
        for family in families:
            assert isinstance(family, dict)
            assert set(family) == {"id", "metrics", "extensions"}
            family_id = family["id"]
            assert isinstance(family_id, str) and family_id not in seen_families
            descriptor = known_families[family_id]
            assert descriptor.category == group_id
            seen_families.add(family_id)
            emitted_family_ids.append(family_id)
            metrics = _validated_population_metrics(family["metrics"])
            extensions = family["extensions"]
            assert isinstance(extensions, list) and extensions
            child_metrics: list[dict[str, tuple[int, int]]] = []
            seen_extensions: set[str] = set()
            emitted_extensions: list[str] = []
            for extension in extensions:
                assert isinstance(extension, dict)
                assert set(extension) == {"extension", "metrics"}
                key = extension["extension"]
                assert isinstance(key, str) and key.startswith(".") and key not in seen_extensions
                seen_extensions.add(key)
                emitted_extensions.append(key)
                child_metrics.append(_validated_population_metrics(extension["metrics"]))
            assert emitted_extensions == [
                extension for extension in descriptor.extensions if extension in seen_extensions
            ]
            assert _sum_population_metrics(child_metrics) == metrics
            family_metrics.append(metrics)
        assert emitted_family_ids == [
            family.id
            for family in FILE_TYPE_FAMILIES
            if family.category == group_id and family.id in emitted_family_ids
        ]
    assert emitted_group_ids == [
        group.id for group in active_registry.groups if group.id in emitted_group_ids
    ]

    no_extension = raw["no_extension"]
    assert isinstance(no_extension, dict)
    assert set(no_extension) == {"metrics", "filenames", "others"}
    no_extension_metrics = _validated_population_metrics(no_extension["metrics"])
    filenames = no_extension["filenames"]
    assert isinstance(filenames, list) and len(filenames) <= ROLLUP_FILE_TYPE_FILENAME_LIMIT
    no_extension_children: list[dict[str, tuple[int, int]]] = []
    seen_filenames: set[str] = set()
    for filename in filenames:
        assert isinstance(filename, dict) and set(filename) == {"basename", "metrics"}
        basename = filename["basename"]
        assert isinstance(basename, str) and basename and basename not in seen_filenames
        seen_filenames.add(basename)
        no_extension_children.append(_validated_population_metrics(filename["metrics"]))
    no_extension_others = no_extension["others"]
    if no_extension_others is not None:
        assert isinstance(no_extension_others, dict)
        assert set(no_extension_others) == {"metrics", "omitted_distinct_values"}
        assert (
            isinstance(no_extension_others["omitted_distinct_values"], int)
            and no_extension_others["omitted_distinct_values"] > 0
        )
        no_extension_children.append(_validated_population_metrics(no_extension_others["metrics"]))
    assert _sum_population_metrics(no_extension_children) == no_extension_metrics

    remaining = raw["remaining_types"]
    assert isinstance(remaining, dict)
    assert set(remaining) == {"metrics", "extensions", "others"}
    remaining_metrics = _validated_population_metrics(remaining["metrics"])
    remaining_extensions = remaining["extensions"]
    assert (
        isinstance(remaining_extensions, list)
        and len(remaining_extensions) <= ROLLUP_FILE_TYPE_REMAINING_LIMIT
    )
    remaining_children: list[dict[str, tuple[int, int]]] = []
    seen_remaining: set[str] = set()
    for extension in remaining_extensions:
        assert isinstance(extension, dict) and set(extension) == {"extension", "metrics"}
        key = extension["extension"]
        assert isinstance(key, str) and key.startswith(".") and key not in seen_remaining
        assert family_for_extension(key) is None
        seen_remaining.add(key)
        remaining_children.append(_validated_population_metrics(extension["metrics"]))
    remaining_others = remaining["others"]
    if remaining_others is not None:
        assert isinstance(remaining_others, dict)
        assert set(remaining_others) == {"metrics", "omitted_distinct_values"}
        assert (
            isinstance(remaining_others["omitted_distinct_values"], int)
            and remaining_others["omitted_distinct_values"] > 0
        )
        remaining_children.append(_validated_population_metrics(remaining_others["metrics"]))
    assert _sum_population_metrics(remaining_children) == remaining_metrics
    assert (
        _sum_population_metrics([*family_metrics, no_extension_metrics, remaining_metrics])
        == root_metrics
    )


def validate_rollup_result(result: Mapping[str, Any]) -> None:
    """Assert one inventory result and the equality of root and tally totals."""

    assert set(result) in (
        {"node", "ext_tallies", "type_tallies"},
        {"node", "ext_tallies", "type_tallies", "file_type_breakdown"},
    )
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
    if "file_type_breakdown" in result:
        validate_file_type_breakdown(result["file_type_breakdown"], node)


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
    file_type_breakdown = envelope.get("file_type_breakdown")
    assert isinstance(rows, list)
    assert isinstance(type_tallies, dict)
    if node is None:
        assert rows == [], "a cold rollup cannot advertise tallies"
        assert type_tallies == {"families": [], "extensions": []}
        assert file_type_breakdown is None
        return
    result = {"node": node, "ext_tallies": rows, "type_tallies": type_tallies}
    if file_type_breakdown is not None:
        result["file_type_breakdown"] = file_type_breakdown
    validate_rollup_result(result)


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
    "validate_file_type_breakdown",
    "validate_rollup_envelope",
    "validate_rollup_node",
    "validate_rollup_result",
    "validate_tree_node",
    "validate_type_tallies",
]
