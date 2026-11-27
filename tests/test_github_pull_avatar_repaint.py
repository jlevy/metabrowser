"""A pull request's header keeps its nodes across repaints, and each avatar loads by its
placement's policy.

``tests/dom/github-pull-avatar-repaint-behavior.js`` mounts the production pull page on
the recorded record of pull request 7, gives its actors avatars, switches through every
tab and back, and lets two polls find a refresh running, the second finding the record
checked, which changes nothing shown, since the freshness note says the fetch alone.
Then four polls each change one of the header's inputs: a label, the head branch, the
author's avatar, and the state, merged by another actor. It asserts that
every avatar the page creates has its placement's loading, eager in the header and lazy in
the conversation, decodes asynchronously, sits in its 18 px box, and gives the box to
the person glyph on an error; that the header's avatar is the one its actor has at each
step; and this pins the steps it went through, which of the header's parts each found
new, how many header elements each built, and how many it kept but took out of their
parents and put back.

A repaint that changes none of the header's inputs builds none of its nodes and moves
none. Before, it built every part again, about 30 elements on each tab switch and poll,
and a node replaced under the reader lost its focus, as a focused branch chip's copy
button did in headless Chrome. A kept node put back in the same task loses its focus too,
so `detached` counts them: placing the header's parts with `replaceChildren` built
nothing and detached all 42. A changed input builds its part again and only that part,
and moves no other. This checks node lifecycle and attributes, not paint;
explorations/performance-loop/design-rule-measurements.md has the measurements.
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
                # The header: the branches (mb-fon5) and the state and its ages (mb-4ydo) have
                # rows of their own, and the row of ages ends in the stack's slot (mb-646g), no
                # row in a strut of its own (mb-cf0l); the Diff summary's row ends it, built once
                # and kept by every repaint below (mb-pb35), with its pending placeholder, a
                # reveal and its block, built once at mount and kept across the waits (mb-onr2).
                # The author is the shell's identity, its avatar in a box of its own (mb-nunw).
                # The author's row's lead holds the sentence and the freshness note, its dot,
                # slot, and sizer (mb-ne91); the row of ages its ages, a span of their own so
                # they give way before Browse code's span, which this record has none of (B4 of
                # review B on #506). The View on GitHub button's corner is an empty span here:
                # the SDK draws the button (mb-4wqh), and this page has none to draw it with.
                # The size line's row, its placeholder, and the placeholder's block are three
                # (docs/design-system.md, "Change Size Line"). The page has no Refresh of its
                # own (mb-ablv), which a hidden button in the row of ages was. The readiness's
                # slot after the state's is thirty-one: the slot, its link, the verdict's chip,
                # the chip's glyph box and its drawing, the glyph alone for a narrow row and
                # its drawing, and a sizer for each of the server's twelve labels, each with a
                # glyph's box, so the slot is the chip's width (mb-io36, mb-omc0).
                "built": 85,
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
            # A refresh running builds and moves nothing.
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
                "rebuilt": ["branches", "ref menu triggers"],
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
                "built": 4,
                "detached": 0,
                "created": {"header": 1, "conversation": 1},
                "shown": 7,
            },
            # A merge changes the state and the actor: the title's icon, the badge, the
            # sentence, and the row of ages, which gains the merge's. The branches, the
            # badge's sizers, and the labels are kept.
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
                ],
                # The row of ages is its ages, a span of their own (B4 of review B on #506).
                "built": 17,
                "detached": 0,
                "created": {"header": 1, "conversation": 6},
                "shown": 7,
            },
        ],
        "loading": {"header": ["eager"], "conversation": ["lazy"]},
    }
