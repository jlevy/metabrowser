"""Verified repair must retire actors that can still read an unlinked corrupt pack."""

from __future__ import annotations

import asyncio
import hashlib
import struct
import subprocess
import zlib
from contextlib import AsyncExitStack
from pathlib import Path
from unittest.mock import Mock

import pytest

from metabrowser.cache.acquire import PublishedSource
from metabrowser.cache.object_recovery import recover_comparison_objects
from metabrowser.git import tree_source as tree
from metabrowser.git.object_failures import observed_object_failures
from metabrowser.git.process import repository_store_target
from tests.git_pin_harness import fast_import_store, git_env
from tests.required_tools import needs_git

pytestmark = needs_git


def _git(store: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "--git-dir", str(store), *args],
        check=True,
        capture_output=True,
        env=git_env(store.parent),
    ).stdout


def _pack(store: Path, objects: list[tuple[str, str, bytes]]) -> Path:
    """Build valid pack/index framing with deliberately chosen object names."""
    packed = b"PACK" + struct.pack(">II", 2, len(objects))
    entries: list[tuple[str, int, int]] = []
    kinds = {"commit": 1, "tree": 2, "blob": 3, "tag": 4}
    for oid, kind, body in objects:
        size = len(body)
        first = kinds[kind] << 4 | (size & 15)
        size >>= 4
        header = bytearray([first | (128 if size else 0)])
        while size:
            byte = size & 127
            size >>= 7
            header.append(byte | (128 if size else 0))
        framed = bytes(header) + zlib.compress(body)
        entries.append((oid, zlib.crc32(framed), len(packed)))
        packed += framed
    pack_hash = hashlib.sha1(packed).digest()
    entries.sort()
    index = b"\xfftOc" + struct.pack(">I", 2)
    index += b"".join(
        struct.pack(">I", sum(int(oid[:2], 16) <= byte for oid, _, _ in entries))
        for byte in range(256)
    )
    index += b"".join(bytes.fromhex(oid) for oid, _, _ in entries)
    index += b"".join(struct.pack(">I", crc) for _, crc, _ in entries)
    index += b"".join(struct.pack(">I", offset) for _, _, offset in entries)
    index += pack_hash
    prefix = store / "objects" / "pack" / f"pack-{pack_hash.hex()}"
    prefix.with_suffix(".pack").write_bytes(packed + pack_hash)
    prefix.with_suffix(".idx").write_bytes(index + hashlib.sha1(index).digest())
    return prefix


@pytest.mark.parametrize("active_lease", [False, True], ids=["idle", "checked-out"])
def test_repair_retires_every_actor_holding_a_corrupt_unlinked_pack(
    tmp_path: Path, active_lease: bool
) -> None:
    genuine, forged, anchor = b"genuine target\n", b"forgery target\n", b"unchanged anchor\n"
    store, commit = fast_import_store(tmp_path, {b"target.txt": genuine, b"anchor.txt": anchor})
    oid = _git(store, "rev-parse", f"{commit}:target.txt").decode().strip()
    anchor_oid = _git(store, "rev-parse", f"{commit}:anchor.txt").decode().strip()
    objects: list[tuple[str, str, bytes]] = []
    for line in (
        _git(store, "cat-file", "--batch-all-objects", "--batch-check=%(objectname) %(objecttype)")
        .decode()
        .splitlines()
    ):
        name, kind = line.split()
        objects.append((name, kind, _git(store, "cat-file", kind, name)))
    for path in (store / "objects" / "pack").iterdir():
        path.unlink()
    for name, _, _ in objects:
        (store / "objects" / name[:2] / name[2:]).unlink(missing_ok=True)
    corrupt_pack = _pack(
        store, [(name, kind, forged if name == oid else body) for name, kind, body in objects]
    )
    assert _git(store, "cat-file", "blob", oid) == forged
    target = repository_store_target(git_dir=store)

    async def run() -> None:
        source = tree.GitTreeSource(target=target, root_tree_oid="0" * 40)
        try:
            async with AsyncExitStack() as leases:
                retained = await leases.enter_async_context(source._pool.checkout())
                assert await retained.read_blob(anchor_oid, max_blob_bytes=1024) == anchor
                with pytest.raises(tree.GitObjectCorruptError) as failure:
                    await tree.read_store_blob(target, oid)
                observed_object_failures.remember(target, (commit,), failure.value)
                old_process = retained._proc
                assert old_process is not None
                if not active_lease:
                    await leases.aclose()
                corrupt_pack.with_suffix(".pack").unlink()
                corrupt_pack.with_suffix(".idx").unlink()
                _pack(store, objects)
                published = Mock(spec=PublishedSource, git_dir=store)
                assert len(await recover_comparison_objects(published, (commit,))) == 1
                assert not observed_object_failures.pending(target, (commit,))
                if active_lease:
                    assert old_process.returncode is None, (
                        "repair killed an exclusively leased actor"
                    )
                    assert await retained.read_blob(anchor_oid, max_blob_bytes=1024) == anchor
                await leases.aclose()
                for _ in range(4):
                    assert await tree.read_store_blob(target, oid) == genuine
                assert old_process.returncode is not None, "the obsolete process was not reaped"
        finally:
            await source.aclose()

    asyncio.run(run())


def test_recycling_a_fully_leased_pool_releases_waiters_without_interrupting_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tree, "MAX_BATCH_READERS_PER_STORE", 1)
    store, commit = fast_import_store(tmp_path, {b"file": b"readable\n"})
    oid = _git(store, "rev-parse", f"{commit}:file").decode().strip()
    target = repository_store_target(git_dir=store)

    async def run() -> None:
        source = tree.GitTreeSource(target=target, root_tree_oid="0" * 40)
        try:
            async with source._pool.checkout() as leased:
                assert await leased.read_blob(oid, max_blob_bytes=1024) == b"readable\n"
                old = leased._proc
                assert old is not None
                waiting = asyncio.create_task(tree.read_store_blob(target, oid))
                await asyncio.sleep(0)
                assert not waiting.done()
                await tree.recycle_store_readers(target)
                assert not waiting.done() and old.returncode is None
                assert await leased.read_blob(oid, max_blob_bytes=1024) == b"readable\n"
            assert await asyncio.wait_for(waiting, 5) == b"readable\n"
            assert old.returncode is not None
            assert source._pool._available.qsize() == 1
        finally:
            await source.aclose()

    asyncio.run(run())


@pytest.mark.parametrize("readers", [1, 2])
def test_cancelled_recycling_keeps_the_pool_slot_stale_and_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, readers: int
) -> None:
    monkeypatch.setattr(tree, "MAX_BATCH_READERS_PER_STORE", readers)
    store, commit = fast_import_store(tmp_path, {b"file": b"readable\n"})
    oid = _git(store, "rev-parse", f"{commit}:file").decode().strip()
    target = repository_store_target(git_dir=store)

    async def run() -> None:
        source = tree.GitTreeSource(target=target, root_tree_oid="0" * 40)
        try:
            async with AsyncExitStack() as held:
                for _ in range(readers):
                    actor = await held.enter_async_context(source._pool.checkout())
                    assert await actor.read_blob(oid, max_blob_bytes=1024) == b"readable\n"
            entered = asyncio.Event()
            reader = source._pool._readers[-1]
            old = reader._proc
            assert old is not None
            poison = tree._BatchObjectReader._poison

            async def paused(actor: tree._BatchObjectReader) -> None:
                if actor is reader:
                    entered.set()
                    await asyncio.Event().wait()
                await poison(actor)

            monkeypatch.setattr(tree._BatchObjectReader, "_poison", paused)
            recycling = asyncio.create_task(tree.recycle_store_readers(target))
            await entered.wait()
            recycling.cancel()
            with pytest.raises(asyncio.CancelledError):
                await recycling
            monkeypatch.setattr(tree._BatchObjectReader, "_poison", poison)
            assert source._pool._available.qsize() == readers
            for _ in range(readers):
                assert await asyncio.wait_for(tree.read_store_blob(target, oid), 5) == b"readable\n"
            assert old.returncode is not None
            assert len(source._pool._readers) == source._pool._available.qsize() == readers
        finally:
            await source.aclose()

    asyncio.run(run())
