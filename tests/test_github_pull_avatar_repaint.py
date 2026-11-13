"""A repaint never blanks an avatar whose address did not change.

``tests/dom/github-pull-avatar-repaint-behavior.js`` mounts the production pull page on
the recorded record of pull request 7, gives its actors avatars, switches through every
tab and back, and lets a poll find a refresh running. It asserts that every avatar the
page creates loads eagerly, decodes asynchronously, keeps its 18 px slot, and hides
itself on an error; this pins the steps it went through and what each did to the header's
avatar.

The page builds its actors again when it repaints, so the header's avatar is a new image
on each tab switch and poll. In WebKit, the macOS app's engine, a lazy image waits for
layout and then asks the network again, which painted that avatar blank for the round
trip; an eager one is the cached image at once. docs/design-system.md, "A Repaint Keeps
Its Images", has the measurements.
"""

from __future__ import annotations

from tests.golden_harness import run_session


def test_a_repaint_creates_avatars_that_paint_at_once() -> None:
    result = run_session("github-pull-avatar-repaint-behavior.js")
    assert result == {
        "steps": [
            # The header's author, the description's, and five timeline cards'.
            {"step": "Conversation", "header": "first", "avatarsCreated": 7, "avatarsShown": 7},
            # Each repaint builds the header's actor again: a new image, eager.
            {"step": "Changes", "header": "new", "avatarsCreated": 1, "avatarsShown": 1},
            {"step": "Checks", "header": "new", "avatarsCreated": 1, "avatarsShown": 1},
            # The conversation keeps its sections, avatars and all, across tabs.
            {
                "step": "Conversation again",
                "header": "new",
                "avatarsCreated": 1,
                "avatarsShown": 7,
            },
            {
                "step": "a poll finds a refresh running",
                "header": "new",
                "avatarsCreated": 1,
                "avatarsShown": 7,
            },
        ],
        "everyAvatarEager": True,
    }
