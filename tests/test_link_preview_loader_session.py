"""A link has its card on every page, and the card's code loads only at the first rest.

``tests/dom/link-preview-loader-session.js`` (pinned whole by
``cli-ui-link-preview-loader.tryscript.md``) runs the SDK's registration
(``metabrowser.previewLink`` in ``static/plugin-sdk-views.js``) whole, app.js's own tooltip,
and the ``link-previews`` bundle it loads, on pages that mostly have no GitHub identity.
These hold, from that transcript, what the split of the card from the resolver's bundle
must keep: nothing is loaded without a pointer's rest on a registered link; the first rest
shows its own link's card once the bundle has run; a rest the pointer left, or the reader
ended, shows none; a link forgotten or disposed before the load has none; a load that fails
leaves every link with its author's title and asks once; a link to a file, a folder, or
another site has its card on a page with no GitHub identity; the SDK's answer for an
outside link is the card's; and the SDK keeps no document its surface let go of.
"""

from __future__ import annotations

import functools
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from devtools import check_startup_scripts
from tests.golden_harness import run_session

SESSION = "link-preview-loader-session.js"
REPO_ROOT = Path(__file__).resolve().parents[1]


@functools.cache
def _session() -> dict[str, list[dict[str, Any]]]:
    return run_session(SESSION)


def _seen(log: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [entry for entry in log if entry.get("sees")]


def test_nothing_is_loaded_until_a_pointer_rests_on_a_registered_link() -> None:
    """Every load follows a pointer's arrival on a link, at that arrival, and is the page's
    only one; a page the pointer never rests on loads nothing."""

    for name, log in _session().items():
        loads = [index for index, entry in enumerate(log) if "load" in entry]
        assert len(loads) <= 1, name
        for index in loads:
            arrival = next(entry for entry in reversed(log[:index]) if "pointer" in entry)
            assert arrival.get("pointerType", "mouse") == "mouse", (name, arrival)
            assert arrival["at"] == log[index]["at"], (name, arrival, log[index])
    assert not any("load" in entry for entry in _session()["registered before the bundle"])
    touched = _session()["a touch"]
    first_mouse = next(
        index
        for index, entry in enumerate(touched)
        if entry.get("pointer") == "the guide" and "pointerType" not in entry
    )
    assert all("load" not in entry for entry in touched[:first_mouse])


def test_the_first_rest_shows_its_links_card_once_the_bundle_runs() -> None:
    """The first card is on the link the pointer arrived on, no sooner than the tooltip's
    own delay after the bundle ran, and with what its provider read for it."""

    for name in ("the first rest loads it", "the first rest keeps its time"):
        log = _session()[name]
        loaded = next(entry["at"] for entry in log if "loaded" in entry)
        arrival = next(entry for entry in log if "pointer" in entry)
        first = _seen(log)[0]
        assert first["on"] == arrival["pointer"], (name, first)
        assert first["at"] >= loaded + _appear_delay(), (name, first, loaded)
        assert all(
            entry["sees"] is None for entry in log if "sees" in entry and entry["at"] < first["at"]
        )
    kept = _session()["the first rest keeps its time"]
    arrival = next(entry["at"] for entry in kept if "pointer" in entry)
    read = next(entry for entry in kept if entry.get("read", "").startswith("github/pulls"))
    assert read["at"] - arrival == _intent_ms(), read
    assert "feat(links)" in _seen(kept)[0]["sees"]


def test_a_page_with_no_github_identity_gives_its_links_cards() -> None:
    """A Markdown document's links to a file, a folder, and another site each have a card
    on a plain folder's page; a mail link has none and keeps its title."""

    log = _session()["the first rest loads it"]
    answers = {entry["registered"]: entry["card"] for entry in log if "registered" in entry}
    assert answers == {
        "the guide": True,
        "the docs folder": True,
        "elsewhere": True,
        "write to us": False,
    }
    cards = {entry["on"]: entry["sees"] for entry in _seen(log)}
    assert set(cards) == {"the guide", "the docs folder", "elsewhere"}, cards
    assert cards["the guide"].startswith("docs/guide.md"), cards
    assert cards["the docs folder"].startswith("docs/"), cards
    assert cards["elsewhere"].startswith("Opens example.com"), cards


def test_a_rest_that_ended_while_the_bundle_loaded_shows_no_card() -> None:
    """The pointer leaving, or the reader's press, during the load leaves no card; the next
    rest has one, and loads nothing again."""

    for name, ended in (("left during the load", "pointer"), ("pressed during the load", "press")):
        log = _session()[name]
        loaded = next(index for index, entry in enumerate(log) if "loaded" in entry)
        ending = next(
            index for index, entry in enumerate(log) if ended in entry and entry["at"] > 0
        )
        assert ending < loaded, (name, log[ending])
        back = next(entry["at"] for entry in log[loaded:] if entry.get("pointer") == "the guide")
        first = _seen(log)[0]
        assert first["at"] > back and first["on"] == "the guide", (name, first, back)
        assert sum("load" in entry for entry in log) == 1, name


def test_a_link_forgotten_or_disposed_before_the_load_has_no_card() -> None:
    log = _session()["forgotten and disposed before the load"]
    cards = {entry["on"] for entry in _seen(log)}
    assert cards == {"the guide"}, cards
    load = next(index for index, entry in enumerate(log) if "load" in entry)
    rests = [entry["pointer"] for entry in log[:load] if "pointer" in entry]
    assert rests == ["the docs folder", "the guide"], rests


def test_a_failed_load_leaves_links_as_they_were_and_asks_once() -> None:
    log = _session()["a failed load"]
    assert not _seen(log)
    assert sum("load" in entry for entry in log) == 1
    assert sum("warned" in entry for entry in log) == 1
    failed = next(entry["at"] for entry in log if entry.get("failed"))
    later = [entry for entry in log if "registered" in entry and entry["at"] > failed]
    assert later and all(entry["card"] is False for entry in later), later


def test_the_sdks_answer_for_an_outside_link_is_the_cards() -> None:
    """Whether the SDK says an outside link has a card before the card's code loads is what
    the card says once it has: the hand-over gives no link back the title its surface took
    off it, and each address registered again answers the same. An address is read where
    the browser follows it, against the page's own, and only so far."""

    log = _session()["outside addresses"]
    loaded = next(index for index, entry in enumerate(log) if "loaded" in entry)
    before = {entry["registered"]: entry["card"] for entry in log[:loaded] if "registered" in entry}
    after = {entry["registered"]: entry["card"] for entry in log[loaded:] if "registered" in entry}
    assert before == after
    handed = next(entry["titles"] for entry in log if "titles" in entry)
    assert {name: title is None for name, title in handed.items()} == before
    assert before["the page's scheme and no host"] is False
    assert before["the page's own origin"] is False
    assert before["an address at the bound"] is True
    assert before["an address past the bound"] is False
    cards = {entry["on"]: entry["sees"] for entry in _seen(log)}
    for name in ("a scheme-relative address", "another scheme and no slashes"):
        assert cards[name].startswith("Opens example.com"), cards


def test_the_sdk_keeps_no_document_its_surface_let_go_of() -> None:
    """A document replaced without `disposePreviews` before the card's code loads is the
    collector's, and the next document's first rest still loads the card."""

    log = _session()["a document no surface disposed"]
    assert [entry["collected"] for entry in log if "collected" in entry] == [True]
    assert [entry["on"] for entry in _seen(log)] == ["the docs folder"]


def test_links_registered_during_and_after_the_load_have_cards() -> None:
    """A link registered while the bundle loads is handed over with the rest, one registered
    after goes to the registry, and a document keeps one pair of pointer listeners through
    the hand-over."""

    log = _session()["registered during and after the load"]
    load = next(entry["at"] for entry in log if "load" in entry)
    loaded = next(entry["at"] for entry in log if "loaded" in entry)
    registered = [entry for entry in log if "registered" in entry]
    assert any(load < entry["at"] < loaded for entry in registered), registered
    assert any(entry["at"] > loaded for entry in registered), registered
    assert all(entry["card"] for entry in registered)
    assert {entry["on"] for entry in _seen(log)} == {entry["registered"] for entry in registered}
    assert len({entry["listeners"] for entry in log if "listeners" in entry}) == 1


def test_the_card_loads_apart_from_the_resolver_and_is_no_startup_script() -> None:
    """The card is the `link-previews` bundle, its registry before the providers that
    register with it, on no startup path and not in the resolver's bundle, and the sessions
    run that bundle as the server lists it."""

    html = check_startup_scripts.render_folder_shell()
    bundles = json.loads(
        html.split("window.METABROWSER_ASSET_BUNDLES=", 1)[1].split(";</script>", 1)[0]
    )
    cards = [urlsplit(entry["src"]).path for entry in bundles["link-previews"]]
    assert cards.index("/static/link-previews.js") < cards.index(
        "/static/link-preview-providers.js"
    )
    assert bundles["link-previews"][0]["provides"] == "MetabrowserLinkPreviews"
    resolver = {urlsplit(entry["src"]).path for entry in bundles["repository-links"]}
    assert not resolver & set(cards), resolver
    assert not set(check_startup_scripts.startup_script_paths(html)) & set(cards)
    page = (REPO_ROOT / "tests/dom/link-card-page.js").read_text(encoding="utf-8")
    listed = re.search(r"const LINK_PREVIEWS_BUNDLE = \[([^\]]*)\]", page)
    assert listed is not None
    assert [f"/static/{name}" for name in re.findall(r'"([^"]+)"', listed.group(1))] == cards


@functools.cache
def _appear_delay() -> int:
    app = (REPO_ROOT / "src/metabrowser/static/app.js").read_text(encoding="utf-8")
    found = re.search(r"\nvar TOOLTIP_APPEAR_DELAY = (\d+);", app)
    assert found is not None
    return int(found.group(1))


@functools.cache
def _intent_ms() -> int:
    module = (REPO_ROOT / "src/metabrowser/static/link-previews.js").read_text(encoding="utf-8")
    found = re.search(r"\n  const INTENT_MS = (\d+);", module)
    assert found is not None
    return int(found.group(1))
