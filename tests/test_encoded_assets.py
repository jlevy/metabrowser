"""The application's own assets at a current stamped address, held and compressed once (H115).

A hit sends what is held and does no work; the bound is in bytes over both encodings;
an edited file has a new key and its old bytes are not served for it; and a client gets
the bytes and headers the middleware would have given it.
"""

from __future__ import annotations

import asyncio
import contextlib
import gzip
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import cast

import pytest
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Mount, Route
from starlette.testclient import TestClient
from starlette.types import Message, Scope

from metabrowser import (
    asset_stamps,
    delivery,
    encoded_assets,
    kpress_adapter,
    server,
    server_timing,
)
from metabrowser.asset_stamps import StampedStaticFiles, StampedTree, content_digest
from metabrowser.encoded_assets import AssetChanged, EncodedAssetResponse, EncodedAssets
from tests.test_server_timing import _metrics  # pyright: ignore[reportPrivateUsage]

GZIP = {"accept-encoding": "gzip, deflate, br, zstd"}


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> EncodedAssets:
    """A fresh store in place of the process's, so each test starts with nothing held."""
    fresh = EncodedAssets()
    monkeypatch.setattr(encoded_assets, "ENCODED_ASSETS", fresh)
    return fresh


@pytest.fixture
def compressions(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[int]]:
    """The size of every body the store compresses."""
    seen: list[int] = []
    original = delivery.gzip_bytes

    def counted(content: bytes) -> bytes:
        seen.append(len(content))
        return original(content)

    monkeypatch.setattr(delivery, "gzip_bytes", counted)
    yield seen


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    server._set_root_dir(tmp_path)  # pyright: ignore[reportPrivateUsage]
    server.prepare_asset_stamps()
    return TestClient(server.app)


def _stamped_static(name: str) -> tuple[str, bytes]:
    stamp = server._STATIC_TREE.stamp()  # pyright: ignore[reportPrivateUsage]
    assert stamp is not None
    return f"/static/{name}?v={stamp.digests[name]}", (server.STATIC_DIR / name).read_bytes()


def test_a_stamped_asset_is_read_and_compressed_once_and_then_sent_from_memory(
    client: TestClient, store: EncodedAssets, compressions: list[int]
) -> None:
    address, content = _stamped_static("app.js")
    first = client.get(address, headers=GZIP)
    second = client.get(address, headers=GZIP)
    for answer in (first, second):
        assert answer.status_code == 200
        assert answer.headers["content-encoding"] == "gzip"
        assert answer.headers["vary"] == "Accept-Encoding"
        assert answer.headers["cache-control"] == "public, max-age=31536000, immutable"
        assert answer.content == content
        assert int(answer.headers["content-length"]) == answer.num_bytes_downloaded
    assert compressions == [len(content)], "compressed once, for the first request"
    # The first request paid the read and the compression; the second paid neither.
    assert {"read", "encode"} <= set(_metrics(first.headers["server-timing"]))
    assert not {"read", "encode"} & set(_metrics(second.headers["server-timing"]))
    assert store.holds(address.rsplit("=", 1)[1], "gzip")


def test_what_a_client_receives_is_what_the_middleware_sent(
    client: TestClient, store: EncodedAssets
) -> None:
    address, content = _stamped_static("app.js")
    held = client.get(address, headers=GZIP)
    # The same file at an unstamped address is streamed and compressed per request.
    streamed = client.get("/static/app.js", headers=GZIP)
    assert held.content == streamed.content == content
    assert held.num_bytes_downloaded == len(delivery.gzip_bytes(content))
    assert held.num_bytes_downloaded == streamed.num_bytes_downloaded
    for name in ("content-type", "etag", "last-modified", "accept-ranges", "vary"):
        assert held.headers[name] == streamed.headers[name], name
    assert gzip.decompress(delivery.gzip_bytes(content)) == content


def test_an_identity_client_and_a_small_asset_are_sent_as_they_are(
    client: TestClient, store: EncodedAssets, compressions: list[int]
) -> None:
    address, content = _stamped_static("app.js")
    plain = client.get(address, headers={"accept-encoding": "identity"})
    assert "content-encoding" not in plain.headers
    assert plain.content == content
    assert plain.num_bytes_downloaded == len(content)
    # The middleware adds Vary to an answer it could have compressed, as before.
    assert plain.headers["vary"] == "Accept-Encoding"
    assert compressions == []


def test_an_asset_under_the_floor_is_sent_as_it_is(
    tmp_path: Path, store: EncodedAssets, compressions: list[int]
) -> None:
    (tmp_path / "small.js").write_text("small();\n")
    app, tree = _live_app(tmp_path)
    stamp = tree.stamp()
    assert stamp is not None
    tiny = TestClient(app).get(f"/static/small.js?v={stamp.digests['small.js']}", headers=GZIP)
    assert tiny.status_code == 200
    assert tiny.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert "content-encoding" not in tiny.headers and "vary" not in tiny.headers
    assert tiny.text == "small();\n"
    assert compressions == []


def test_a_head_a_range_and_a_revalidation_keep_their_answers(
    client: TestClient, store: EncodedAssets, compressions: list[int]
) -> None:
    address, content = _stamped_static("app.js")
    head = client.head(address, headers=GZIP)
    # A HEAD is the file response's, as before: the identity length, nothing read or held.
    assert head.status_code == 200 and head.content == b""
    assert int(head.headers["content-length"]) == len(content)
    assert "content-encoding" not in head.headers
    assert compressions == [] and store.held_bytes == 0
    ranged = client.get(address, headers={**GZIP, "range": "bytes=0-9"})
    assert ranged.status_code == 206
    etag = head.headers["etag"]
    revalidated = client.get(address, headers={**GZIP, "if-none-match": etag})
    assert revalidated.status_code == 304
    assert revalidated.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_an_old_stamp_is_revalidated_and_read_from_disk(
    client: TestClient, store: EncodedAssets, compressions: list[int]
) -> None:
    _address, content = _stamped_static("app.js")
    stale = client.get(f"/static/app.js?v={'0' * 32}", headers=GZIP)
    assert stale.headers["cache-control"] == "no-cache"
    assert stale.content == content
    assert compressions == [], "only an immutable answer is held"


def test_a_plugin_asset_and_a_kpress_asset_are_held_once(
    client: TestClient, store: EncodedAssets, compressions: list[int]
) -> None:
    tree = server._PLUGIN_ASSET_TREES["markdown"]  # pyright: ignore[reportPrivateUsage]
    stamp = tree.stamp()
    assert stamp is not None
    plugin = f"/plugin-static/markdown/@{stamp.digest}/rendered.js"
    kpress = kpress_adapter.kpress_asset_url_prefix() + "css/style-tokens.css"
    assert "@" in kpress, "the KPress tree is stamped"
    for address in (plugin, kpress):
        first = client.get(address, headers=GZIP)
        second = client.get(address, headers=GZIP)
        assert first.status_code == second.status_code == 200, address
        assert first.headers["content-encoding"] == "gzip", address
        assert first.headers["cache-control"] == "public, max-age=31536000, immutable"
        assert first.content == second.content
        assert not {"encode"} & set(_metrics(second.headers["server-timing"])), address
    assert len(compressions) == 2
    assert client.get(plugin, headers=GZIP).content == (tree.root / "rendered.js").read_bytes()


def test_the_bound_is_in_bytes_over_both_encodings() -> None:
    async def run() -> None:
        bounded = EncodedAssets(max_bytes=10_000)
        one = b"a" * 6000
        two = bytes(range(256)) * 20  # 5,120 bytes that barely compress
        await bounded.identity("one", lambda: one)
        assert bounded.held_bytes == 6000
        await bounded.gzipped("one", one)
        assert bounded.held_bytes == 6000 + len(delivery.gzip_bytes(one))
        await bounded.identity("two", lambda: two)
        assert bounded.held_bytes <= 10_000
        assert bounded.holds("two", "identity")
        assert not bounded.holds("one", "identity"), "the least recently used goes first"
        # Heavier than the bound: sent, not held.
        assert await bounded.identity("big", lambda: b"b" * 10_001) == b"b" * 10_001
        assert not bounded.holds("big", "identity")
        assert bounded.held_bytes <= 10_000

    asyncio.run(run())


def _live_app(root: Path) -> tuple[Starlette, StampedTree]:
    tree = StampedTree(root, live=True)
    app = Starlette(
        routes=[Mount("/static", app=StampedStaticFiles(directory=root, tree=tree))],
        middleware=[
            Middleware(
                server_timing.TimedGZipMiddleware,
                minimum_size=delivery.GZIP_MINIMUM_SIZE,
                compresslevel=delivery.GZIP_LEVEL,
            )
        ],
    )
    return app, tree


def test_an_edit_in_a_live_tree_is_a_new_key_and_the_old_bytes_are_never_sent_for_it(
    tmp_path: Path, store: EncodedAssets
) -> None:
    asset = tmp_path / "a.js"
    asset.write_text("one();\n" * 400)
    app, tree = _live_app(tmp_path)
    client = TestClient(app)
    before = tree.stamp()
    assert before is not None
    old = before.digests["a.js"]
    assert client.get(f"/static/a.js?v={old}", headers=GZIP).text == "one();\n" * 400
    assert store.holds(old, "gzip")

    asset.write_text("two();\n" * 400)
    # The address the old page asks with is no longer current: the file is read again.
    stale = client.get(f"/static/a.js?v={old}", headers=GZIP)
    assert stale.headers["cache-control"] == "no-cache"
    assert stale.text == "two();\n" * 400
    # The next page's stamp names the new bytes, which are held under their own key.
    after = tree.stamp()
    assert after is not None
    new = after.digests["a.js"]
    assert new != old
    fresh = client.get(f"/static/a.js?v={new}", headers=GZIP)
    assert fresh.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert fresh.text == "two();\n" * 400
    assert store.holds(new, "gzip")


def test_bytes_that_changed_after_their_stamp_are_sent_revalidated_and_not_held(
    tmp_path: Path, store: EncodedAssets
) -> None:
    body = b"changed(); " * 400

    def load() -> bytes:
        raise AssetChanged(body)

    async def answer(_request: Request) -> Response:
        return EncodedAssetResponse(
            key="named",
            load=load,
            headers={"cache-control": "public, max-age=31536000, immutable"},
            media_type="text/javascript",
        )

    app = Starlette(
        routes=[Route("/x", answer)],
        middleware=[Middleware(server_timing.TimedGZipMiddleware, minimum_size=1024)],
    )
    sent = TestClient(app).get("/x", headers=GZIP)
    assert sent.headers["cache-control"] == "no-cache"
    assert sent.content == body
    assert sent.headers["content-encoding"] == "gzip", "the middleware compressed it"
    assert not store.holds("named", "identity")


def test_a_file_loader_refuses_bytes_its_digest_does_not_name(tmp_path: Path) -> None:
    path = tmp_path / "a.js"
    path.write_bytes(b"a")
    assert encoded_assets.file_loader(path, content_digest(b"a"), content_digest)() == b"a"
    with pytest.raises(AssetChanged):
        encoded_assets.file_loader(path, content_digest(b"b"), content_digest)()


def test_an_asset_given_its_bytes_reads_nothing_and_has_them_as_its_body(
    store: EncodedAssets, compressions: list[int]
) -> None:
    body = b"kpress(); " * 400

    async def answer(_request: Request) -> Response:
        return EncodedAssetResponse(
            key="given", identity=body, headers={}, media_type="text/javascript"
        )

    made = EncodedAssetResponse(key="given", identity=body, headers={}, media_type=None)
    assert made.body == body, "a caller that reads the response's body sees the bytes"
    app = Starlette(
        routes=[Route("/x", answer)],
        middleware=[Middleware(server_timing.TimedGZipMiddleware, minimum_size=1024)],
    )
    sent = TestClient(app).get("/x", headers=GZIP)
    assert sent.headers["content-encoding"] == "gzip" and sent.content == body
    assert compressions == [len(body)]
    assert not store.holds("given", "identity")
    with pytest.raises(ValueError, match="its bytes or a way to read them"):
        EncodedAssetResponse(
            key="both", identity=body, load=lambda: body, headers={}, media_type=None
        )


# Concurrency at the route, over raw ASGI against the application, middleware and all
# (review C of #455, C4): the store's single flight is tested on LoadingCache itself, and
# these hold that the routes share it as the store says.


async def _asgi_get(path: str, headers: dict[str, str]) -> tuple[int | None, dict[str, str], bytes]:
    """GET *path* from ``server.app`` as a client elsewhere: status, headers, raw body."""
    route, _, query = path.partition("?")
    scope: Scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": route,
        "raw_path": route.encode(),
        "query_string": query.encode(),
        "root_path": "",
        "headers": [
            (b"host", b"127.0.0.1"),
            *((name.encode(), value.encode()) for name, value in headers.items()),
        ],
        "client": ("192.0.2.1", 50000),
        "server": ("127.0.0.1", 8411),
    }
    asked = False

    async def receive() -> Message:
        nonlocal asked
        if not asked:
            asked = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    status: int | None = None
    sent_headers: dict[str, str] = {}
    body = bytearray()

    async def send(message: Message) -> None:
        nonlocal status
        if message["type"] == "http.response.start":
            status = cast("int", message["status"])
            for name, value in cast("list[tuple[bytes, bytes]]", message.get("headers", [])):
                sent_headers[name.decode("latin-1").lower()] = value.decode("latin-1")
        elif message["type"] == "http.response.body":
            body.extend(cast("bytes", message.get("body", b"")))

    with contextlib.suppress(RuntimeError):
        # A failed load is answered 500 by the error middleware, which then raises again.
        await server.app(scope, receive, send)
    return status, sent_headers, bytes(body)


def _gated_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[list[str], threading.Event, threading.Event]:
    """Count the /static route's reads; each waits for the returned *release* to be set."""
    reads: list[str] = []
    started = threading.Event()
    release = threading.Event()
    original = encoded_assets.file_loader  # what asset_stamps imported

    def gated(path: Path, digest: str, digest_of: Callable[[bytes], str]) -> Callable[[], bytes]:
        load = original(path, digest, digest_of)

        def read() -> bytes:
            reads.append(digest)
            started.set()
            assert release.wait(30), "the test never released the read"
            return load()

        return read

    monkeypatch.setattr(asset_stamps, "file_loader", gated)
    return reads, started, release


def _joined(monkeypatch: pytest.MonkeyPatch, store: EncodedAssets, method: str) -> list[str]:
    """The keys every caller of the store's *method* asked for, as each one arrives."""
    callers: list[str] = []
    original = getattr(store, method)

    async def counted(key: str, *args: object) -> bytes:
        callers.append(key)
        return cast("bytes", await original(key, *args))

    monkeypatch.setattr(store, method, counted)
    return callers


async def _until(condition: Callable[[], bool]) -> None:
    deadline = time.monotonic() + 30
    while not condition():
        assert time.monotonic() < deadline, "the requests never reached the store"
        await asyncio.sleep(0.001)


def test_concurrent_first_requests_share_one_read_and_one_compression(
    client: TestClient,
    store: EncodedAssets,
    compressions: list[int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reads, _started, release = _gated_reads(monkeypatch)
    release.set()
    address, content = _stamped_static("app.js")

    async def land() -> list[tuple[int | None, dict[str, str], bytes]]:
        return await asyncio.gather(*(_asgi_get(address, GZIP) for _ in range(20)))

    answers = asyncio.run(land())
    assert [status for status, _, _ in answers] == [200] * 20
    assert {gzip.decompress(body) for _, _, body in answers} == {content}
    assert len({body for _, _, body in answers}) == 1, "one encoding, sent to every client"
    assert len(reads) == 1 and compressions == [len(content)]
    timings = [set(_metrics(headers["server-timing"])) for _, headers, _ in answers]
    assert sum("read" in names for names in timings) == 1, "only the request that read says so"
    assert sum("encode" in names for names in timings) == 1


def test_a_cancelled_first_request_leaves_its_load_to_the_others(
    client: TestClient,
    store: EncodedAssets,
    compressions: list[int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reads, started, release = _gated_reads(monkeypatch)
    arrived = _joined(monkeypatch, store, "identity")
    address, content = _stamped_static("app.js")
    key = address.rsplit("=", 1)[1]

    async def land() -> list[tuple[int | None, dict[str, str], bytes]]:
        first = asyncio.create_task(_asgi_get(address, GZIP))
        await _until(started.is_set)
        others = [asyncio.create_task(_asgi_get(address, GZIP)) for _ in range(3)]
        await _until(lambda: len(arrived) == 4)
        first.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await first
        release.set()
        return await asyncio.gather(*others)

    answers = asyncio.run(land())
    assert [status for status, _, _ in answers] == [200] * 3
    assert {gzip.decompress(body) for _, _, body in answers} == {content}
    assert len(reads) == 1
    assert store.holds(key, "identity") and store.holds(key, "gzip")


def test_a_failed_compression_fails_its_waiters_keeps_nothing_and_is_tried_again(
    client: TestClient, store: EncodedAssets, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = threading.Event()
    release = threading.Event()
    original = delivery.gzip_bytes
    attempts: list[int] = []

    def fails_once(content: bytes) -> bytes:
        attempts.append(len(content))
        if len(attempts) == 1:
            started.set()
            assert release.wait(30), "the test never released the compression"
            raise RuntimeError("compression failed")
        return original(content)

    monkeypatch.setattr(delivery, "gzip_bytes", fails_once)
    arrived = _joined(monkeypatch, store, "gzipped")
    address, content = _stamped_static("app.js")
    key = address.rsplit("=", 1)[1]

    async def land() -> list[tuple[int | None, dict[str, str], bytes]]:
        waiting = [asyncio.create_task(_asgi_get(address, GZIP)) for _ in range(2)]
        await _until(lambda: started.is_set() and len(arrived) == 2)
        release.set()
        return await asyncio.gather(*waiting)

    failed = asyncio.run(land())
    assert [status for status, _, _ in failed] == [500, 500], "both waiters share the failure"
    assert store.holds(key, "identity") and not store.holds(key, "gzip")
    status, headers, body = asyncio.run(_asgi_get(address, GZIP))
    assert status == 200 and headers["content-encoding"] == "gzip"
    assert gzip.decompress(body) == content
    assert len(attempts) == 2 and store.holds(key, "gzip")


def test_a_load_every_waiter_left_still_finishes_and_is_kept(
    client: TestClient, store: EncodedAssets, monkeypatch: pytest.MonkeyPatch
) -> None:
    reads, started, release = _gated_reads(monkeypatch)
    address, content = _stamped_static("app.js")
    key = address.rsplit("=", 1)[1]

    async def land() -> None:
        alone = asyncio.create_task(_asgi_get(address, GZIP))
        await _until(started.is_set)
        alone.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await alone
        release.set()
        await _until(lambda: store.holds(key, "identity"))

    asyncio.run(land())
    assert len(reads) == 1 and store.held_bytes == len(content)
