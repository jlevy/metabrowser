"""A plugin's file view offered only where its predicate accepts the file's leading bytes.

The structured kind offers its Table view only on a JSON or YAML file that starts as a
list of records (``tests/test_structured_offer.py`` pins its predicate). These pin the
server's half of that contract: what each route that lists a file's views hands the
predicate, and what it does with the answer.
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
from metabrowser.plugin_loader.classify import CONTENT_PREDICATE_MAX_BYTES

_MAPPING = b'{"name": "metabrowser", "version": 1}'
_RECORDS = b'[{"name": "Ada"}, {"name": "Grace"}]'


def _ids(views: list[dict[str, Any]]) -> list[str]:
    return [view["id"] for view in views]


def _api_file(path: str) -> dict[str, Any]:
    request = Mock(spec=["query_params", "headers"])
    request.query_params = {"path": path}
    request.headers = {}
    response = asyncio.run(server.api_file(request))
    return json.loads(bytes(response.body))


@pytest.mark.parametrize(
    ("name", "content", "views"),
    [
        ("people.json", _RECORDS, ["tree", "table", "source"]),
        ("people.yaml", b"- name: Ada\n- name: Grace\n", ["tree", "table", "source"]),
        ("config.json", _MAPPING, ["tree", "source"]),
        ("config.yaml", b"name: metabrowser\n", ["tree", "source"]),
    ],
)
def test_a_file_lists_the_table_view_only_where_it_starts_as_a_list_of_records(
    tmp_path: Path, name: str, content: bytes, views: list[str]
) -> None:
    server._set_root_dir(tmp_path)
    (tmp_path / name).write_bytes(content)
    body = _api_file(name)
    assert (body["kind"], _ids(body["views"])) == ("structured", views)


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

    assert ids == ["tree", "table", "source"]
    assert seen == [(CONTENT_PREDICATE_MAX_BYTES + 1, ".json")]


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


def test_a_pinned_blob_offers_from_its_leading_bytes() -> None:
    """Both of a pin's text responses list views through this, with the blob in hand;
    `tests/golden/cli-git-pin-files.txt` pins a mapping's views without the Table."""
    from metabrowser.git.content_routes import _text_views_off_loop

    offered = asyncio.run(_text_views_off_loop("structured", ".json", _RECORDS))
    refused = asyncio.run(_text_views_off_loop("structured", ".json", _MAPPING))

    assert (_ids(offered), _ids(refused)) == (["tree", "table", "source"], ["tree", "source"])


def test_without_a_file_or_a_prefix_in_hand_no_view_is_offered() -> None:
    assert _ids(server._views_for_kind("structured")) == ["tree", "source"]


def test_an_unreadable_file_offers_nothing(tmp_path: Path) -> None:
    assert _ids(server._views_for_kind("structured", target=tmp_path / "gone.json")) == [
        "tree",
        "source",
    ]


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


def test_a_view_that_can_never_apply_is_never_offered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(server._FILE_OFFERS, ("structured", "table"), None)
    assert _ids(server._views_for_kind("structured", prefix=(_RECORDS, ".json"))) == [
        "tree",
        "source",
    ]


def test_a_dropped_default_falls_back_to_the_first_view(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(server._FILE_OFFERS, ("structured", "tree"), lambda _p, _e: False)

    views = server._views_for_kind("structured", prefix=(_RECORDS, ".json"))

    assert _ids(views) == ["table", "source"]
    assert [view["id"] for view in views if view.get("default")] == ["table"]
