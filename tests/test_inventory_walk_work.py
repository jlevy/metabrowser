"""Deterministic work meters for the inventory walk and the passes that overlap it.

The engine performance model's rule is that nothing goes on the per-entry path without
a measured reason, and its discipline is counts before times. These tests hold the
counts: how many path validations, record conversions, and copies a discovered entry
costs; how much Python a catalog pass spends per entry it visits; and how many entries
a worker pass takes between cooperative yields. None of them reads a clock, so a busy
host can neither fail nor pass them.

Each bound fails on the v0.10.0 release candidate that exp-033 rejected, whose 300,000
file walk was 1.13-1.49 times slower than v0.9.1 without a browser and whose progress
polls missed their budget while a tally ran. The per-entry costs behind each bound are
recorded beside the code that pays them.
"""

from __future__ import annotations

import asyncio
import functools
import sys
import time
from collections.abc import AsyncIterator, Callable, Iterator, Sequence
from dataclasses import replace
from itertools import pairwise
from pathlib import Path
from types import FrameType
from typing import Any, overload

import pytest

from metabrowser import walker
from metabrowser.active_tracker import _SCOPED_DIRS
from metabrowser.activity import TRACKABLE_FILE_MAX_SIZE
from metabrowser.events import CatalogChange, FsChange, FsResyncRequired, FsUpsert
from metabrowser.file_extensions import BROWSER_TRACKABLE_EXTS
from metabrowser.fs_record import FsEntry
from metabrowser.inventory_engine import contract
from metabrowser.inventory_engine.contract import (
    CatalogProjection,
    CatalogQuery,
    ChangeBatch,
    EntryPresence,
    EntryProjection,
    EntryQuery,
    LifecyclePhase,
    NavigationQuery,
    ReadRequest,
    ReadResult,
)
from metabrowser.inventory_engine.coordinator import InventoryCoordinator
from metabrowser.inventory_engine.providers import python_inventory as python_provider
from metabrowser.inventory_engine.providers.python_inventory import (
    _PythonInventoryStore as PythonInventoryStore,
)
from metabrowser.inventory_engine.runtime import default_inventory_config
from metabrowser.walker import WALKER_EMIT_BATCH
from tests.inventory_harness import inventory_harness

DIRECTORIES = 6
FILES_PER_DIRECTORY = 200


class _CallCounter:
    """Wrap a function or method and count the calls that reach it."""

    def __init__(self, target: Callable[..., Any]) -> None:
        self._target = target
        self.calls = 0

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls += 1
        return self._target(*args, **kwargs)

    def __get__(self, instance: object, owner: type | None = None) -> Callable[..., Any]:
        # Installed on a class, bind like the function it replaces.
        if instance is None:
            return self
        return functools.partial(self, instance)


def _count(monkeypatch: pytest.MonkeyPatch, owner: object, name: str) -> _CallCounter:
    counter = _CallCounter(getattr(owner, name))
    monkeypatch.setattr(owner, name, counter)
    return counter


class _MergeRevalidations:
    """Count the dirty paths the coordinator revalidates by merging several batches.

    Batches that queue up while the coordinator is busy are merged into one, and the
    merged batch validates its paths again. How many queue up is a scheduling fact, so
    the bounds below credit exactly those revalidations instead of guessing a margin;
    a lone batch, which is almost every batch in a walk, must pass through unrebuilt.
    """

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.paths = 0
        real_merge = InventoryCoordinator._merge_provider_batches

        def counting_merge(batches: tuple[ChangeBatch, ...]) -> ChangeBatch:
            merged = real_merge(batches)
            if len(batches) > 1:
                self.paths += len(merged.dirty_paths)
            return merged

        monkeypatch.setattr(
            InventoryCoordinator, "_merge_provider_batches", staticmethod(counting_merge)
        )


def _build_tree(root: Path) -> set[str]:
    files: set[str] = set()
    for directory_index in range(DIRECTORIES):
        directory = root / f"dir{directory_index:02d}"
        directory.mkdir()
        for file_index in range(FILES_PER_DIRECTORY):
            name = f"file{file_index:04d}.txt"
            (directory / name).write_bytes(b"x")
            files.add(f"dir{directory_index:02d}/{name}")
    return files


def _quiet_config() -> contract.InventoryConfig:
    # No watcher: nothing but the walk may produce an observation.
    return replace(default_inventory_config(), watch_mode="off")


def _gate_walk(monkeypatch: pytest.MonkeyPatch) -> Callable[[], asyncio.Event]:
    """Hold discovery until a test has attached, so every entry takes the measured path."""

    gates: list[asyncio.Event] = []
    real_walk_tree = python_provider.walk_tree

    async def gated_walk_tree(*args: Any, **kwargs: Any) -> AsyncIterator[FsEntry]:
        gate = gates[0]
        await gate.wait()
        async for entry in real_walk_tree(*args, **kwargs):
            yield entry

    monkeypatch.setattr(python_provider, "walk_tree", gated_walk_tree)

    def make_gate() -> asyncio.Event:
        gate = asyncio.Event()
        gates.append(gate)
        return gate

    return make_gate


async def _wait_until_delivered(harness: Any) -> None:
    """Wait for the walk to settle and for the event bus to project its last change."""

    handle = harness.runtime.coordinator._handle
    await handle.wait_until_done(timeout=60)
    for _ in range(6_000):
        cursor, _version, state = await harness.runtime.coordinator.checkpoint()
        settled = state.phase in {LifecyclePhase.READY, LifecyclePhase.WATCHING}
        if settled and harness.bus._after == cursor:
            return
        await asyncio.sleep(0.01)
    pytest.fail("the event bus never projected the walk's final change")


def test_discovery_validates_each_path_once_and_converts_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With nobody reading, a discovered entry is one record and one path validation.

    The walker builds the retained record directly and copies it positionally, so no
    contract entry is built and converted back, and `dataclasses.replace` runs once per
    directory finalization rather than once per entry. The single validation is the
    provider's change batch. The coordinator used to rebuild every batch it received
    alone -- almost all of them during a walk -- and validate its paths a second time.
    """

    files = _build_tree(tmp_path)
    make_gate = _gate_walk(monkeypatch)
    validations = _count(monkeypatch, contract, "require_canonical_inventory_path")
    walker_replaces = _count(monkeypatch, walker, "replace")
    provider_replaces = _count(monkeypatch, python_provider, "replace")
    conversions = _count(monkeypatch, python_provider, "_semantic_entry")
    stored = _count(monkeypatch, PythonInventoryStore, "_store_walker_entry")
    merges = _MergeRevalidations(monkeypatch)

    async def run() -> None:
        gate = make_gate()
        async with inventory_harness(tmp_path, config=_quiet_config(), settle=False) as harness:
            validations.calls = 0
            merges.paths = 0
            gate.set()
            await _wait_until_delivered(harness)

    asyncio.run(run())

    assert stored.calls >= len(files) + DIRECTORIES, "the walk must store every entry"
    assert conversions.calls == 0, (
        f"discovery converted {conversions.calls} retained records to contract entries "
        "with no reader attached"
    )
    assert walker_replaces.calls <= DIRECTORIES + 1, (
        f"the walker ran dataclasses.replace {walker_replaces.calls} times for "
        f"{DIRECTORIES + 1} directories"
    )
    assert provider_replaces.calls == 0
    # One validation per stored entry, plus whatever the coordinator revalidated by
    # merging batches that happened to queue up together.
    assert validations.calls <= stored.calls + merges.paths, (
        f"discovery validated {validations.calls} paths for {stored.calls} stored entries "
        f"({merges.paths} revalidated by merges); a path is validated once, when the "
        "provider's change batch is built"
    )


def test_attached_walk_projects_each_entry_with_one_validation_per_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A browser attached during a walk rereads every entry; each reread is linear.

    Projection builds three validated records per discovered path -- the change batch,
    the entry query, and the contract entry -- and each validates its path once. The
    contract entry used to validate its parent too, although the identity check already
    proves it, and the coordinator revalidated lone batches, for five per entry.

    The bus also looked each projection up with `ReadResult.completed_projection`, a
    scan of the result, once per dirty path, which made every change quadratic in its
    size. It now indexes the result once per change.
    """

    files = _build_tree(tmp_path)
    make_gate = _gate_walk(monkeypatch)
    validations = _count(monkeypatch, contract, "require_canonical_inventory_path")
    stored = _count(monkeypatch, PythonInventoryStore, "_store_walker_entry")
    lookups = _count(monkeypatch, ReadResult, "projection")
    merges = _MergeRevalidations(monkeypatch)
    delivered_files: set[str] = set()

    async def run() -> None:
        gate = make_gate()
        async with inventory_harness(tmp_path, config=_quiet_config(), settle=False) as harness:
            _snapshot, queue = await harness.bus.snapshot_and_attach("root-depth-2")
            lookups.calls = 0

            async def drain() -> None:
                while True:
                    envelope = await queue.get()
                    event = envelope.event
                    if isinstance(event, FsResyncRequired):
                        pytest.fail(f"the attached connection was reset: {event.reason}")
                    if isinstance(event, CatalogChange):
                        delivered_files.update(upsert.p for upsert in event.upserts)
                    elif isinstance(event, FsChange):
                        for op in event.ops:
                            if isinstance(op, FsUpsert) and op.entry.type == "file":
                                delivered_files.add(op.entry.path)
                    queue.task_done()

            drainer = asyncio.create_task(drain())
            validations.calls = 0
            merges.paths = 0
            gate.set()
            try:
                await _wait_until_delivered(harness)
                await queue.join()
            finally:
                drainer.cancel()

    asyncio.run(run())

    assert delivered_files == files, "the connection must receive every discovered file"
    # Three validations per stored entry, plus merge revalidations, plus up to two emit
    # batches of rereads whose number depends on when the connection's snapshot and the
    # final catalog refresh land (measured at about 20 paths). The regression this holds
    # back, five validations per entry, adds two per stored entry: 2,428 here.
    assert validations.calls <= 3 * stored.calls + merges.paths + 2 * WALKER_EMIT_BATCH, (
        f"an attached walk validated {validations.calls} paths for {stored.calls} stored "
        f"entries ({merges.paths} revalidated by merges); projection validates each path "
        "once per record it builds, three in all"
    )
    assert lookups.calls <= 32, (
        f"the bus made {lookups.calls} projection lookups for {stored.calls} stored "
        "entries; a change is indexed once, not scanned once per dirty path"
    )


def _activity_query() -> CatalogQuery:
    """The activity tracker's candidate query, which it issues every five seconds."""

    return CatalogQuery(
        query_id="activity-candidates",
        max_rows=500_000,
        include_ignored=True,
        terminal_extensions=tuple(sorted(BROWSER_TRACKABLE_EXTS)),
        ancestor_names=tuple(sorted(_SCOPED_DIRS)),
        size_less_than=TRACKABLE_FILE_MAX_SIZE,
    )


_CORPUS_EXTENSIONS = (".py", ".md", ".json", ".txt", ".yaml", ".csv", ".log", ".png")


def _store_with_files(files: int) -> PythonInventoryStore:
    store = PythonInventoryStore()
    for index in range(files):
        parent = f"top{index % 12:02d}/leaf{index % 8:02d}"
        name = f"file{index:05d}{_CORPUS_EXTENSIONS[index % len(_CORPUS_EXTENSIONS)]}"
        store._replace_index_entry(
            FsEntry.for_observed_file(
                path=f"{parent}/{name}",
                parent=parent,
                name=name,
                size=64,
                mtime_ns=1,
            )
        )
    return store


# Python calls the tracker's catalog pass may spend per entry it visits. The compiled
# predicate costs about five: the predicate, the terminal-suffix rule and its fold, and
# the ancestor split for the entries whose suffix matched. Rebuilding the wanted-suffix
# set inside the predicate cost more than thirty.
MAX_CATALOG_CALLS_PER_ENTRY = 10


def test_activity_catalog_pass_does_bounded_work_per_entry() -> None:
    """The tracker's catalog pass visits every entry, so its per-entry cost is the pass.

    A profile hook counts every Python and builtin call the read makes. The count is
    per entry, independent of the host, and it is what separated this pass from v0.9.1's
    filter: the same answer at several times the calls.
    """

    files = 4_096
    store = _store_with_files(files)
    request = ReadRequest(queries=(_activity_query(),))
    calls = 0

    def profile(_frame: FrameType, event: str, _arg: object) -> None:
        nonlocal calls
        if event in ("call", "c_call"):
            calls += 1

    previous_profile = sys.getprofile()
    sys.setprofile(profile)
    try:
        result = store._read_sync(request)
    finally:
        sys.setprofile(previous_profile)

    projection = result.projection("activity-candidates")
    assert isinstance(projection, CatalogProjection)
    assert projection.records == (), "no synthetic file is inside a scoped directory"
    per_entry = calls / files
    assert per_entry <= MAX_CATALOG_CALLS_PER_ENTRY, (
        f"the activity catalog pass made {per_entry:.1f} calls per entry "
        f"(limit {MAX_CATALOG_CALLS_PER_ENTRY}); compile its predicates once per query"
    )


class _PassCountingEntries(Sequence[FsEntry]):
    """An image's entries that record each full pass and how far the current one got."""

    def __init__(self, entries: Sequence[FsEntry]) -> None:
        self._entries = tuple(entries)
        self.passes = 0
        self.taken = 0

    def __len__(self) -> int:
        return len(self._entries)

    @overload
    def __getitem__(self, index: int) -> FsEntry: ...

    @overload
    def __getitem__(self, index: slice) -> Sequence[FsEntry]: ...

    def __getitem__(self, index: int | slice) -> FsEntry | Sequence[FsEntry]:
        return self._entries[index]

    def __iter__(self) -> Iterator[FsEntry]:
        self.passes += 1
        self.taken = 0
        for entry in self._entries:
            self.taken += 1
            yield entry


def _count_image_passes(
    monkeypatch: pytest.MonkeyPatch,
    store: PythonInventoryStore,
) -> list[_PassCountingEntries]:
    images: list[_PassCountingEntries] = []
    real_capture = store._capture_image

    def capture(request: ReadRequest) -> Any:
        image = real_capture(request)
        counted = _PassCountingEntries(image.entries)
        images.append(counted)
        return replace(image, entries=counted)

    monkeypatch.setattr(store, "_capture_image", capture)
    return images


# The most catalog-pass entries a waiting event-loop iteration can queue behind. It
# restates `_CATALOG_COOPERATIVE_YIELD_BATCH`, where the measurement behind it is
# recorded, so raising that constant fails here until someone re-measures.
MAX_CATALOG_ENTRIES_BETWEEN_YIELDS = 1_024


def test_catalog_pass_cooperatively_yields_to_the_event_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A whole-index pass on a worker must release the GIL on its own cadence.

    Without a yield the pass is served by the interpreter's forced switch, and every
    event-loop iteration -- the walker's and each request's -- waits up to the 5 ms
    switch interval for as long as the pass runs. The activity tracker runs this pass
    every five seconds through the initial walk. A profile hook notes how many entries
    the pass had taken at each timer-backed sleep; the run between sleeps is the bound.
    """

    files = 5_000
    store = _store_with_files(files)
    images = _count_image_passes(monkeypatch, store)
    yields_after: list[int] = []

    def profile(_frame: FrameType, event: str, arg: object) -> None:
        if event == "c_call" and arg is time.sleep and images:
            # The entry being taken when the pass yields is not yet processed.
            yields_after.append(images[-1].taken - 1)

    previous_profile = sys.getprofile()
    sys.setprofile(profile)
    try:
        store._read_sync(ReadRequest(queries=(_activity_query(),)))
    finally:
        sys.setprofile(previous_profile)

    assert images and images[-1].taken == files, "the pass must visit every entry"
    boundaries = [0, *yields_after, files]
    longest_run = max(later - earlier for earlier, later in pairwise(boundaries))
    assert longest_run <= MAX_CATALOG_ENTRIES_BETWEEN_YIELDS, (
        f"the catalog pass took {longest_run} entries without releasing the GIL "
        f"(limit {MAX_CATALOG_ENTRIES_BETWEEN_YIELDS}; it yielded {len(yields_after)} times "
        f"over {files} entries)"
    )


def test_root_navigation_read_passes_over_the_index_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The root tree request bundles its entry with the tallies; only the tallies scan.

    Answering the root entry used to index every entry by path first -- a second pass
    over the whole index, with no cooperative yield, before the tally pass that does
    yield -- and every root tally refresh during a walk paid it.
    """

    store = _store_with_files(2_000)
    store._replace_index_entry(FsEntry.for_observed_dir(path="top00", parent="", name="top00"))
    images = _count_image_passes(monkeypatch, store)
    request = ReadRequest(
        queries=(
            EntryQuery(query_id="tree-parent", path="top00"),
            NavigationQuery(query_id="tree-navigation", max_rows=200),
        )
    )

    result = store._read_snapshot_sync(request)

    parent = result.projection("tree-parent")
    assert isinstance(parent, EntryProjection)
    assert parent.presence is EntryPresence.PRESENT, "the entry lookup must still find the entry"
    assert parent.entry is not None and parent.entry.path == "top00"
    assert len(images) == 1
    assert images[0].passes == 1, (
        f"a root navigation read made {images[0].passes} passes over the index; "
        "only the tally pass needs one"
    )


@pytest.mark.parametrize("parent", [None, b"", 0, False])
def test_root_entry_rejects_a_falsy_parent_that_is_not_the_root(parent: object) -> None:
    """The root's parent is the root spelling itself, not any falsy value.

    `InventoryEntry` no longer validates `parent` separately, because a non-root
    entry's identity check already pins it to the path's prefix. The root has no
    prefix, so its parent must be compared with `""` directly.
    """

    with pytest.raises(ValueError, match="root entry must have the root as its parent"):
        contract.InventoryEntry(
            path="",
            parent=parent,  # pyright: ignore[reportArgumentType]
            name="",
            type=contract.EntryType.DIRECTORY,
            ext="",
            size=0,
            mtime_ns=0,
        )
