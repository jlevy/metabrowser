"""Focused contracts for pure inventory rollup aggregation."""

from __future__ import annotations

import random
from collections.abc import Iterator
from dataclasses import dataclass, replace
from typing import Any, cast

import pytest
from conftest import SyntheticIndexWriter

from metabrowser.events import FsEntry
from metabrowser.file_type_registry import FileTypeClassification, load_file_type_registry
from metabrowser.inventory_engine.providers.python_inventory import (
    _PythonInventoryStore as PythonInventoryStore,
)
from metabrowser.inventory_rollup import (
    RollupEncoding,
    RollupIgnored,
    RollupOptions,
    RollupRank,
    build_rollup,
    group_rollup_children,
)
from metabrowser.wire_models import validate_rollup_node


def _synthetic_index(files: list[tuple[str, int, bool]]) -> PythonInventoryStore:
    index = PythonInventoryStore()
    entries = SyntheticIndexWriter(index)
    mtime_ns = 1_700_000_000_000_000_000
    root = FsEntry.for_observed_dir(path="", parent="", name="root")
    entries[""] = replace(
        root,
        total_files=len(files),
        total_size=sum(size for _name, size, _ignored in files),
        newest_mtime_ns=mtime_ns,
    )
    for name, size, ignored in files:
        entry = FsEntry.for_observed_file(
            path=name,
            parent="",
            name=name,
            size=size,
            mtime_ns=mtime_ns,
        )
        entries[name] = replace(entry, gitignored=ignored)
    return index


def test_rollup_options_reject_invalid_limits_and_rank() -> None:
    with pytest.raises(ValueError):
        RollupOptions(depth=-1, top=0, ext_top=0, max_nodes=0)
    with pytest.raises(ValueError):
        RollupOptions(depth=0, top=-1, ext_top=0, max_nodes=0)
    with pytest.raises(ValueError):
        RollupOptions(depth=0, top=0, ext_top=-1, max_nodes=0)
    with pytest.raises(ValueError):
        RollupOptions(depth=0, top=0, ext_top=0, max_nodes=-1)
    with pytest.raises(ValueError):
        RollupOptions(depth=0, top=0, ext_top=0, max_nodes=0, remaining_top=-1)
    with pytest.raises(ValueError):
        RollupOptions(depth=0, top=0, ext_top=0, max_nodes=0, remaining_top=21)
    with pytest.raises(ValueError):
        RollupOptions(depth=0, top=0, ext_top=0, max_nodes=0, filename_top=21)
    with pytest.raises(ValueError):
        RollupOptions(
            depth=0,
            top=0,
            ext_top=0,
            max_nodes=0,
            ext_rank=cast(RollupRank, "unknown"),
        )


def test_dual_rank_keeps_count_and_byte_heavy_types_with_exact_other() -> None:
    files = [(f"tiny-{index}.txt", 1, False) for index in range(20)]
    files.extend(
        [
            ("large.bin", 10_000, False),
            ("ignored.log", 9_000, True),
            ("empty.cfg", 0, False),
            ("README", 7, False),
        ]
    )
    index = _synthetic_index(files)

    result = index.rollup("", depth=0, top=0, ext_top=2, ext_rank="dual")
    assert result is not None
    assert result["node"]["children"] is None
    rows = result["ext_tallies"]
    assert [row[0] for row in rows] == [".bin", ".txt", ""]
    assert rows[-1][1:] == (3, 9_007, 2, 7)
    assert sum(row[1] for row in rows) == 24
    assert sum(row[2] for row in rows) == 19_027
    assert sum(row[3] for row in rows) == 23
    assert sum(row[4] for row in rows) == 10_027


def test_dual_rank_uses_union_of_all_populations() -> None:
    index = _synthetic_index(
        [
            ("tracked.py", 0, False),
            ("ignored.md", 0, True),
            ("extensionless", 0, False),
        ]
    )

    result = index.rollup("", depth=0, top=0, ext_top=10, ext_rank="dual")
    assert result is not None
    assert {row[0] for row in result["ext_tallies"]} == {".py", ".md", "(none)"}
    assert result["node"]["total_size"] == 0


def test_zero_top_accounts_for_omitted_children_when_depth_allows() -> None:
    index = _synthetic_index([("one.py", 5, False), ("two.md", 7, False)])

    result = index.rollup("", depth=1, top=0, ext_top=10, ext_rank="dual")
    assert result is not None
    assert result["node"]["children"] == []
    assert result["node"].get("rest") == {
        "dirs": 0,
        "files": 2,
        "size": 12,
        "unignored_files": 2,
        "unignored_size": 12,
    }


def test_breakdown_aggregates_families_before_bounding_the_remaining_tail() -> None:
    files = [
        ("app.js", 10, False),
        ("bundle.min.js", 20, False),
        ("worker.mjs", 30, True),
        ("types.d.ts", 5, False),
        ("large.unknown", 1_000, False),
        ("many.raw", 3, False),
        ("README", 7, False),
    ]
    index = _synthetic_index(files)

    result = index.rollup("", depth=0, top=0, ext_top=1, remaining_top=1, ext_rank="dual")

    assert result is not None
    breakdown = result["file_type_breakdown"]
    families = {
        family["id"]: family for group in breakdown["groups"] for family in group["families"]
    }
    # Compound suffixes fold into the canonical family member before any cap applies,
    # so a low remaining_top never truncates a known family.
    assert families["javascript"]["metrics"] == {
        "all": {"files": 3, "bytes": 60},
        "unignored": {"files": 2, "bytes": 30},
    }
    assert [child["extension"] for child in families["javascript"]["extensions"]] == [
        ".js",
        ".mjs",
    ]
    assert families["typescript"]["extensions"] == [
        {
            "extension": ".ts",
            "metrics": {"all": {"files": 1, "bytes": 5}, "unignored": {"files": 1, "bytes": 5}},
        }
    ]

    assert [row["basename"] for row in breakdown["no_extension"]["filenames"]] == ["README"]
    remaining = breakdown["remaining_types"]
    assert len(remaining["extensions"]) == 1
    assert remaining["others"] is not None
    assert remaining["others"]["omitted_distinct_values"] == 1

    totals = breakdown["metrics"]["all"]
    assert totals["files"] == result["node"]["total_files"]
    assert totals["bytes"] == result["node"]["total_size"]


def test_rollup_classifies_each_distinct_extension_once(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = load_file_type_registry()
    calls: list[str] = []

    class CountingRegistry:
        def __getattr__(self, name: str) -> Any:
            return getattr(registry, name)

        def classify(self, name: str, extension: str) -> FileTypeClassification:
            calls.append(extension)
            return registry.classify(name, extension)

    index = _synthetic_index(
        [
            ("app.js", 1, False),
            ("bundle.min.js", 1, False),
            ("types.d.ts", 1, False),
            ("unknown.zzz", 1, False),
            ("README", 1, False),
        ]
    )
    monkeypatch.setattr(index, "_registry", CountingRegistry())

    result = index.rollup("", depth=0, top=0, ext_top=0, remaining_top=20, ext_rank="dual")

    assert result is not None
    assert sorted(calls) == [".d.ts", ".js", ".min.js", ".zzz"]


def test_registry_breakdown_groups_families_and_bounds_fallback_children() -> None:
    files = [
        ("events.jsonl", 20, False),
        ("notes.log", 10, True),
        ("photo.svg", 5, False),
    ]
    files.extend((f"bare-{index}", index, False) for index in range(21))
    files.extend((f"unknown-{index}.x{index}", index, False) for index in range(21))
    index = _synthetic_index(files)

    result = index.rollup("", depth=0, top=0, ext_top=1, remaining_top=20, filename_top=20)

    assert result is not None
    breakdown = result["file_type_breakdown"]
    assert breakdown["schema"] == "file-type-breakdown-v1"
    groups = {group["id"]: group for group in breakdown["groups"]}
    log_files = next(
        family for family in groups["other"]["families"] if family["id"] == "log-files"
    )
    assert log_files["id"] == "log-files"
    assert {row["extension"] for row in log_files["extensions"]} == {".jsonl", ".log"}
    assert groups["media"]["families"][0]["id"] == "images"

    no_extension = breakdown["no_extension"]
    assert len(no_extension["filenames"]) == 20
    assert no_extension["others"] is not None
    assert no_extension["others"]["omitted_distinct_values"] == 1
    remaining = breakdown["remaining_types"]
    assert len(remaining["extensions"]) == 20
    assert remaining["others"] is not None
    assert remaining["others"]["omitted_distinct_values"] == 1


@dataclass(frozen=True, slots=True)
class _RollupProbe:
    path: str
    parent: str
    name: str
    type: str
    ext: str
    size: int
    mtime_ns: int
    gitignored: bool
    total_files: int | None


def test_omit_mtime_drops_mtime_from_emitted_nodes() -> None:
    entries = {
        "": _RollupProbe("", "", "root", "dir", "", 0, 1, False, 1),
        "a.txt": _RollupProbe("a.txt", "", "a.txt", "file", ".txt", 4, 1, False, None),
    }
    result = build_rollup(
        entries,
        group_rollup_children(entries),
        "",
        RollupOptions(depth=1, top=10, ext_top=10, max_nodes=10, omit_mtime=True),
        False,
    )
    assert result is not None
    assert "mtime" not in result["node"]
    children = result["node"]["children"]
    assert children is not None
    assert "mtime" not in children[0]


def test_rollup_mtime_stays_in_the_filesystem_key_order() -> None:
    entries = {
        "": _RollupProbe("", "", "root", "dir", "", 0, 1, False, 1),
        "a.txt": _RollupProbe("a.txt", "", "a.txt", "file", ".txt", 4, 1, False, None),
    }
    result = build_rollup(
        entries,
        group_rollup_children(entries),
        "",
        RollupOptions(depth=1, top=10, ext_top=10, max_nodes=10),
        False,
    )
    assert result is not None
    dir_keys = list(result["node"].keys())
    assert dir_keys.index("mtime") == dir_keys.index("unignored_size") + 1
    children = result["node"]["children"]
    assert children is not None
    file_keys = list(children[0].keys())
    assert file_keys[file_keys.index("size") : file_keys.index("ext") + 1] == [
        "size",
        "mtime",
        "ext",
    ]


def test_node_budget_expands_the_heaviest_directory_first() -> None:
    """A wide, light folder must not spend the budget a deep, heavy one needs.

    Level by level, the budget went to ``wide``'s thirty one-file folders and ``zdeep/a``
    came back unexpanded, though it holds most of the files. Heaviest first, the chain
    down to ``zdeep/a/b`` expands and its files are emitted. The heavy branch sorts after
    the light one, so expanding in path order fails here too.
    """

    entries = _probes(
        _dir(""),
        _dir("wide"),
        _dir("zdeep"),
        _dir("zdeep/a"),
        _dir("zdeep/a/b"),
        *(_dir(f"wide/s{i:02d}") for i in range(30)),
        *(_file(f"wide/s{i:02d}/x.py", 10) for i in range(30)),
        *(_file(f"zdeep/a/b/f{i:03d}.py", 10) for i in range(100)),
    )

    root = _rollup_root(entries, depth=6, top=50, max_nodes=40)
    nodes = _nodes_by_path(root)
    assert nodes["zdeep/a"]["children"] is not None
    assert nodes["zdeep/a/b"]["children"], "the heaviest chain was not expanded"
    assert len(nodes) <= 40


def test_node_budget_weighs_unignored_files_beside_all_files() -> None:
    """One response serves both Show ignored settings.

    ``build`` is ignored and holds most of all files; ``src`` holds most of the unignored
    ones. Both expand before ``docs``, which is light by either measure. Weighing all
    files alone leaves ``src`` unexpanded; weighing unignored files alone leaves ``build``.
    The budget is shared by both populations too: ``src/lib`` emits six of its eight
    files, its share of the visible entries waiting, where a share of all entries alone
    gives it one, the map with Show ignored off one file.
    """

    entries = _probes(
        _dir(""),
        _dir("build", ignored=True),
        _dir("build/a"),
        _dir("build/b"),
        _dir("src"),
        _dir("src/lib"),
        _dir("docs"),
        _dir("docs/guide"),
        *(_file(f"build/a/f{i:02d}.py") for i in range(50)),
        *(_file(f"build/b/f{i:02d}.py") for i in range(40)),
        *(_file(f"src/lib/f{i}.py") for i in range(8)),
        *(_file(f"docs/guide/f{i}.md") for i in range(2)),
    )

    nodes = _nodes_by_path(_rollup_root(entries, depth=12, top=50, max_nodes=15))
    assert [child["name"] for child in nodes["build"]["children"] or []] == ["a", "b"]
    assert len(nodes.get("src/lib", {}).get("children") or []) == 6
    assert nodes["src/lib"]["rest"]["unignored_files"] == 2
    assert len(nodes["build/a"]["children"] or []) == 2
    assert nodes["build/b"]["children"] is None
    assert nodes["docs"]["children"] is None


def test_node_budget_weighs_bytes_beside_files() -> None:
    """A folder heavy by bytes and one heavy by files both expand before a light one.

    ``assets`` holds one large file, ``tests`` many small ones, and ``misc`` is light by
    either measure, though it outweighs ``tests`` by bytes and ``assets`` by files.
    Each heavy folder emits its share of the budget, and ``misc/x`` is not reached.
    """

    entries = _probes(
        _dir(""),
        _dir("assets"),
        _dir("assets/img"),
        _dir("tests"),
        _dir("tests/unit"),
        _dir("misc"),
        _dir("misc/x"),
        _file("assets/img/hero.png", 9_000),
        *(_file(f"tests/unit/t{i}.py", 1) for i in range(8)),
        *(_file(f"misc/x/m{i}.bin", 500) for i in range(2)),
    )

    nodes = _nodes_by_path(_rollup_root(entries, depth=12, top=50, max_nodes=13))
    assert len(nodes["assets/img"]["children"] or []) == 1
    assert len(nodes.get("tests/unit", {}).get("children") or []) == 5
    assert nodes["misc/x"]["children"] is None


def test_node_budget_breaks_an_exact_weight_tie_by_path() -> None:
    """Equal weights at one level expand in path order, whatever order they were found.

    ``q`` outweighs ``p``, so ``q/aa`` is found before ``p/zz``; the two weigh exactly the
    same, so path order expands ``p/zz`` first, and it takes its share of the budget
    rounded up, three of five files to two. The emitted tree is the same whatever order
    the entries arrive in.
    """

    probes = (
        _dir(""),
        _dir("p"),
        _dir("p/zz"),
        _dir("q"),
        _dir("q/aa"),
        _file("q/f1.py"),
        _file("q/f2.py"),
        *(_file(f"p/zz/f{i}.py") for i in range(5)),
        *(_file(f"q/aa/f{i}.py") for i in range(5)),
    )

    root = _rollup_root(_probes(*probes), depth=12, top=50, max_nodes=12)
    nodes = _nodes_by_path(root)
    assert len(nodes["p/zz"]["children"] or []) == 3
    assert len(nodes["q/aa"]["children"] or []) == 2
    assert _rollup_root(_probes(*reversed(probes)), depth=12, top=50, max_nodes=12) == root


def test_zero_weight_tree_expands_level_by_level() -> None:
    """With no files counted yet every weight is zero, and expansion falls back to levels.

    Path order would expand ``a/x`` before ``b``; level order, which keeps truncation
    honest (``inventory_engine/contract.py``), expands every top-level folder it can first.
    """

    entries = _probes(
        _dir(""),
        *(_dir(name) for name in ("a", "b", "c")),
        *(_dir(f"{name}/x") for name in ("a", "b", "c")),
        *(_dir(f"{name}/x/y") for name in ("a", "b", "c")),
    )

    nodes = _nodes_by_path(_rollup_root(entries, depth=12, top=10, max_nodes=6))
    assert [child["path"] for child in nodes["a"]["children"] or []] == ["a/x"]
    assert [child["path"] for child in nodes["b"]["children"] or []] == ["b/x"]
    assert nodes["c"]["children"] is None
    assert nodes["a/x"]["children"] is None


@pytest.mark.parametrize(
    ("top", "max_nodes"),
    [(0, 1_200), (1, 1_200), (7, 1_200), (200, 1_200), (200, 90), (6_000, 100_000)],
)
def test_selected_children_and_rest_match_a_full_sort(top: int, max_nodes: int) -> None:
    """Selecting the leading children equals sorting every child, on a large directory.

    The reference below sorts both rankings in full, interleaves them, emits up to the
    limit, and sums every omitted child into ``rest``, as emission did before it selected.
    Sizes repeat so that path breaks ties; heavy symlinks lead both rankings, so the
    selection has to reach past them; some folders outweigh every file, so folders are
    emitted beside a ``rest``; and some files and folders are ignored.
    """

    rng = random.Random(20261122)
    probes: list[_RollupProbe] = [_dir("")]
    for i in range(3_000):
        probes.append(_file(f"f{i:04d}.py", rng.choice((0, 1, 2, 3, 5, 8, 13)), ignored=i % 7 == 0))
    for i in range(400):
        folder = f"d{i:03d}"
        probes.append(_dir(folder, ignored=i % 5 == 0))
        probes.extend(
            _file(f"{folder}/g{j}.md", rng.choice((1, 2, 3, 40)), ignored=j == 0 and i % 3 == 0)
            for j in range(rng.randint(0, 4))
        )
    for i in range(40):
        probes.append(_file(f"s{i:02d}", 1_000_000, kind="symlink", ignored=i % 2 == 0))
    entries = _probes(*probes)

    root = _rollup_root(entries, depth=1, top=top, max_nodes=max_nodes)

    children = [probe for probe in entries.values() if probe.parent == "" and probe.path]
    expected_paths, expected_rest = _full_sort_reference(entries, children, min(top, max_nodes - 1))
    assert [child["path"] for child in root["children"]] == expected_paths
    assert root.get("rest") == expected_rest
    # The fixture reaches the case it is for: folders emitted beside a rest.
    if top == 200 and max_nodes == 1_200:
        assert any(child["type"] == "dir" for child in root["children"]) and expected_rest
        assert 0 < expected_rest["dirs"] < 400


def _full_sort_reference(
    entries: dict[str, _RollupProbe],
    children: list[_RollupProbe],
    emit_limit: int,
) -> tuple[list[str], dict[str, int] | None]:
    # Totals of each folder's files: (files, bytes, unignored files, unignored bytes).
    subtree: dict[str, list[int]] = {
        child.path: [0, 0, 0, 0] for child in children if child.type == "dir"
    }
    for probe in entries.values():
        totals = subtree.get(probe.parent)
        if totals is None or probe.type != "file":
            continue
        totals[0] += 1
        totals[1] += probe.size
        if not (entries[probe.parent].gitignored or probe.gitignored):
            totals[2] += 1
            totals[3] += probe.size

    def all_weight(child: _RollupProbe) -> int:
        return subtree[child.path][1] if child.type == "dir" else child.size

    def visible_weight(child: _RollupProbe) -> int:
        if child.type == "dir":
            return subtree[child.path][3]
        return 0 if child.gitignored else child.size

    all_ranked = sorted(children, key=lambda child: (-all_weight(child), child.path))
    visible_ranked = sorted(children, key=lambda child: (-visible_weight(child), child.path))
    ordered: list[_RollupProbe] = []
    seen: set[str] = set()
    for pair in zip(all_ranked, visible_ranked, strict=True):
        for child in pair:
            if child.path not in seen:
                seen.add(child.path)
                ordered.append(child)
    emitted: list[str] = []
    omitted: list[_RollupProbe] = []
    for child in ordered:
        if len(emitted) >= emit_limit:
            omitted.append(child)
        elif child.type in ("dir", "file"):
            emitted.append(child.path)
    if not omitted:
        return emitted, None
    rest = {"dirs": 0, "files": 0, "size": 0, "unignored_files": 0, "unignored_size": 0}
    for child in omitted:
        if child.type == "dir":
            files, size, visible_files, visible_size = subtree[child.path]
            rest["dirs"] += 1
        elif child.type == "file":
            files, size = 1, child.size
            visible_files, visible_size = (0, 0) if child.gitignored else (1, child.size)
        else:
            continue
        rest["files"] += files
        rest["size"] += size
        rest["unignored_files"] += visible_files
        rest["unignored_size"] += visible_size
    return emitted, rest


def test_rollup_options_reject_unknown_ignored_and_encoding() -> None:
    with pytest.raises(ValueError, match="ignored"):
        RollupOptions(depth=0, top=0, ext_top=0, max_nodes=0, ignored=cast(Any, "only"))
    with pytest.raises(ValueError, match="encoding"):
        RollupOptions(depth=0, top=0, ext_top=0, max_nodes=0, encoding=cast(Any, "msgpack"))


def test_budget_share_keeps_a_flat_folder_from_taking_the_budget() -> None:
    """A flat folder first in the order takes its share of the budget, not all of it.

    ``flat`` holds 200 of the 240 files and expands first. With ``top`` as large as the
    budget, the first directory expanded emitted up to the whole budget left, and ``b``
    and ``c`` came back empty-handed. Shared by demand, ``flat`` takes 80 of the 96
    nodes left (200 of the 240 entries waiting), and ``b`` and ``c`` eight each.
    """

    entries = _probes(
        _dir(""),
        _dir("flat"),
        _dir("b"),
        _dir("c"),
        *(_file(f"flat/f{i:03d}.py", 10) for i in range(200)),
        *(_file(f"b/f{i:02d}.py", 10) for i in range(20)),
        *(_file(f"c/f{i:02d}.py", 10) for i in range(20)),
    )

    nodes = _nodes_by_path(_rollup_root(entries, depth=12, top=10_000, max_nodes=100))
    assert len(nodes["flat"]["children"]) == 80
    assert len(nodes["b"]["children"]) == 8
    assert len(nodes["c"]["children"]) == 8
    assert nodes["flat"]["rest"]["files"] == 120
    assert len(nodes) == 100


@pytest.mark.parametrize("ignored", ["include", "exclude"])
def test_a_budget_that_covers_the_tree_emits_all_of_it(ignored: str) -> None:
    """A budget of one node per entry emits every entry, with no ``rest`` anywhere.

    ``exclude`` needs one per unignored entry only, since its ignored ones take none. A
    folder left unexpanded is an empty one the order reached after the budget was spent,
    which costs nothing to leave out.
    """

    entries = _mixed_tree()
    if ignored == "include":
        wanted = {path for path, probe in entries.items() if probe.type in ("dir", "file")}
    else:
        wanted = _visible_paths(entries)
    result = _rollup_result(
        entries, depth=12, top=10_000, max_nodes=len(wanted), ignored=cast(Any, ignored)
    )
    nodes = _nodes_by_path(cast(dict[str, Any], result["node"]))
    assert set(nodes) == wanted
    assert all("rest" not in node for node in nodes.values())
    unexpanded = [path for path, node in nodes.items() if node.get("children", ()) is None]
    assert all(not any(probe.parent == path for probe in entries.values()) for path in unexpanded)


@pytest.mark.parametrize("ignored", ["include", "exclude"])
@pytest.mark.parametrize("depth", [1, 2, 3])
def test_a_budget_that_covers_the_tree_to_its_depth_emits_all_of_it(
    ignored: str, depth: int
) -> None:
    """The same at every depth: a folder's demand on the budget stops at the depth.

    Counting a folder's whole subtree, past the levels the request reaches, gave it a share
    it could never spend and gave the folders expanded before it a smaller one, which left
    them in ``rest`` with the budget unspent.
    """

    entries = _mixed_tree()
    visible = _visible_paths(entries)
    wanted = {
        path
        for path, probe in entries.items()
        if probe.type in ("dir", "file")
        and (path == "" or path.count("/") < depth)
        and (ignored == "include" or path in visible)
    }
    result = _rollup_result(
        entries, depth=depth, top=10_000, max_nodes=len(wanted), ignored=cast(Any, ignored)
    )
    nodes = _nodes_by_path(cast(dict[str, Any], result["node"]))
    assert set(nodes) == wanted
    assert all("rest" not in node for node in nodes.values())


@pytest.mark.parametrize("ignored", ["include", "exclude"])
def test_a_deep_sibling_does_not_starve_a_shallow_one_under_a_depth(ignored: str) -> None:
    """A heavy flat folder expanded first keeps its files when its sibling runs deep.

    ``B``, ten large files, expands before ``A``, whose thousand files lie two levels down,
    past ``depth=2``. Fourteen nodes cover the tree to that depth: the root, ``A``, ``B``,
    ``A/A1``, and ``B``'s ten files.
    """

    entries = _probes(
        _dir(""),
        _dir("A"),
        _dir("A/A1"),
        _dir("B"),
        *(_file(f"A/A1/x{i:04d}.py", 1) for i in range(1000)),
        *(_file(f"B/b{i}.py", 10_000_000) for i in range(10)),
    )
    for max_nodes in (14, 30):
        result = _rollup_result(
            entries, depth=2, top=10_000, max_nodes=max_nodes, ignored=cast(Any, ignored)
        )
        nodes = _nodes_by_path(cast(dict[str, Any], result["node"]))
        assert len(nodes) == 14, max_nodes
        assert "rest" not in nodes["B"]


@pytest.mark.parametrize("max_nodes", [10_000, 40, 7])
def test_exclude_is_the_same_envelope_less_the_ignored_children(max_nodes: int) -> None:
    """``ignored=exclude`` changes the emitted children and ``rest``, and nothing else.

    With a budget that covers the tree, the excluded node tree is the included one less
    every ignored node, children compared by path: ``exclude`` ranks children by their
    unignored weight alone, so the ones left may come in another order. Under any budget, the tallies, the breakdown, and every emitted
    folder's totals, mtime, ignored flag, and ``dominant_ext`` are those of the included
    rollup; ``dominant_ext`` ranks every file beneath the folder, ignored ones too.
    """

    entries = _mixed_tree()
    whole = _rollup_result(entries, depth=12, top=10_000, max_nodes=10_000)
    included = _rollup_result(entries, depth=12, top=10_000, max_nodes=max_nodes)
    excluded = _rollup_result(entries, depth=12, top=10_000, max_nodes=max_nodes, ignored="exclude")
    assert excluded["ext_tallies"] == included["ext_tallies"]
    assert excluded["file_type_breakdown"] == included["file_type_breakdown"]
    whole_nodes = _nodes_by_path(cast(dict[str, Any], whole["node"]))
    excluded_nodes = _nodes_by_path(cast(dict[str, Any], excluded["node"]))
    assert not any(node["gitignored"] for node in excluded_nodes.values())
    for path, node in excluded_nodes.items():
        expected = {k: v for k, v in whole_nodes[path].items() if k not in ("children", "rest")}
        assert {k: v for k, v in node.items() if k not in ("children", "rest")} == expected
    if max_nodes == 10_000:
        assert _by_path(cast(dict[str, Any], excluded["node"])) == _by_path(
            _without_ignored(cast(dict[str, Any], included["node"]))
        )
    # The fixture reaches the case it is for: a folder whose ignored files outweigh its
    # unignored ones, so its dominant extension is one Show ignored off does not draw.
    assert whole_nodes["mixed"]["dominant_ext"] == ".bin"
    assert max_nodes < 10_000 or "mixed" in excluded_nodes


def test_exclude_rest_counts_only_the_unignored_siblings_left_out() -> None:
    """Under ``exclude`` an ignored child is neither emitted nor counted in ``rest``.

    The fully ignored ``ignored_dir`` does not appear among the children and adds no
    ``dirs`` to ``rest``, and the ignored logs, the heaviest children by bytes, add no
    files. ``d1`` keeps its totals (two files, one ignored) and emits its one unignored
    file with no ``rest``: the ignored one is left out, not omitted.
    """

    entries = _probes(
        _dir(""),
        _dir("ignored_dir", ignored=True),
        *(_file(f"ignored_dir/f{i}.py", 100) for i in range(5)),
        *(_file(f"ign{i}.log", 1_000, ignored=True) for i in range(3)),
        _file("f1.py", 50),
        _file("f2.py", 40),
        _file("f3.py", 30),
        _file("f4.py", 20),
        _dir("d1"),
        _file("d1/x.py", 60),
        _file("d1/y.tmp", 70, ignored=True),
        _dir("d2"),
        _file("d2/z.py", 10),
    )

    result = _rollup_result(entries, depth=2, top=2, max_nodes=1_000, ignored="exclude")
    root = cast(dict[str, Any], result["node"])
    assert [child["path"] for child in root["children"]] == ["d1", "f1.py"]
    assert root["rest"] == {
        "dirs": 1,
        "files": 4,
        "size": 100,
        "unignored_files": 4,
        "unignored_size": 100,
    }
    assert (root["total_files"], root["unignored_files"]) == (15, 6)
    d1 = root["children"][0]
    assert (d1["total_files"], d1["unignored_files"]) == (2, 1)
    assert [child["path"] for child in d1["children"]] == ["d1/x.py"]
    assert "rest" not in d1


def test_exclude_under_an_ignored_root_emits_no_children() -> None:
    entries = _probes(_dir("", ignored=True), _dir("a"), _file("a/f.py", 3), _file("g.py", 4))
    root = cast(
        dict[str, Any],
        _rollup_result(entries, depth=12, top=10, max_nodes=100, ignored="exclude")["node"],
    )
    assert root["children"] == []
    assert "rest" not in root
    assert (root["total_files"], root["total_size"], root["gitignored"]) == (2, 7, True)


@pytest.mark.parametrize("root_path", ["", "d01"])
@pytest.mark.parametrize("ignored", ["include", "exclude"])
@pytest.mark.parametrize("omit_mtime", [False, True])
@pytest.mark.parametrize("max_nodes", [10_000, 30])
def test_compact_decodes_to_the_json_tree(
    root_path: str, ignored: str, omit_mtime: bool, max_nodes: int
) -> None:
    """The compact encoding holds the JSON tree: its file rows decode to the file nodes.

    ``_decode_compact`` below decodes by the client's rule; the production decoder,
    ``treemap-rollup-decode.js``, runs against the route in
    ``tests/test_treemap_rollup_decode.py``. A file's path is
    ``dir.path ? dir.path + "/" + name : name``, a null mtime is the JSON's omitted one,
    and ``gitignored`` 0 or 1 is false or true. Folders keep their children as
    folders only, an unexpanded folder has no ``files``, and the budget is spent alike, so
    the decoded tree equals the JSON one, children compared by path.
    """

    entries = _mixed_tree()
    tallies: list[dict[str, Any]] = []
    trees: list[dict[str, Any]] = []
    for encoding in ("json", "compact"):
        result = _rollup_result(
            entries,
            root_path=root_path,
            depth=12,
            top=10_000,
            max_nodes=max_nodes,
            ignored=cast(Any, ignored),
            encoding=cast(Any, encoding),
            omit_mtime=omit_mtime,
        )
        node = cast(dict[str, Any], result["node"])
        validate_rollup_node(cast(Any, node), compact=encoding == "compact")
        tallies.append({k: v for k, v in result.items() if k != "node"})
        trees.append(_by_path(node) if encoding == "json" else _decode_compact(node))
    assert tallies[0] == tallies[1]
    assert trees[1] == trees[0]
    # The fixture reaches the cases it is for: files at the root, a bounded budget that
    # leaves folders unexpanded, and file names the derivation must not mangle.
    decoded = _nodes_by_path(trees[1])
    assert any(child["type"] == "file" for child in trees[1]["children"])
    if max_nodes == 30 and root_path == "":
        assert any(node.get("children", ()) is None for node in decoded.values())
    assert any(" " in node["name"] or "é" in node["name"] for node in decoded.values())


def _mixed_tree() -> dict[str, _RollupProbe]:
    """Nested folders with ignored folders and files, odd names, and a symlink."""

    rng = random.Random(20261123)
    probes: list[_RollupProbe] = [_dir("")]
    for i in range(12):
        folder = f"d{i:02d}"
        probes.append(_dir(folder, ignored=i % 4 == 3))
        for j in range(rng.randint(0, 3)):
            sub = f"{folder}/s{j}"
            probes.append(_dir(sub, ignored=j == 2))
            probes.extend(
                _file(f"{sub}/f{k}.py", rng.choice((1, 5, 40)), ignored=k == 1 and i % 2 == 0)
                for k in range(rng.randint(0, 5))
            )
        probes.extend(
            _file(f"{folder}/{name}", rng.choice((2, 7, 300)), ignored=n == 2)
            for n, name in enumerate(("notes v2.md", "café.txt", "#build.log", "x.tar.gz"))
        )
    probes.extend(_file(f"top{i}.cfg", 3 + i, ignored=i == 1) for i in range(3))
    probes.append(_file("link", 9, kind="symlink"))
    probes.append(_dir("mixed"))
    probes.append(_file("mixed/a.py", 10))
    probes.append(_file("mixed/big.bin", 1_000, ignored=True))
    return _probes(*probes)


def _visible_paths(entries: dict[str, _RollupProbe]) -> set[str]:
    def hidden(path: str) -> bool:
        while True:
            if entries[path].gitignored:
                return True
            if path == "":
                return False
            path = entries[path].parent

    return {
        path
        for path, probe in entries.items()
        if probe.type in ("dir", "file") and (path == "" or not hidden(path))
    }


def _rollup_result(
    entries: dict[str, _RollupProbe],
    *,
    root_path: str = "",
    depth: int,
    top: int,
    max_nodes: int,
    ignored: RollupIgnored = "include",
    encoding: RollupEncoding = "json",
    omit_mtime: bool = False,
) -> dict[str, Any]:
    result = build_rollup(
        entries,
        group_rollup_children(entries),
        root_path,
        RollupOptions(
            depth=depth,
            top=top,
            ext_top=12,
            max_nodes=max_nodes,
            omit_mtime=omit_mtime,
            ignored=ignored,
            encoding=encoding,
        ),
        False,
    )
    assert result is not None
    return cast(dict[str, Any], result)


def _without_ignored(node: dict[str, Any]) -> dict[str, Any]:
    children = node.get("children")
    if not isinstance(children, list):
        return node
    kept = [_without_ignored(child) for child in children if not child["gitignored"]]
    return {**node, "children": kept}


def _by_path(node: dict[str, Any]) -> dict[str, Any]:
    children = node.get("children")
    if not isinstance(children, list):
        return node
    ordered = sorted((_by_path(child) for child in children), key=lambda child: child["path"])
    return {**node, "children": ordered}


def _decode_compact(node: dict[str, Any]) -> dict[str, Any]:
    decoded = {key: value for key, value in node.items() if key not in ("children", "files")}
    children = node["children"]
    if children is None:
        assert "files" not in node
        decoded["children"] = None
        return decoded
    assert all(child["type"] == "dir" for child in children)
    decoded_children = [_decode_compact(child) for child in children]
    for name, size, mtime, ext, gitignored in node["files"]:
        file: dict[str, Any] = {
            "name": name,
            "path": f"{node['path']}/{name}" if node["path"] else name,
            "type": "file",
            "size": size,
        }
        if mtime is not None:
            file["mtime"] = mtime
        file["ext"] = ext
        file["gitignored"] = gitignored == 1
        decoded_children.append(file)
    decoded["children"] = sorted(decoded_children, key=lambda child: child["path"])
    return decoded


def _dir(path: str, *, ignored: bool = False) -> _RollupProbe:
    parent, _, name = path.rpartition("/")
    return _RollupProbe(path, parent, name or "root", "dir", "", 0, 1, ignored, 1)


def _file(path: str, size: int = 1, *, ignored: bool = False, kind: str = "file") -> _RollupProbe:
    parent, _, name = path.rpartition("/")
    dot = name.rfind(".")
    ext = name[dot:] if dot > 0 else ""
    return _RollupProbe(path, parent, name, kind, ext, size, 1, ignored, None)


def _probes(*probes: _RollupProbe) -> dict[str, _RollupProbe]:
    return {probe.path: probe for probe in probes}


def _rollup_root(
    entries: dict[str, _RollupProbe], *, depth: int, top: int, max_nodes: int
) -> dict[str, Any]:
    result = build_rollup(
        entries,
        group_rollup_children(entries),
        "",
        RollupOptions(depth=depth, top=top, ext_top=0, max_nodes=max_nodes),
        False,
    )
    assert result is not None
    return cast(dict[str, Any], result["node"])


def _nodes_by_path(root: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {node["path"]: node for node in _walk(root)}


def _walk(node: dict[str, Any]) -> Iterator[dict[str, Any]]:
    yield node
    for child in node.get("children") or []:
        yield from _walk(child)
