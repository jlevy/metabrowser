"""A plugin's folder view offered only where its predicate accepts the folder.

The agents plugin offers its home and session list on a Claude Code or Codex home
and nowhere else; these pin the server's half of that contract with a stand-in
predicate, since the predicate itself is the plugin's.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import pytest

from metabrowser import server
from metabrowser.plugin_loader.discovery import LoadedPlugin
from metabrowser.plugin_loader.manifest import PluginManifest, view_entry
from metabrowser.plugin_loader.static_assets import resolve_folder_offers

_HOME_VIEW = {
    "id": "agent-home",
    "label": "Agents",
    "default": True,
    "container_class": "content-body",
}


def _is_marked(folder: Path) -> bool:
    return (folder / "marker").exists()


def _raises(_folder: Path) -> bool:
    raise RuntimeError("offer failed")


@pytest.fixture
def offered(monkeypatch: pytest.MonkeyPatch) -> None:
    folder_views = [*server._PLUGIN_VIEWS_BY_KIND.get("folder", []), _HOME_VIEW]
    monkeypatch.setitem(server._PLUGIN_VIEWS_BY_KIND, "folder", folder_views)
    monkeypatch.setattr(
        server, "_FOLDER_OFFERS", {**server._FOLDER_OFFERS, "agent-home": _is_marked}
    )


def _ids_and_default(views: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    return [v["id"] for v in views], [v["id"] for v in views if v.get("default")]


@pytest.mark.usefixtures("offered")
def test_an_offered_view_appears_where_its_predicate_accepts_and_becomes_the_default(
    tmp_path: Path,
) -> None:
    (tmp_path / "marker").touch()

    ids, defaults = _ids_and_default(server._views_for_kind("folder", target=tmp_path))

    assert ids == ["overview", "treemap", "agent-home"]
    assert defaults == ["agent-home"]


@pytest.mark.usefixtures("offered")
def test_an_offered_view_is_absent_elsewhere_and_the_overview_stays_default(
    tmp_path: Path,
) -> None:
    ids, defaults = _ids_and_default(server._views_for_kind("folder", target=tmp_path))

    assert ids == ["overview", "treemap"]
    assert defaults == ["overview"]


@pytest.mark.usefixtures("offered")
def test_without_a_folder_in_hand_no_view_is_offered() -> None:
    """A Git folder's views come from here with no target, so it never gets one."""
    ids, _defaults = _ids_and_default(server._views_for_kind("folder"))
    assert "agent-home" not in ids


def test_a_failing_offer_leaves_its_view_out_and_the_page_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    folder_views = [*server._PLUGIN_VIEWS_BY_KIND.get("folder", []), _HOME_VIEW]
    monkeypatch.setitem(server._PLUGIN_VIEWS_BY_KIND, "folder", folder_views)
    monkeypatch.setattr(server, "_FOLDER_OFFERS", {**server._FOLDER_OFFERS, "agent-home": _raises})

    with caplog.at_level(logging.ERROR, logger=server.LOG.name):
        ids, defaults = _ids_and_default(server._views_for_kind("folder", target=tmp_path))

    assert ids == ["overview", "treemap"]
    assert defaults == ["overview"]
    assert "agent-home offer failed" in caplog.text


def _manifest(view: dict[str, Any]) -> PluginManifest:
    return PluginManifest.model_validate(
        {
            "plugin": {"name": "offers", "version": "0.0.1", "sdk_version": "0.8"},
            "view": [view],
        }
    )


def test_only_a_folder_view_may_declare_an_offer() -> None:
    manifest = _manifest(
        {"kind": "markdown", "id": "x", "label": "X", "offer": "tests.module:predicate"}
    )
    assert any("only a view of the folder kind" in p for p in manifest.validate_consistency())


def test_an_offer_must_name_a_module_and_a_function() -> None:
    with pytest.raises(ValueError, match="offer"):
        _manifest({"kind": "folder", "id": "x", "label": "X", "offer": "no_function_here"})


def test_the_envelope_entry_does_not_carry_the_offer() -> None:
    """The predicate is the server's business; the browser sees an ordinary view."""
    manifest = _manifest(
        {"kind": "folder", "id": "x", "label": "X", "offer": "tests.module:predicate"}
    )
    assert "offer" not in view_entry(manifest.view[0])


def _plugin(offer: str, source: str) -> LoadedPlugin:
    manifest = _manifest({"kind": "folder", "id": "home", "label": "Home", "offer": offer})
    return LoadedPlugin(name="offers", static_root=Path("."), manifest=manifest, source=source)


def test_offers_resolve_by_view_id() -> None:
    offers = resolve_folder_offers([_plugin("os.path:isdir", "builtin")])
    assert offers == {"home": os.path.isdir}


@pytest.mark.parametrize(
    ("offer", "source"),
    [
        ("os.path:isdir", "local:/plugins"),
        ("metabrowser_no_such_module:predicate", "builtin"),
        ("os.path:no_such_function", "builtin"),
        ("os.path:sep", "builtin"),
    ],
    ids=["javascript-only-plugin", "missing-module", "missing-function", "not-callable"],
)
def test_an_offer_that_cannot_apply_is_never_offered(offer: str, source: str) -> None:
    assert resolve_folder_offers([_plugin(offer, source)]) == {"home": None}
