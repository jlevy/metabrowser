"""The link card holds its rules across its real boundaries, not only against stand-ins.

``tests/dom/link-card-integration-session.js`` (pinned whole by
``cli-ui-link-card-integration.tryscript.md``) runs app.js's own tooltip and its delegated
listeners, the resolver's ``enhance``, the card's registry, and its providers in one realm,
each read replaying the server's recorded answer. These hold, from that transcript, the
rules the review found broken at those boundaries: a card is placed on the link the pointer
rests on, and another link's card replaces it; focus brings no card back; a read that failed
and a page state that changed are read again at the next rest; a file the Quick File
catalog leaves out is not called missing; an image inside a link shows no tooltip of its
own; and a link to another site says where it goes.
"""

from __future__ import annotations

import functools
from typing import Any

from tests.golden_harness import run_session

SESSION = "link-card-integration-session.js"


@functools.cache
def _session() -> dict[str, list[dict[str, Any]]]:
    return run_session(SESSION)


def _seen(log: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [entry for entry in log if entry.get("sees")]


def test_a_card_is_placed_on_the_link_the_pointer_rests_on() -> None:
    """Each card is on the link the pointer last arrived on. The image's session rests on
    the link's parts, and focus's shows none; both are held below."""

    for name, log in _session().items():
        if name in {"an image inside a link", "focus during the read"}:
            continue
        under = None
        for entry in log:
            under = entry.get("pointer", under)
            if entry.get("sees"):
                assert entry["on"] == under, (name, entry)
        assert _seen(log), name


def test_the_next_links_card_replaces_the_one_up() -> None:
    log = _session()["handover"]
    last = _seen(log)[-1]
    assert last["on"] == "#13" and last["sees"].startswith("Pull request #13"), last


def test_focus_during_a_read_brings_no_card_back() -> None:
    log = _session()["focus during the read"]
    focused = next(index for index, entry in enumerate(log) if "focus" in entry)
    assert any("read" in entry for entry in log[:focused])
    assert not _seen(log[focused:])


def test_what_failed_or_changed_is_read_again_at_the_next_rest() -> None:
    session = _session()
    retried = session["a failed read, then the next rest"]
    reads = [entry["read"] for entry in retried if entry.get("read", "").startswith("github/pulls")]
    assert len(reads) == 2, reads
    first, second = (entry["sees"] for entry in _seen(retried))
    assert first != second and second.startswith(first.split(" | ")[0]), (first, second)
    before, after = (
        entry["sees"].split(" | ") for entry in _seen(session["a folder the tree totals"])
    )
    assert set(before) < set(after), (before, after)


def test_a_file_the_catalog_leaves_out_reads_as_one_it_lists() -> None:
    """The page's Quick File catalog is not every file a link can open: it leaves out a
    hidden, a gitignored, and a symlinked file, which the served folder opens all the same.
    So a card on a link to one says what a card on a file the catalog lists says, but for
    the file's path: no line of it is drawn from the catalog's not holding it."""

    log = _session()["files the catalog leaves out"]
    cards: dict[str, list[str]] = {}
    for entry in log:
        if entry.get("sees"):
            cards[entry["on"]] = entry["sees"].split(" | ")
    listed = [lines for name, lines in cards.items() if name.startswith("listed ")]
    unlisted = {name: lines for name, lines in cards.items() if name.startswith("unlisted ")}
    assert listed and len(unlisted) >= 3, cards
    for name, lines in unlisted.items():
        assert lines[0] == name.removeprefix("unlisted "), (name, lines)
        assert all(lines[1:] == other[1:] for other in listed), (name, lines, listed)


def test_an_image_inside_a_link_shows_one_tooltip_the_link_card() -> None:
    log = _session()["an image inside a link"]
    seen = _seen(log)
    assert len(seen) == 3 and len({entry["sees"] for entry in seen}) == 1, seen
    assert all(entry["on"] == "#12" for entry in seen), seen
    assert any(line.startswith("Image from ") for line in seen[0]["sees"].split(" | "))


def test_a_link_to_another_site_says_where_it_goes_and_reads_nothing() -> None:
    log = _session()["a link to another site"]
    [seen] = _seen(log)
    assert seen["sees"].startswith("Opens example.com"), seen
    assert not any("read" in entry for entry in log)
