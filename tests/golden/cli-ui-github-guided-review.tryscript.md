---
cwd: ../..
sandbox: false
---
# Guided Review step navigation

The production navigation waits for the cached PR, opens on the overview, step 0, with
the answer for step 1, whose titles list the guide, and requests each other step once
per record revision: a step already read, the first one included, shows with no request.
A step chosen from the list goes straight to it, and no move passes either end.
It discards late responses after a revision change or disposal.
An edited guide with fewer steps returns the reviewer to its first step.
A head GitHub reports past the cached record asks for the step again, and the server
answers a stale guide with its step, so a stale guide’s steps still move.
A step whose read is refused or fails keeps the guide’s steps, so the reader can still
move, and it is read again when chosen again, the one on screen too.
An answer whose note a busy renderer, or one that could not start, refused is not kept,
so its step is read again when chosen again; a note refused past the deadline keeps its
answer. A stack’s guide, under `stack`, has no overview: it opens on step 1, and no move
goes before it. A step read while the stack is pending, or cannot be paired, is refused
before the guide is found, with no revision: that step’s refusal, never a new guide, so
the steps stay and the step is read again when chosen again.
Read through the document’s keep (`guide-reads.js`), as the page reads, a shown step’s
neighbors are read ahead, a move to one shows it at once with no loading state, and a
guide mounted again over the same keep moves through what it kept, reading nothing; a
new revision shows none of what the old one kept.
Under `head`, a head GitHub reports past the record, with the record unchanged, shows
nothing the keep read before: the step is read again, and that answer is kept for the
moved head. An answer that cites a pull request this copy has not read is never kept, so
the step is read again, and kept once what it cites is read.

```console
$ node tests/dom/github-guided-review-session.js
{
  "calls": [
    1,
    2,
    3,
    1,
    2,
    2,
    3,
    3,
    1,
    1,
    1,
    1,
    2,
    2,
    2,
    2,
    1,
    2,
    2,
    2
  ],
  "states": [
    "overview: preview",
    "overview: loading",
    "overview: step 1 of 3",
    "step 1: step 1 of 3",
    "step 2: loading",
    "step 2: step 2 of 3",
    "overview: step 1 of 3",
    "step 2: step 2 of 3",
    "step 3: loading",
    "step 3: step 3 of 3",
    "step 1: step 1 of 3",
    "step 1: loading",
    "step 1: stale step 1 of 3",
    "step 2: loading",
    "step 1: stale step 1 of 3",
    "step 2: loading",
    "step 2: stale step 2 of 3",
    "step 3: loading",
    "step 3: stale step 3 of 3",
    "step 3: loading",
    "step 1: step 1 of 3",
    "step 1: loading",
    "step 1: updated",
    "step 1: loading",
    "step 1: invalid",
    "step 1: loading",
    "step 1: step 1 of 3",
    "step 2: loading",
    "step 2: comparison_unavailable",
    "step 2: loading",
    "step 2: error",
    "step 1: step 1 of 3",
    "step 2: loading",
    "step 2: step 2 of 3",
    "step 2: loading",
    "step 2: step 2 of 3",
    "step 1: loading",
    "step 1: step 1 of 3",
    "step 2: loading",
    "step 2: step 2 of 3",
    "step 1: step 1 of 3",
    "step 2: loading",
    "step 2: step 2 of 3",
    "step 1: step 1 of 3",
    "step 2: step 2 of 3",
    "step 2: loading"
  ],
  "stack": {
    "calls": [
      1,
      2,
      3,
      3,
      3
    ],
    "states": [
      "step 1: loading",
      "step 1: step 1 of 3",
      "step 2: loading",
      "step 2: step 2 of 3",
      "step 1: step 1 of 3",
      "step 3: loading",
      "step 3: not_cached",
      "step 2: step 2 of 3",
      "step 3: loading",
      "step 3: stack_unavailable",
      "step 1: step 1 of 3",
      "step 3: loading",
      "step 3: step 3 of 3"
    ]
  },
  "moved": {
    "calls": [
      1,
      2,
      3,
      2,
      2
    ],
    "states": [
      "step 1: loading, 0 steps",
      "step 1: step 1 of 3",
      "step 2: loading, 3 steps",
      "step 2: stack_moved, 3 steps",
      "step 1: step 1 of 3",
      "step 3: loading, 3 steps",
      "step 3: stack_moved, 3 steps",
      "step 2: loading, 3 steps",
      "step 2: step 2 of 3",
      "step 2: stack_moved, 0 steps",
      "step 2: loading, 0 steps",
      "step 2: step 2 of 3"
    ]
  },
  "ahead": {
    "read": [
      1,
      2,
      3,
      2,
      3,
      1
    ],
    "states": [
      "first mount overview: loading (read )",
      "first mount overview: step 1 (read 1)",
      "first mount step 1: step 1 (read 1 2)",
      "first mount step 2: step 2 (read 1 2)",
      "first mount step 3: step 3 (read 1 2 3)",
      "mounted again overview: step 1 (read 1 2 3)",
      "mounted again step 3: step 3 (read 1 2 3)",
      "mounted again step 2: step 2 (read 1 2 3)",
      "mounted again step 2: loading (read 1 2 3)",
      "mounted again step 2: step 2 (read 1 2 3 2)"
    ]
  },
  "head": {
    "read": [
      "1",
      "1",
      "1",
      "1"
    ],
    "states": [
      "before the push overview: loading (read )",
      "before the push overview: ready step 1 (read 1)",
      "after the push overview: ready step 1 (read 1)",
      "after the push overview: loading (read 1)",
      "after the push overview: stale step 1 (read 1 1)",
      "mounted again overview: stale step 1 (read 1 1)",
      "citing #9 overview: loading (read 1 1)",
      "citing #9 overview: ready step 1, citing not_cached (read 1 1 1)",
      "#9 opened overview: loading (read 1 1 1)",
      "#9 opened overview: ready step 1, citing ready (read 1 1 1 1)",
      "back again overview: ready step 1, citing ready (read 1 1 1 1)"
    ]
  }
}
? 0
```

# Guided Review on the pull page

The production page imports and mounts the guide only when its tab first paints, and
asks for its first step as the import starts; Conversation reads the guide only when the
page is idle, which this session never is.
A pull request whose description has a guide opens on it, and Conversation, at its own
address, shows a card where the description had its guided-review block.
The guide opens on its overview, the description’s card as Conversation draws it, under
a list of its steps, and Next step goes to a step with no read, since the overview
already has its answer; each step is a card headed as a guided review.
A stale guide still shows its steps, read at the current head, under one warning and its
remedy at the top of the page, with the steps and files that changed since marked; the
commits, heads, merge bases, and paths behind it stay in the route’s answer.
A tab left while the import is on its way mounts nothing, and neither does a page that
ends there, though its first step was asked for.
A new record revision asks again for the step on screen and drops the read still on its
way, whose late answer paints nothing, and a poll of the same record asks for nothing.
Next leaves the step shown, its diff with it, until the next one is in hand.
Leaving the tab disposes the view; a read on its way goes on for the document’s keep,
and the tab opened again shows the overview and the steps read before at once, reading
nothing. A step’s title is inserted as text, so markup in it stays markup, and so is a
note whose render was refused, and each row is the diff plugin’s, its code a span, which
the shell’s highlighter, which takes `pre code`, skips.
Open full diff reaches the page’s own `openChangedFile`, which asks the route for the
file’s Changes address.
A guide stale only because GitHub reports a newer head says nothing, since the page’s
header already says new commits were pushed.
A guide whose head the local copy lacks marks no step and says some may not match; above
an excerpt it says the file may have changed, and in a reference’s place that its lines
may have. A guide whose cited files did not change says so in a quiet line.
A step can cite past its pull request, and one that cites a pull request this copy has
not read is read again when the reader moves to it, the overview shown meanwhile:
another pull request is a row as the stack menu lists a member, its title, its place in
a stack, bare in the guide’s own stack and naming any other, with its stack in its tip,
its number, and its author, and goes to that pull request’s page, and one this copy has
not read is named by its number; a file of another pull request is drawn under a bar
that names that pull request, whose Open full diff opens the file in that pull request’s
Changes, and one that is not loaded here says how to load it; a commit is a row of its
short ID, its subject, and when it was committed, a plain link to the commit, one the
store lacks says it is unavailable, and one this checkout cannot open says so before
when it was committed, which ends the row.
None of them is marked changed, even when the guide is stale and a path another pull
request’s reference names changed.
A guide whose merge base alone moved is out of date too: a step that cites a file
changed on the base side is marked, and when none is, a quiet line says so.
A refused step keeps the step list, whose buttons survive the click that chose it, and
says why in the step’s place.
A row outside any group starts on the edge a group’s heading starts on: the overview’s,
which has no number, and each step’s, numbered in a column as wide as the widest of
their numbers, two digits for a guide of twelve steps in no group, and one for a guide
whose only such step is its first, however far its group’s steps run.
A guide in groups lists each group as a heading, with no number and nothing to press,
above its steps, which keep their numbers through the groups; a step outside a group
sits between them. A step’s card names its group before its place, a group’s note shows
above its first step alone, and the list keeps its buttons and its changed marks as the
reader moves. A note the route rendered, a step’s or its group’s, is handed to the
description’s allowlist against the pull request’s page, and what it builds is set in
the step’s prose after the title, or, for a group, in a KPress article above the card.
A note whose render was refused shows as typed with the line a description’s refusal
says under it, in a warning, and a step whose group’s note met a busy renderer is read
again when the reader moves to it.
Without the allowlist, a rendered note shows as typed, with nothing said beside it.
A core preview opens a guided pull request on its guide, which waits for the record, and
the record’s arrival reads the guide without changing tab.
On a guided front page, Guided Review’s link and key go to the page already shown, and
the description’s card on Conversation links the front page.
A description that carries a stack’s guide, a `stack-review` block, gets a card on
Conversation that says it has a stack guide and links each stack the pull request is a
member of, or none while it is in no stack this copy knows, and no Guided Review of its
own.
A stack’s guide, as the stack’s page mounts it, has no introduction and no overview:
it opens on its first step, asks the route by `stack=`, goes no further back, and says
of the stack what a pull request’s guide says of the pull request.
A step’s file is a card that folds as a file’s does in Changes, by the diff plugin’s own
bar and chevron, which the guide’s drawer hands the card: it starts open, a press on its
bar or its trigger folds it and opens it, and folding keeps the rows the diff drew.
A card that holds a sentence in a diff’s place is built on the same bar and folds too.
A file the reader folds stays folded for the document, as the step answers are kept: the
guide mounted again on its tab draws it folded, and so does a step left and come back
to, and one opened again stays open.
The folds are a guide’s at one head, so the same guide read at a new head, whose files
may differ, starts with none.

```console
$ node tests/dom/github-guided-review-mount-behavior.js
[
  "the front page: guide mounted; asked step 1",
  "a stale guide opens on: Overview; > Overview | 1 Step 1 changed | 2 Step 2 | 3 Step 3 changed",
  "a stale guide's notice: warning: This guide was written for an earlier version of this pull request, so steps marked changed may not match it. Its author can update the guide.",
  "and its step, in a card: Guided ReviewStep 1 of 3 · changed; Step 1; src/app.txt: This file changed after the guide was written. | gone.txt: This file is no longer in the pull request's changes.",
  "Conversation: guide not mounted; asked nothing",
  "its description's block: This description has a guided review. Open Guided Review",
  "its tab opens: guide mounted; asked step 1",
  "the guide's overview: rendered",
  "the guide opens on: Overview; > Overview | 1 Step 1 | 2 Step 2; step shown null",
  "its rows outside a group: Overview, no number | 1 | 2; column 1",
  "step 1: Step 1; rows context one, del <i>two</i>, add three",
  "a path outside the comparison says: This path is not in the comparison.",
  "Open full diff: files src/app.txt",
  "step 1's file: open; its bar pressed: folded, 3 rows kept; its trigger pressed: open; a card with no diff, its bar pressed: folded",
  "Next with step 2 on its way: step shown Step 1",
  "left for Conversation with step 2 on its way: read aborted false; guide gone",
  "its tab again: Overview; asked nothing",
  "and its kept steps at once: step shown Step 2; asked nothing",
  "step 1's file, left folded: back on the tab folded; after Next and Back folded; opened, then Next and Back open",
  "a fold kept for a guide at its head: the same head true, another guide false, a new head false, the first head again false",
  "opened on its tab: asked step 1",
  "a newer record arrives with the read on its way: old read aborted false; asked step 1, step 1",
  "the new read's answer: Overview",
  "a poll of the same record: asked step 1, step 1",
  "Guided Review opened and left before its import settled: guide not mounted; asked step 1",
  "the page ended before the import settled: asked step 1",
  "a guide behind a newer head on GitHub: none; > Overview | 1 Step 1 | 2 Step 2 | 3 Step 3",
  "a guide whose head this copy lacks: warning: This guide was written for an earlier version of this pull request, so some steps may not match it. Its author can update the guide.; > Overview | 1 Step 1 | 2 Step 2 | 3 Step 3",
  "and its step: Step 1; src/app.txt: This file may have changed since the guide was written. | gone.txt: This path is not in the comparison. | src/app.txt: These lines may have changed since the guide was written.",
  "moving to it reads it again: 1 read, the overview shown meanwhile",
  "a step past its pull request: Guided Review | Step 1 of 3; row to /pull/8: Say <b>more</b> 1/3 · #8 · maintainer (tip: Stack #71, position 1 of 3) | row to /pull/50: Work item 50 300 2/2 · #50 · contributor (tip: Stack #300, position 2 of 2) | row to /pull/2000: Pull request #2000 #2000 | #9 src/app.txt: no note | #12 docs/plan.md: This pull request has not been loaded here. Open it to load its changes. | row to /commit/cccccccccccccccccccccccccccccccccccccccc: ccccccc Count <i>to</i> two committed now | row: eeeeeee This commit is unavailable. | row: fffffff Fetched with its pull request Not in this checkout. | row: ddddddd Fetched and dated Not in this checkout. committed now",
  "its pull request row, then its other pull request's Open full diff, open: #8 front page; #9 files src/app.txt",
  "a guide whose cited files did not change: quiet: This guide was written for an earlier version of this pull request, but the files it cites have not changed.",
  "a guide whose merge base alone moved: warning: This guide was written for an earlier version of this pull request, so steps marked changed may not match it. Its author can update the guide.; > Overview | 1 Step 1 changed | 2 Step 2 | 3 Step 3",
  "and when none of its files changed: quiet: This guide was written for an earlier version of this pull request, but the files it cites have not changed.",
  "a refused step: Step 2 of 3; Overview | 1 Step 1 | > 2 Step 2 | 3 Step 3; says This step could not be read. Choose it again to retry.",
  "chosen again: asked step 1, step 2, step 2",
  "and answered: Step 2 of 3; Step 2; says nothing",
  "back: Step 1 of 3; asked step 1, step 2, step 2",
  "a guide of twelve steps, its rows outside a group: Overview, no number | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12; column 2",
  "a step, then a group of ten, its rows outside a group: Overview, no number | 1; column 1",
  "a guide in groups opens on: Overview; > Overview | [Decisions] | 1 Step 1 | 2 Step 2 changed | 3 Step 3 | [Testing] | 4 Step 4 changed",
  "its rows outside a group: Overview, no number | 3; column 1",
  "its first step: Guided Review | Decisions · Step 1 of 4; under the group's note: Read these first.\nEach says why.",
  "its second: Guided Review | Decisions · Step 2 of 4 · changed",
  "step 3: Guided Review | Step 3 of 4; Overview | [Decisions] | 1 Step 1 | 2 Step 2 changed | > 3 Step 3 | [Testing] | 4 Step 4 changed",
  "step 4: Guided Review | Testing · Step 4 of 4 · changed; Overview | [Decisions] | 1 Step 1 | 2 Step 2 changed | 3 Step 3 | [Testing] | > 4 Step 4 changed",
  "asked: step 1, step 2, step 3, step 4",
  "a rendered note: title Step <b>1</b>; blocks span.inert-rebuilt: <p>Check <b>this</b> first.</p>; group's note <p>Read <em>these</em>.</p>; allowlist asked <p>Check <b>this</b> first.</p> at https://github.com/octo/demo/pull/7, <p>Read <em>these</em>.</p> at https://github.com/octo/demo/pull/7",
  "refused notes: asked step 1, step 1; group's note Read *these*. | warning: This text could not be rendered, so it is shown as written. Reload the page to try again.; step's note Check <b>this</b> first.\nThen that. | warning: This text took too long to render, so it is shown as written.; allowlist asked 0",
  "no allowlist: step's note Check <b>this</b> first.\nThen that.; group's note Read *these*.; console metabrowser github: the guide's notes will show as typed",
  "a preview's front page: guide mounted; says The guide needs the full pull request.; asked nothing",
  "its record arrives: guide mounted; asked step 1",
  "the guided front page: Guided Review links /pull/7, Conversation /pull/7/conversation; its key opens nothing",
  "from Conversation, the description's card links /pull/7",
  "a description with a stack's guide: \"This description has a stack guide, read on its stack's page. Open Stack #286\" links Open Stack #286 (/stack/286)",
  "one in no stack this copy knows: \"This description has a stack guide, read on its stack's page.\"",
  "a stack's guide opens on Step 1 of 2, lists 2 steps and no overview, asks stack=70&step=1, and goes no further back; it says \"This guide was written for an earlier version of this stack, so steps marked changed may not match it. Its author can update the guide.\" and of a file \"This file changed after the guide was written. | This file is no longer in the stack's changes.\"",
  "a stack step refused while a member is fetched says \"This stack's pull requests are still being fetched.\", one whose carrier moved past the comparison drawn says \"This stack has moved since its comparison was drawn. Show the new comparison to read its guide.\", and a guide refused whole names no place and says \"The stack-review block cannot be read.\""
]
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
