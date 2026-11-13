"""Each avatar on a pull request's page loads by the policy of where it is placed.

``tests/dom/github-pull-avatar-repaint-behavior.js`` mounts the production pull page on
the recorded record of pull request 7, gives its actors avatars, switches through every
tab and back, and lets a poll find a refresh running. It asserts that every avatar the
page creates has its placement's loading, eager in the header and lazy in the
conversation, decodes asynchronously, keeps its 18 px slot, and hides itself on an error;
this pins the steps it went through and what each built or kept.

The header's avatar is a new image on each tab switch and poll. In WebKit, the macOS
app's engine, a new lazy image waits for layout and asks the network again, which left
that avatar with no image for the round trip, so it is eager. The conversation keeps its
sections across tabs and polls, so its avatars stay lazy. This checks attributes and node
lifecycle, not paint; docs/design-system.md, "A Repaint Keeps Its Images", has the
measurements.
"""

from __future__ import annotations

from tests.golden_harness import run_session


def test_each_avatar_loads_by_its_placement_across_repaints() -> None:
    result = run_session("github-pull-avatar-repaint-behavior.js")
    assert result == {
        "steps": [
            # The header's author; the description's and five timeline cards'.
            {
                "step": "Conversation",
                "header": "first",
                "created": {"header": 1, "conversation": 6},
                "shown": 7,
            },
            # Each repaint builds the header's actor again: a new image, eager.
            {
                "step": "Changes",
                "header": "new",
                "created": {"header": 1, "conversation": 0},
                "shown": 1,
            },
            {
                "step": "Checks",
                "header": "new",
                "created": {"header": 1, "conversation": 0},
                "shown": 1,
            },
            # The conversation keeps its sections, avatars and all, across tabs and polls.
            {
                "step": "Conversation again",
                "header": "new",
                "created": {"header": 1, "conversation": 0},
                "shown": 7,
            },
            {
                "step": "a poll finds a refresh running",
                "header": "new",
                "created": {"header": 1, "conversation": 0},
                "shown": 7,
            },
        ],
        "loading": {"header": ["eager"], "conversation": ["lazy"]},
    }
