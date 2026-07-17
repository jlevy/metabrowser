"""Direct unit coverage for the generic mtime-keyed LRU cache.

The cache was previously exercised only indirectly through the projection
tests; the three-outcome ``CacheRead`` discriminator (hit / miss / absent)
and the invalidation rules deserve their own file.
"""

from __future__ import annotations

import os
from pathlib import Path

from metabrowser.mtime_cache import MtimeCache


def _write(path: Path, text: str, mtime_ns: int) -> None:
    path.write_text(text)
    os.utime(path, ns=(mtime_ns, mtime_ns))


def test_miss_then_update_then_hit(tmp_path: Path) -> None:
    cache: MtimeCache[dict[str, int]] = MtimeCache(8, name="test")
    target = tmp_path / "value.json"
    _write(target, "{}", 1_000_000_000)

    first = cache.read(target)
    assert not first.hit
    assert not first.absent
    assert first.value is None

    cache.update(target, {"n": 1})
    second = cache.read(target)
    assert second.hit
    assert second.value == {"n": 1}


def test_hit_returns_independent_copy(tmp_path: Path) -> None:
    cache: MtimeCache[dict[str, list[int]]] = MtimeCache(8, name="test")
    target = tmp_path / "value.json"
    _write(target, "{}", 1_000_000_000)

    cache.update(target, {"items": [1]})
    first = cache.read(target)
    assert first.value is not None
    first.value["items"].append(2)

    second = cache.read(target)
    assert second.value == {"items": [1]}


def test_mtime_change_invalidates(tmp_path: Path) -> None:
    cache: MtimeCache[str] = MtimeCache(8, name="test")
    target = tmp_path / "value.txt"
    _write(target, "one", 1_000_000_000)
    cache.update(target, "derived-one")
    assert cache.read(target).hit

    _write(target, "two!", 2_000_000_000)
    stale = cache.read(target)
    assert not stale.hit
    assert not stale.absent


def test_missing_file_reports_absent_and_drops_entry(tmp_path: Path) -> None:
    cache: MtimeCache[str] = MtimeCache(8, name="test")
    target = tmp_path / "value.txt"
    _write(target, "one", 1_000_000_000)
    cache.update(target, "derived")
    assert cache.read(target).hit

    target.unlink()
    gone = cache.read(target)
    assert gone.absent
    assert gone.value is None

    # A later re-create with different content must not resurrect the
    # deleted entry's value: it reads as an ordinary miss.
    _write(target, "reborn", 3_000_000_000)
    fresh = cache.read(target)
    assert not fresh.hit
    assert not fresh.absent


def test_delete_removes_entry(tmp_path: Path) -> None:
    cache: MtimeCache[str] = MtimeCache(8, name="test")
    target = tmp_path / "value.txt"
    _write(target, "one", 1_000_000_000)
    cache.update(target, "derived")
    cache.delete(target)
    assert not cache.read(target).hit
