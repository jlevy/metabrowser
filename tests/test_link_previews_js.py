"""The link card's rules hold on what the exact module does, not on a copy of its source.

``static/link-previews.js`` gives a link that opens a page in Metabrowser the link card
(docs/design-system.md, "Tooltips on Links"). The browserless session
(``tests/dom/link-previews-session.js``, pinned whole by
``cli-ui-link-previews.tryscript.md``) runs it on app.js's own tooltip code and a clock
of its own. These read that transcript for the rules every card and every rest keeps: a
card never says its link's text again, ends with where the link opens, and claims a state
only its data gives; a rest asks for a summary at the tree's own hover delay, never on
focus or touch, with one read and one prefetch in flight and none aborted; and a surface's
``dispose`` puts away its own card and no other.
"""

from __future__ import annotations

import functools
import json
import re
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from devtools import check_startup_scripts
from tests.required_tools import require_node

ROOT = Path(__file__).resolve().parents[1]
SESSION_JS = ROOT / "tests" / "dom" / "link-previews-session.js"
APP_JS = ROOT / "src" / "metabrowser" / "static" / "app.js"
OPENS = ("Opens here in Metabrowser", "Opens in the served working tree")
STATES = ("open", "closed", "merged", "draft")


@functools.cache
def _session() -> dict[str, Any]:
    result = subprocess.run(
        [require_node(), str(SESSION_JS)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    return json.loads(result.stdout)


def _app_constant(declaration: str) -> int:
    """The number app.js gives *declaration*, ``const NAME`` or ``var NAME``."""

    match = re.search(rf"\b{declaration} = (\d+);", APP_JS.read_text(encoding="utf-8"))
    assert match is not None, f"app.js no longer declares {declaration}"
    return int(match[1])


def _fold(text: str) -> str:
    return " ".join(text.split()).lower()


def _lines(html: str) -> list[str]:
    """A card's lines as the reader sees their words, its mark left out."""

    parts = [part for part in html.split("</div>") if part]
    words = [re.sub(r"<[^>]+>", "", part) for part in parts]
    return [
        line.replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
        .replace("&amp;", "&")
        for line in words
    ]


def _drawn_cards() -> list[dict[str, Any]]:
    return [row for row in _session()["cards"] if row.get("html")]


def test_a_card_never_says_its_links_text_again() -> None:
    cards = _session()["cards"]
    assert any(row["label"] == "the link's text is the title" for row in cards)
    for row in cards:
        if not row.get("linkText"):
            continue
        said = [_fold(line) for line in _lines(row["html"])] if "html" in row else []
        for line in row.get("text", "").split(" | "):
            said.append(_fold(re.sub(r"^\[[^\]]+\] ", "", line)))
        assert _fold(row["linkText"]) not in said, row["label"]


def test_a_card_ends_with_where_its_link_opens() -> None:
    for row in _drawn_cards():
        last = _lines(row["html"])[-1]
        preview = row["preview"] if isinstance(row["preview"], dict) else {}
        missing = preview.get("missing")
        assert last == missing if missing else last in OPENS, row["label"]


def test_a_card_claims_a_state_only_its_data_gives() -> None:
    session = _session()
    for row in _drawn_cards():
        preview = row["preview"] if isinstance(row["preview"], dict) else {}
        claimed = re.findall(r'data-state="([a-z]+)"', row["html"])
        assert claimed == ([preview["state"]] if preview.get("state") in STATES else []), row
    # The address alone, a title alone, and a state the card does not know draw the neutral
    # mark; so does a state given before the github plugin's glyphs have loaded.
    after = session["states"]["after"]
    assert after["no data"].startswith("[pull] ")
    assert after["a title alone"].startswith("[pull] ")
    assert after["a state the card does not know"].startswith("[pull] ")
    assert after["a draft"].startswith("[draft] ")
    assert session["states"]["beforeTheGlyphsLoad"].startswith("[pull] ")


def test_a_providers_text_is_never_markup() -> None:
    row = next(row for row in _session()["cards"] if row["label"] == "a title with markup")
    assert "<img" not in row["html"]
    assert "&lt;img src=x onerror=&quot;go()&quot;&gt; &amp; &#39;q&#39;" in row["html"]


def test_a_rest_asks_at_the_trees_own_hover_delay() -> None:
    """The summary starts when a tree row's prefetch would: app.js's delay, not a copy."""

    delay = _app_constant("const FILE_PREFETCH_HOVER_DELAY_MS")
    log = _session()["timing"]["an answer during the delay: the card waits for it"]
    assert log[0]["at"] == 0 and "show" in log[0]
    assert [entry["at"] for entry in log if "summary" in entry or "prefetch" in entry] == [
        delay,
        delay,
    ]


def test_the_card_appears_only_on_the_tooltips_own_timer() -> None:
    """A card first seen in a rest was asked for at least the tooltip's delay before."""

    delay = _app_constant("var TOOLTIP_APPEAR_DELAY")
    timing = _session()["timing"]
    for name, log in timing.items():
        rest_began = 0
        for index, entry in enumerate(log):
            if entry.get("hide"):
                rest_began = index + 1
            if not entry.get("tooltip") or any(
                earlier.get("tooltip") for earlier in log[rest_began:index]
            ):
                continue
            last_show = max(e["at"] for e in log[rest_began:index] if "show" in e)
            assert entry["at"] - last_show >= delay, name
    passed = timing["a pass across the link: nothing is read"]
    assert not any("summary" in entry or "prefetch" in entry for entry in passed)
    assert all(entry.get("tooltip") is None for entry in passed if "tooltip" in entry)


def test_a_late_answer_is_kept_for_the_next_rest() -> None:
    log = _session()["timing"]["a late answer: kept for the next rest"]
    assert sum("summary" in entry for entry in log) == 1
    shows = [entry for entry in log if "show" in entry]
    seen = [entry["tooltip"] for entry in log if entry.get("tooltip")]
    assert "Keep the tail" not in seen[0], "the card already up took the late answer"
    assert "Keep the tail" in shows[-1]["card"] and "Keep the tail" in seen[-1]


def test_one_read_and_one_prefetch_in_flight_and_none_aborted() -> None:
    requests = _session()["requests"]
    assert requests["counts"] == {
        "reads": 0,
        "prefetches": 0,
        "maxReads": 1,
        "maxPrefetches": 1,
        "aborted": 0,
    }
    asked = [(entry["at"], entry.get("summary")) for entry in requests["log"] if "summary" in entry]
    # The second link's rest began during the first's read and waited for it to settle.
    assert asked == [(250, "pull 1"), (650, "pull 2")]


def test_focus_and_touch_show_no_card() -> None:
    modality = _session()["modality"]
    assert not any("show" in entry for entry in modality["focus, keys, and a touch"])
    assert any("show" in entry for entry in modality["then a pen"])


def test_focus_or_a_press_during_a_rest_brings_no_card_back() -> None:
    """A Tab or a click onto the rested link ends the rest: no later answer shows its card."""

    modality = _session()["modality"]
    for name, act in (("focus during the read", "focus"), ("a press during the read", "press")):
        log = modality[name]
        acted = next(index for index, entry in enumerate(log) if act in entry)
        # The read was asked for before the reader acted, and answered after.
        assert any("summary" in entry for entry in log[:acted]), name
        assert not any("show" in entry or entry.get("tooltip") for entry in log[acted:]), name


def test_a_failing_provider_leaves_the_card_with_where_it_opens() -> None:
    for name, session in _session()["failures"].items():
        assert session["cards"] == ["Commit 0123456 | Opens here in Metabrowser"] * 2, name
    # A failure is asked about again at the next rest; an answer of nothing is kept.
    assert _session()["failures"]["a provider that throws"]["asked"] == 2
    assert _session()["failures"]["a provider that answers null"]["asked"] == 1


def test_a_surface_puts_away_only_its_own_card() -> None:
    log = _session()["disposal"]["dispose"]
    other = next(index for index, entry in enumerate(log) if entry.get("hide") == "comment")
    own = next(index for index, entry in enumerate(log) if entry.get("hide") == "readme")
    assert log[other + 1]["tooltip"], "another root's dispose put the card away"
    assert log[own + 1]["tooltip"] is None, "the root's dispose left its card"


def test_a_pins_address_reads_as_the_same_path() -> None:
    rows = _session()["subjects"]
    subjects = {row["label"]: row.get("subject") for row in rows}
    shown = ("kind", "path", "opens")
    checkout = {key: subjects["a file at the served commit"][key] for key in shown}
    for label in (
        "the same file on the pin",
        "a rendered diff's head link",
        "the same file on the pin, as the page's source kind reads it",
    ):
        assert {key: subjects[label][key] for key in shown} == checkout, label
    assert subjects["a head link whose name is not text"] is None


def test_a_files_subject_keeps_the_resolvers_own_spelling() -> None:
    """A provider opens the address the resolver spelled, never the display path again."""

    rows = _session()["subjects"]
    subjects = {row["label"]: row.get("subject") for row in rows}
    wire = next(row["path"] for row in rows if row["label"] == "a pin's address for it")
    assert subjects["the same file on the pin"]["target"] == {"path": wire}
    assert subjects["a file at the served commit"]["target"] == {"path": "docs/guide.md"}
    assert subjects["a name holding %"]["target"] == {"path": "docs/100%25.md"}
    assert subjects["a folder on the served branch"]["target"] == {"path": "docs/"}
    assert subjects["a file with a query and an anchor"]["target"] == {
        "path": "docs/guide.md",
        "query": "plain=1",
        "fragment": "install",
    }
    # A head link's target is its wire path and its fragment, decoded.
    assert subjects["a rendered diff's head link"]["target"] == {
        "path": wire,
        "fragment": "install",
    }
    assert subjects["a head link with an escaped anchor"]["target"]["fragment"] == "über-uns"
    assert subjects["a head link whose anchor does not decode"] is None


def test_the_card_loads_with_the_resolver_and_is_no_startup_script() -> None:
    html = check_startup_scripts.render_folder_shell()
    bundles = json.loads(
        html.split("window.METABROWSER_ASSET_BUNDLES=", 1)[1].split(";</script>", 1)[0]
    )
    names = [urlsplit(entry["src"]).path for entry in bundles["repository-links"]]
    resolver = names.index("/static/repository-links.js")
    assert names[resolver + 1] == "/static/link-previews.js"
    entry = bundles["repository-links"][resolver + 1]
    assert entry["provides"] == "MetabrowserLinkPreviews"
    assert "/static/link-previews.js" not in check_startup_scripts.startup_script_paths(html)
