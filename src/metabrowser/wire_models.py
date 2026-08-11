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

from typing import Any, Literal, TypedDict


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


__all__ = [
    "DirNode",
    "FileNode",
    "validate_tree_node",
]
