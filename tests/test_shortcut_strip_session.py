"""The shortcut strip stays one row, Shift first, in the browserless session.

``tests/dom/shortcut-strip-session.js`` runs the production Help, its strip, the Shift
reveal, and Quick Search on the key reveal's stand-in DOM, gives the strip the boxes a
layout would, and records what it shows at each pane width; its golden is
``tests/golden/cli-ui-shortcut-strip.tryscript.md``. The owner's rule (mb-k8am): the strip
is one row, it drops items from the end, Quick Search first and then Help, Shift always
shows, and a dropped item stays on the revealed layer. These are the invariants the golden
shows, held here so a regenerated transcript cannot quietly change them;
``tests/test_shortcut_strip_chrome.py`` holds the same rule in Chrome.
"""

from __future__ import annotations

from tests.golden_harness import run_session

EVERYTHING = ["Shift Reveal keys", "? Help", "T Quick Search"]


def test_the_strip_drops_items_from_the_end_and_always_keeps_shift() -> None:
    steps = {step["step"]: step for step in run_session("shortcut-strip-session.js")["steps"]}

    unlaid = steps["before a layout, the strip lists Shift, Help, and Quick Search"]
    assert unlaid["strip"] == {"surface": "nav", "items": EVERYTHING}

    narrowing = steps["a narrowing pane drops Quick Search, then Help, and keeps Shift"]
    assert narrowing["panes"] == [
        [300, *EVERYTHING],
        [273, *EVERYTHING],
        [272, *EVERYTHING[:2]],
        [200, *EVERYTHING[:2]],
        [181, *EVERYTHING[:2]],
        [180, *EVERYTHING[:1]],
    ]
    widening = steps["a widening pane brings Help, then Quick Search, back"]
    assert [shown for _pane, *shown in widening["panes"]] == [
        EVERYTHING[:1],
        EVERYTHING[:2],
        EVERYTHING[:2],
        EVERYTHING,
        EVERYTHING,
    ]
    # Whatever the width, what shows is Shift and then the next items in order.
    for step in (narrowing, widening):
        for _pane, *shown in step["panes"]:
            assert shown == EVERYTHING[: len(shown)] and shown, step["step"]

    # What the narrowest pane dropped is on the revealed layer while Shift is held.
    held = steps["Shift held in the narrowest pane lists what the strip dropped"]
    assert held["reveal"] == "revealed"
    assert held["strip"] == {"surface": "reveal", "items": ["? Help", "T or / Quick Search"]}
    released = steps["Shift released, the narrowest pane shows Shift alone"]
    assert released["strip"] == {"surface": "nav", "items": EVERYTHING[:1]}

    # Wider text is measured again, not fitted from the widths measured before it.
    wider = steps[
        "wider text is measured again: the default pane drops Quick Search, a pixel more keeps it"
    ]
    assert wider["panes"] == [[300, *EVERYTHING[:2]], [301, *EVERYTHING]]

    disposed = steps["disposed, Help empties the strip and stops observing it"]
    assert disposed["strip"]["items"] == []
    assert disposed["observing"] == 0
