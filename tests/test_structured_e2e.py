"""End-to-end test for the structured plugin's sidekick endpoint.

Boots a Starlette TestClient with the built-in structured plugin
mounted, drops a small JSON file under ROOT_DIR, and hits
``GET /api/plugin/structured/parsed?path=<rel>``. Asserts the
response envelope shape + the parsed payload + the canonical YAML
re-serialization.
"""

from __future__ import annotations

import gzip
import json
import os
import zlib
from pathlib import Path
from typing import Any

import pytest
from cachetools import LRUCache
from starlette.applications import Starlette
from starlette.testclient import TestClient

import metabrowser.builtin_plugins.structured as structured_sidekick
import metabrowser.builtin_plugins.structured.parser as structured_parser
from metabrowser import paths_safe
from metabrowser import server as proc_browser  # noqa: F401  # pyright: ignore[reportUnusedImport]
from metabrowser.gz_io import ARTIFACT_MAX_COMPRESSED_BYTES
from metabrowser.plugin_loader.discovery import _try_load_plugin
from metabrowser.plugin_loader.static_assets import build_plugin_routes

_STRUCTURED_DIR = (
    Path(__file__).resolve().parents[1] / "src" / "metabrowser" / "builtin_plugins" / "structured"
)


@pytest.fixture
def structured_app(tmp_path: Path) -> TestClient:
    paths_safe._set_root_dir(tmp_path)
    plugin = _try_load_plugin(_STRUCTURED_DIR, source="builtin:test")
    assert plugin is not None and not isinstance(plugin, str), plugin
    routes = build_plugin_routes([plugin])
    app = Starlette(routes=routes)
    return TestClient(app)


def test_parsed_endpoint_round_trips_json(tmp_path: Path, structured_app: TestClient) -> None:
    f = tmp_path / "bundle%20.json"
    f.write_text(json.dumps({"spec": "Demo/0.1", "n": 3, "items": ["a", "b"]}))
    resp = structured_app.get("/api/plugin/structured/parsed", params={"path": "bundle%2520.json"})
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["type"] == "structured"
    assert payload["path"] == "bundle%2520.json"
    assert payload["ext"] == ".json"
    assert payload["parse_error"] is None
    assert payload["truncated"] is False
    assert payload["comments_supported"] is False
    assert payload["parsed"] == {"spec": "Demo/0.1", "n": 3, "items": ["a", "b"]}
    assert "pretty_yaml" in payload
    assert payload["pretty_yaml"].strip() != ""
    assert payload["node_count"] >= 3
    assert payload["mtime_hash"]


def test_parsed_endpoint_surfaces_parse_error(tmp_path: Path, structured_app: TestClient) -> None:
    f = tmp_path / "bad.json"
    f.write_text("{not valid json")
    resp = structured_app.get("/api/plugin/structured/parsed", params={"path": "bad.json"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["parse_error"] is not None
    assert payload["parsed"] is None


def test_parsed_endpoint_404_for_unknown_path(structured_app: TestClient) -> None:
    resp = structured_app.get("/api/plugin/structured/parsed", params={"path": "nope.json"})
    assert resp.status_code == 404


def test_parsed_endpoint_400_for_wrong_ext(tmp_path: Path, structured_app: TestClient) -> None:
    f = tmp_path / "note.md"
    f.write_text("# hello")
    resp = structured_app.get("/api/plugin/structured/parsed", params={"path": "note.md"})
    assert resp.status_code == 400


def test_parsed_endpoint_etag_header(tmp_path: Path, structured_app: TestClient) -> None:
    f = tmp_path / "x.yaml"
    f.write_text("a: 1\nb: 2\n")
    resp = structured_app.get("/api/plugin/structured/parsed", params={"path": "x.yaml"})
    assert resp.status_code == 200
    assert resp.headers["ETag"]


def test_parsed_endpoint_handles_gzipped_json(tmp_path: Path, structured_app: TestClient) -> None:
    """``foo.json.gz`` should classify on its logical extension (``.json``)
    and decompress transparently. Caught a real bug pre-test where
    target.suffix.lower() == ".gz" 400'd otherwise-valid files."""

    f = tmp_path / "bundle.json.gz"
    payload = json.dumps({"compressed": True, "n": 7}).encode()
    with gzip.open(f, "wb") as fh:
        fh.write(payload)
    resp = structured_app.get("/api/plugin/structured/parsed", params={"path": "bundle.json.gz"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ext"] == ".json"
    assert body["parsed"] == {"compressed": True, "n": 7}
    assert body["parse_error"] is None


def test_parsed_endpoint_handles_zlib_json(tmp_path: Path, structured_app: TestClient) -> None:
    source = tmp_path / "bundle.json.zlib"
    source.write_bytes(zlib.compress(json.dumps({"compressed": "zlib", "n": 8}).encode()))

    response = structured_app.get("/api/plugin/structured/parsed", params={"path": source.name})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ext"] == ".json"
    assert body["parsed"] == {"compressed": "zlib", "n": 8}
    assert body["parse_error"] is None


def test_parsed_endpoint_reports_the_stored_size_and_truncation_past_the_cap(
    tmp_path: Path, structured_app: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``size`` is the file's size on disk, and ``truncated`` says the cap was passed.

    ``size`` is not what was read or parsed: for a compressed file it is the
    compressed size, as ``/api/file`` reports it, and past the cap it is still the
    whole file's, not the cap. v0.11.0 answered it this way, and an answer taken from
    the bounded read gave 22 for the 40-byte ``small.json.gz`` and 1000 for a file
    over a 1000-byte cap.

    Past the cap the route answers ``truncated`` with nothing parsed, which is what
    sends the Tree view to Source. A compressed file is over the cap by what it
    decodes to, whatever it weighs on disk.
    """

    cap = 1000
    monkeypatch.setattr(structured_sidekick, "STRUCTURED_PARSE_MAX_BYTES", cap)
    monkeypatch.setattr(structured_parser, "STRUCTURED_PARSE_MAX_BYTES", cap)
    small = json.dumps({"a": 1, "b": [2, 3]}).encode()
    big = json.dumps({"x": "y" * (2 * cap)}).encode()
    (tmp_path / "small.json").write_bytes(small)
    (tmp_path / "small.json.gz").write_bytes(gzip.compress(small))
    (tmp_path / "big.json").write_bytes(big)
    (tmp_path / "big.json.gz").write_bytes(gzip.compress(big))
    on_disk = {name: (tmp_path / name).stat().st_size for name in sorted(os.listdir(tmp_path))}
    # The fixture separates the three quantities a wrong `size` could be taken from.
    assert on_disk["small.json.gz"] != len(small)
    assert on_disk["big.json"] > cap > on_disk["big.json.gz"]

    def parsed(name: str) -> dict[str, Any]:
        response = structured_app.get("/api/plugin/structured/parsed", params={"path": name})
        assert response.status_code == 200, response.text
        return response.json()

    for name in ("small.json", "small.json.gz"):
        body = parsed(name)
        assert body["size"] == on_disk[name], name
        assert body["truncated"] is False, name
        assert body["parsed"] == {"a": 1, "b": [2, 3]}, name
    for name in ("big.json", "big.json.gz"):
        body = parsed(name)
        assert body["size"] == on_disk[name], name
        assert body["truncated"] is True, name
        assert (body["parsed"], body["pretty_yaml"], body["parse_error"]) == (None, "", None), name
        assert (body["node_count"], body["max_depth"]) == (0, 0), name
    # A second request is answered from the payload cache, and says the same.
    assert [parsed(name)["size"] for name in on_disk] == list(on_disk.values())


def _parsed(app: TestClient, name: str) -> dict[str, Any]:
    response = app.get("/api/plugin/structured/parsed", params={"path": name})
    assert response.status_code == 200, response.text
    assert response.headers["ETag"]
    return response.json()


def test_parsed_endpoint_answers_a_changed_file_afresh(
    tmp_path: Path, structured_app: TestClient
) -> None:
    """A rewritten file is parsed again: the payload cache is keyed on its fingerprint."""

    target = tmp_path / "mut.json"
    target.write_bytes(b'{"v": 1}')
    first = structured_app.get("/api/plugin/structured/parsed", params={"path": "mut.json"})
    assert (first.json()["parsed"], first.json()["size"]) == ({"v": 1}, 8)

    # A different size, and then the same size with only the modification time moved.
    target.write_bytes(b'{"v": 2, "more": [1, 2, 3]}')
    grown = structured_app.get("/api/plugin/structured/parsed", params={"path": "mut.json"})
    assert (grown.json()["parsed"], grown.json()["size"]) == ({"v": 2, "more": [1, 2, 3]}, 27)

    target.write_bytes(b'{"v": 3, "more": [4, 5, 6]}')
    stamp = target.stat().st_mtime_ns + 5_000_000_000
    os.utime(target, ns=(stamp, stamp))
    same_size = structured_app.get("/api/plugin/structured/parsed", params={"path": "mut.json"})
    assert (same_size.json()["parsed"], same_size.json()["size"]) == (
        {"v": 3, "more": [4, 5, 6]},
        27,
    )

    answers = (first, grown, same_size)
    assert len({answer.json()["mtime_hash"] for answer in answers}) == 3
    assert len({answer.headers["ETag"] for answer in answers}) == 3


@pytest.mark.parametrize("size", [0, -1])
def test_parsed_endpoint_parses_every_request_when_the_cache_holds_nothing(
    size: int, tmp_path: Path, structured_app: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``STRUCTURED_CACHE_SIZE`` of zero or less caches nothing, and is not an error.

    That is how 0.11.0's ``functools.lru_cache`` read the setting. A cachetools cache
    of that size refuses every store, and the route answered the degraded
    ``plugin_error`` envelope for every structured file.
    """

    # The variable is read once at import, into a cache of exactly that size.
    assert structured_parser._PAYLOAD_CACHE.maxsize == structured_parser.STRUCTURED_CACHE_SIZE
    cache: LRUCache[Any, Any] = LRUCache(maxsize=size)
    monkeypatch.setattr(structured_parser, "_PAYLOAD_CACHE", cache)
    (tmp_path / "data.json").write_bytes(b'{"a": 1, "b": [2, 3]}')

    for _ in range(2):
        response = structured_app.get("/api/plugin/structured/parsed", params={"path": "data.json"})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["type"] == "structured", body
        assert (body["parsed"], body["parse_error"]) == ({"a": 1, "b": [2, 3]}, None)
        assert response.headers["ETag"]
    assert len(cache) == 0


def test_parsed_endpoint_reads_bytes_as_a_text_mode_open_does(
    tmp_path: Path, structured_app: TestClient
) -> None:
    """Bytes that are not UTF-8 are replaced and the rest parsed; CRLF and CR read as LF.

    That is how 0.11.0 read a file, through a text-mode open that replaces what it
    cannot decode. A Latin-1 file therefore opens as a tree with U+FFFD where the
    byte was. Decoding strictly answered ``parse_error: "UnicodeDecodeError: ..."``
    for it, which sends the reader to Source for a file that used to open. The
    expected values are 0.11.0's own answers for these bytes.
    """

    latin1_json = '{"a": "calf\xe9"}'.encode("latin-1")
    (tmp_path / "latin1.json").write_bytes(latin1_json)
    (tmp_path / "latin1.json.gz").write_bytes(gzip.compress(latin1_json))
    (tmp_path / "latin1.json.zlib").write_bytes(zlib.compress(latin1_json))
    (tmp_path / "latin1.yaml").write_bytes("a: calf\xe9\n".encode("latin-1"))
    for name in ("latin1.json", "latin1.json.gz", "latin1.json.zlib", "latin1.yaml"):
        body = _parsed(structured_app, name)
        assert (body["parsed"], body["parse_error"]) == ({"a": "calf\ufffd"}, None), name
        assert body["pretty_yaml"] == "a: calf\ufffd\n", name

    # An encoded lone surrogate is three undecodable bytes; a byte order mark is kept
    # and the JSON5 fallback reads past it.
    (tmp_path / "surrogate.json").write_bytes(b'{"a": "\xed\xa0\x80"}')
    assert _parsed(structured_app, "surrogate.json")["parsed"] == {"a": "\ufffd\ufffd\ufffd"}
    (tmp_path / "bom.json").write_bytes(b'\xef\xbb\xbf{"a": 1}')
    assert _parsed(structured_app, "bom.json")["parsed"] == {"a": 1}

    # What cannot parse says why in the parser's words, counted in lines as an editor
    # shows them: a lone CR and a CRLF each end a line.
    errors = {
        "utf16.json": ('{"a": 1}'.encode("utf-16"), 'ValueError: <string>:1 Unexpected "\ufffd"'),
        "cut.json": (b'{"a": "calf\xc3', "ValueError: <string>:1 Unexpected end of input"),
        "cr.json": (b'{\r  "a": \r}\r', 'ValueError: <string>:3 Unexpected "}" at column 1'),
        "crlf.json": (
            b'{\r\n  "a": 1,\r\n  "b": \r\n}\r\n',
            'ValueError: <string>:4 Unexpected "}" at column 1',
        ),
        "cr-in.json": (b'{"a": "x\ry"}', 'ValueError: <string>:1 Unexpected "\n" at column 9'),
    }
    for name, (content, reason) in errors.items():
        (tmp_path / name).write_bytes(content)
        body = _parsed(structured_app, name)
        assert body["parsed"] is None, name
        assert body["parse_error"].startswith(reason), (name, body["parse_error"])
        assert body["truncated"] is False, name


def test_parsed_endpoint_answers_a_compressed_file_it_cannot_decode_as_a_parse_error(
    tmp_path: Path, structured_app: TestClient
) -> None:
    """A corrupt, cut-off or mislabelled compressed file is there, and says what is wrong.

    0.11.0 answered 200 with the decompression failure as ``parse_error``, an ETag and
    the file's size, so the Tree view fell back to Source with the reason. Passing the
    content reader's own error through answered 422 ``content_unreadable`` with no
    envelope.
    """

    whole = gzip.compress(json.dumps({"a": 1, "b": [1, 2, 3]}).encode())
    files = {
        "corrupt.json.gz": (b"\x1f\x8b\x08\x00garbagegarbage", "invalid gzip stream: "),
        "cut.json.gz": (whole[:-6], "invalid gzip stream: "),
        "plain.json.gz": (b'{"a": 1}', "invalid gzip stream: "),
        "plain.yaml.gz": (b"a: 1\n", "invalid gzip stream: "),
        "corrupt.json.zlib": (b"\x78\x9cgarbage", "invalid zlib stream: "),
    }
    for name, (content, reason) in files.items():
        (tmp_path / name).write_bytes(content)
        body = _parsed(structured_app, name)
        assert body["size"] == len(content), name
        assert body["parse_error"].startswith(f"ArtifactCompressionError: {reason}"), name
        assert (body["parsed"], body["pretty_yaml"], body["truncated"]) == (None, "", False), name
        # No path on the host is part of the reason.
        assert str(tmp_path) not in body["parse_error"], name


def test_parsed_endpoint_answers_truncated_for_a_compressed_file_past_a_resource_bound(
    tmp_path: Path, structured_app: TestClient
) -> None:
    """A compressed file the reader refuses for a resource bound is too large, not broken.

    The file is sparse, one byte past the bound on compressed input, so the reader
    refuses it when it opens it and nothing is read.
    """

    target = tmp_path / "huge.json.gz"
    target.touch()
    os.truncate(target, ARTIFACT_MAX_COMPRESSED_BYTES + 1)

    body = _parsed(structured_app, "huge.json.gz")

    assert (body["truncated"], body["parsed"], body["parse_error"]) == (True, None, None)
    assert body["size"] == ARTIFACT_MAX_COMPRESSED_BYTES + 1


@pytest.mark.parametrize("cap", [-1, -2, -5000])
def test_parsed_endpoint_answers_truncated_for_every_file_under_a_negative_cap(
    cap: int, tmp_path: Path, structured_app: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``STRUCTURED_PARSE_MAX_BYTES`` below zero: nothing fits, so nothing is read.

    0.11.0 compared a file's size with the cap before opening it, and every size is
    past a negative cap, an empty file's too, so each answered ``truncated`` and the
    Tree view fell back to Source. The read refuses a negative bound, and the route
    answered the degraded ``plugin_error`` envelope for every structured file.

    A file that cannot be opened is not opened, so it is ``truncated`` as well. A
    compressed file is too: 0.11.0 answered it ``parse_error: "ValueError:
    decompressed output bound must be positive"``, which is its reader refusing the
    bound and is not restored.
    """

    monkeypatch.setattr(structured_sidekick, "STRUCTURED_PARSE_MAX_BYTES", cap)
    monkeypatch.setattr(structured_parser, "_PAYLOAD_CACHE", LRUCache(maxsize=8))
    files = {
        "small.json": b'{"a": 1}\n',
        "empty.json": b"",
        "config.yaml": b"a: 1\n",
        "empty.yaml": b"",
        "small.json.gz": gzip.compress(b'{"a": 1}\n'),
        "locked.json": b'{"a": 1}\n',
    }
    for name, content in files.items():
        (tmp_path / name).write_bytes(content)
    (tmp_path / "locked.json").chmod(0)

    for name in files:
        response = structured_app.get("/api/plugin/structured/parsed", params={"path": name})
        assert response.status_code == 200, (name, response.text)
        body = response.json()
        assert body["type"] == "structured", (name, body)
        assert (body["truncated"], body["parsed"], body["parse_error"]) == (True, None, None), name
        assert (body["pretty_yaml"], body["node_count"], body["max_depth"]) == ("", 0, 0), name
        assert body["size"] == (tmp_path / name).stat().st_size, name
        assert response.headers["ETag"], name

    # A file that is not there, and one the plugin does not parse, answer as at any cap.
    missing = structured_app.get("/api/plugin/structured/parsed", params={"path": "absent.json"})
    assert missing.status_code == 404
    (tmp_path / "note.md").write_bytes(b"# hello\n")
    wrong = structured_app.get("/api/plugin/structured/parsed", params={"path": "note.md"})
    assert wrong.status_code == 400


def test_parsed_endpoint_names_no_host_path_for_a_file_it_cannot_open(
    tmp_path: Path, structured_app: TestClient
) -> None:
    """A file without read permission answers 404, and the answer names the served path.

    0.11.0 answered 200 with ``parse_error: "PermissionError: [Errno 13] Permission
    denied: '<absolute path>'"``, which is the one answer of this route that is not
    restored.
    """

    target = tmp_path / "locked.json"
    target.write_bytes(b'{"a": 1}')
    target.chmod(0)
    if os.access(target, os.R_OK):
        # A superuser reads it anyway; there is nothing to refuse.
        return

    response = structured_app.get("/api/plugin/structured/parsed", params={"path": "locked.json"})

    assert response.status_code == 404
    assert response.json() == {
        "error": "locked.json",
        "code": "content_unavailable",
        "path": "locked.json",
    }
    assert str(tmp_path) not in response.text
