"""A plugin's file view offered only where its predicate accepts the file's leading bytes.

The structured kind offers Table, Tree, and Source for every JSON or YAML file.
The offer tests add a predicate to Table to pin how file routes handle optional views.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from metabrowser import server
from metabrowser.builtin_plugins.structured.offer import offers_table
from metabrowser.plugin_loader.classify import CONTENT_PREDICATE_MAX_BYTES
from tests.required_tools import needs_git

_MAPPING = b'{"name": "metabrowser", "version": 1}'
_RECORDS = b'[{"name": "Ada"}, {"name": "Grace"}]'


@pytest.fixture
def record_view_offer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(server._FILE_OFFERS, ("structured", "table"), offers_table)
    monkeypatch.setattr(server, "_FILE_OFFER_KINDS", server._FILE_OFFER_KINDS | {"structured"})


def _ids(views: list[dict[str, Any]]) -> list[str]:
    return [view["id"] for view in views]


def _api_file(path: str) -> dict[str, Any]:
    request = Mock(spec=["query_params", "headers"])
    request.query_params = {"path": path}
    request.headers = {}
    response = asyncio.run(server.api_file(request))
    return json.loads(bytes(response.body))


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("people.json", _RECORDS),
        ("people.yaml", b"- name: Ada\n- name: Grace\n"),
        ("config.json", _MAPPING),
        ("config.yaml", b"name: metabrowser\n"),
    ],
)
def test_json_and_yaml_files_offer_the_same_views(
    tmp_path: Path, name: str, content: bytes
) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / name).write_bytes(content)
    body = _api_file(name)
    assert (body["kind"], _ids(body["views"])) == ("structured", ["table", "tree", "source"])
    assert [view["id"] for view in body["views"] if view["default"]] == ["table"]


@pytest.mark.usefixtures("record_view_offer")
def test_the_predicate_reads_a_bounded_prefix_and_the_logical_extension(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[tuple[int, str]] = []

    def record(prefix: bytes, ext: str) -> bool:
        seen.append((len(prefix), ext))
        return True

    big = tmp_path / "big.json"
    big.write_bytes(b"[" + b" " * (2 * CONTENT_PREDICATE_MAX_BYTES) + b"]")
    monkeypatch.setitem(server._FILE_OFFERS, ("structured", "table"), record)

    ids = _ids(server._views_for_kind("structured", target=big))

    assert ids == ["table", "tree", "source"]
    assert seen == [(CONTENT_PREDICATE_MAX_BYTES + 1, ".json")]


@pytest.mark.usefixtures("record_view_offer")
def test_a_prefix_in_hand_is_read_instead_of_the_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """A pinned blob's route holds its leading bytes and passes them."""
    seen: list[tuple[bytes, str]] = []

    def record(prefix: bytes, ext: str) -> bool:
        seen.append((prefix, ext))
        return False

    monkeypatch.setitem(server._FILE_OFFERS, ("structured", "table"), record)

    ids = _ids(server._views_for_kind("structured", prefix=(_RECORDS, ".yaml")))

    assert ids == ["tree", "source"]
    assert seen == [(_RECORDS, ".yaml")]


@needs_git
@pytest.mark.usefixtures("record_view_offer")
@pytest.mark.parametrize("ceiling", [None, 16], ids=["whole", "windowed"])
def test_a_pinned_blob_offers_from_its_leading_bytes(tmp_path: Path, ceiling: int | None) -> None:
    """A pin evaluates an offer from the whole blob or its bounded leading bytes."""
    from metabrowser.git.tree_source import GitPath
    from tests.git_pin_harness import fast_import_store
    from tests.test_git_revision_content_routes import _pinned_client

    store, commit = fast_import_store(tmp_path, {b"rows.json": _RECORDS, b"meta.json": _MAPPING})
    assert len(_RECORDS) > 16 and len(_MAPPING) > 16

    async def views(name: bytes) -> list[str]:
        async with _pinned_client(store, commit, max_blob_bytes=ceiling) as (client, _subject):
            path = GitPath.from_segments(name).to_wire()
            answer = (await client.get("/api/file", params={"path": path})).json()
            return _ids(answer["views"])

    assert asyncio.run(views(b"rows.json")) == ["table", "tree", "source"]
    assert asyncio.run(views(b"meta.json")) == ["tree", "source"]


def test_an_offer_on_a_kind_not_served_as_text_is_never_kept_and_said_once(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """An image, a binary, a JSONL log, or a container's entry reads no leading bytes, so
    its kind's offered view is left out, and the plugin's author is told once."""

    monkeypatch.setitem(server._FILE_OFFERS, ("binary", "bytes"), lambda _p, _e: True)
    monkeypatch.setattr(server, "_FILE_OFFER_KINDS", server._FILE_OFFER_KINDS | {"binary"})
    server._warn_offers_never_read.cache_clear()

    with caplog.at_level(logging.WARNING, logger=server.LOG.name):
        first = _ids(server._views_for_kind("binary"))
        again = _ids(server._views_for_kind("binary"))

    assert (first, again) == ([], [])
    warnings = [r for r in caplog.records if "never offered" in r.getMessage()]
    assert [r.getMessage() for r in warnings] == [
        "binary views declare an offer, but a binary file is not served as text, so no "
        "leading bytes are read and those views are never offered"
    ]
    server._warn_offers_never_read.cache_clear()


def test_a_pinned_text_blob_of_a_kind_without_offers_stays_on_the_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from metabrowser.git import content_routes

    async def no_thread(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("a kind with no offers took a thread")

    monkeypatch.setattr(content_routes.asyncio, "to_thread", no_thread)
    views = asyncio.run(content_routes._text_views_off_loop("markdown", ".md", b"# Hi\n"))
    assert "source" in _ids(views)


@pytest.mark.usefixtures("record_view_offer")
def test_without_a_file_or_a_prefix_in_hand_no_view_is_offered() -> None:
    assert _ids(server._views_for_kind("structured")) == ["tree", "source"]


@pytest.mark.usefixtures("record_view_offer")
def test_an_unreadable_file_offers_nothing(tmp_path: Path) -> None:
    assert _ids(server._views_for_kind("structured", target=tmp_path / "gone.json")) == [
        "tree",
        "source",
    ]


@pytest.mark.usefixtures("record_view_offer")
def test_a_failing_offer_leaves_its_view_out_and_the_page_up(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def raises(_prefix: bytes, _ext: str) -> bool:
        raise RuntimeError("offer failed")

    monkeypatch.setitem(server._FILE_OFFERS, ("structured", "table"), raises)

    with caplog.at_level(logging.ERROR, logger=server.LOG.name):
        ids = _ids(server._views_for_kind("structured", prefix=(_RECORDS, ".json")))

    assert ids == ["tree", "source"]
    assert "structured view table offer failed" in caplog.text


@pytest.mark.usefixtures("record_view_offer")
def test_a_view_that_can_never_apply_is_never_offered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(server._FILE_OFFERS, ("structured", "table"), None)
    assert _ids(server._views_for_kind("structured", prefix=(_RECORDS, ".json"))) == [
        "tree",
        "source",
    ]


@pytest.mark.usefixtures("record_view_offer")
def test_a_dropped_default_falls_back_to_the_first_view(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(server._FILE_OFFERS, ("structured", "table"), lambda _p, _e: False)

    views = server._views_for_kind("structured", prefix=(_RECORDS, ".json"))

    assert _ids(views) == ["tree", "source"]
    assert [view["id"] for view in views if view.get("default")] == ["tree"]
