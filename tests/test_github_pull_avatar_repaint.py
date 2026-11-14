"""A pull request's header keeps its nodes across repaints, and each avatar loads by its
placement's policy.

``tests/dom/github-pull-avatar-repaint-behavior.js`` mounts the production pull page on
the recorded record of pull request 7, gives its actors avatars, switches through every
tab and back, and lets two polls find a refresh running, the second changing only the
status line's age. Then four polls each change one of the header's inputs: a label, the
head branch, the author's avatar, and the state, merged by another actor. It asserts that
every avatar the page creates has its placement's loading, eager in the header and lazy in
the conversation, decodes asynchronously, keeps its 18 px slot, and hides itself on an
error; that the header's avatar is the one its actor has at each step; and this pins the
steps it went through, which of the header's parts each found new, how many header
elements each built, and how many it kept but took out of their parents and put back.

A repaint that changes none of the header's inputs builds none of its nodes and moves
none. Before, it built every part again, about 30 elements on each tab switch and poll,
and a node replaced under the reader lost its focus, as a focused branch chip's copy
button did in headless Chrome. A kept node put back in the same task loses its focus too,
so `detached` counts them: placing the header's parts with `replaceChildren` built
nothing and detached all 42. A changed input builds its part again and only that part,
and moves no other. This checks node lifecycle and attributes, not paint;
docs/design-system.md, "A Repaint Keeps Its Images", has the measurements.
"""

from __future__ import annotations

from tests.golden_harness import run_session

# A repaint that changes none of the header's inputs.
UNCHANGED = {"header": "kept", "rebuilt": [], "built": 0, "detached": 0}


def test_the_header_keeps_its_nodes_and_each_avatar_loads_by_its_placement() -> None:
    result = run_session("github-pull-avatar-repaint-behavior.js")
    assert result == {
        "steps": [
            # The header's author; the description's and five timeline cards'.
            {
                "step": "Conversation",
                "header": "first",
                "rebuilt": "first",
                "built": 42,
                "detached": 0,
                "created": {"header": 1, "conversation": 6},
                "shown": 7,
            },
            # Each tab and back: the header keeps every node, its avatar among them.
            {
                "step": "Changes",
                **UNCHANGED,
                "created": {"header": 0, "conversation": 0},
                "shown": 1,
            },
            {
                "step": "Checks",
                **UNCHANGED,
                "created": {"header": 0, "conversation": 0},
                "shown": 1,
            },
            # The conversation keeps its sections, avatars and all, across tabs and polls.
            {
                "step": "Conversation again",
                **UNCHANGED,
                "created": {"header": 0, "conversation": 0},
                "shown": 7,
            },
            # Refresh hides while the refresh runs; it is the same button.
            {
                "step": "a poll finds a refresh running",
                **UNCHANGED,
                "created": {"header": 0, "conversation": 0},
                "shown": 7,
            },
            {
                "step": "the next poll finds it checked",
                **UNCHANGED,
                "created": {"header": 0, "conversation": 0},
                "shown": 7,
            },
            # Each changed input builds its own part again, and nothing else.
            {
                "step": "a label is added",
                "header": "kept",
                "rebuilt": ["labels"],
                "built": 2,
                "detached": 0,
                "created": {"header": 0, "conversation": 0},
                "shown": 7,
            },
            {
                "step": "the head branch is renamed",
                "header": "kept",
                "rebuilt": ["branches", "copy buttons"],
                "built": 8,
                "detached": 0,
                "created": {"header": 0, "conversation": 0},
                "shown": 7,
            },
            # The description's author is the header's, so it changes there too.
            {
                "step": "the author's avatar changes",
                "header": "new",
                "rebuilt": ["identity"],
                "built": 3,
                "detached": 0,
                "created": {"header": 1, "conversation": 1},
                "shown": 7,
            },
            # A merge changes the state and the actor: the title's icon, the badge, the
            # sentence, and the row of ages, which gains the merge's. The branches, the
            # badge's sizers, the labels, and Refresh are kept.
            {
                "step": "another actor merges it",
                "header": "new",
                "rebuilt": [
                    "title",
                    "state icon",
                    "badge",
                    "identity",
                    "action",
                    "opened row",
                    "GitHub link",
                ],
                "built": 16,
                "detached": 0,
                "created": {"header": 1, "conversation": 6},
                "shown": 7,
            },
        ],
        "loading": {"header": ["eager"], "conversation": ["lazy"]},
    }
