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
    "step 2: loading"
  ]
}
? 0
```

# Guided Review on the pull page

The production page imports and mounts the guide only when its tab first paints, so
Conversation never reads it.
A pull request whose description has a guide opens on it, and Conversation, at its own
address, shows a card where the description had its guided-review block.
The guide opens on its overview, the description’s card as Conversation draws it, under
a list of its steps, and Next step goes to a step with no read, since the overview
already has its answer; each step is a card headed as a guided review.
A stale guide still shows its steps, read at the current head, under one warning and its
remedy at the top of the page, with the steps and files that changed since marked; the
commits, heads, merge bases, and paths behind it stay in the route’s answer.
A tab left while the import is on its way mounts nothing, and neither does a page that
ends there. A new record revision asks again for the step on screen and aborts the read
still on its way, whose late answer paints nothing, and a poll of the same record asks
for nothing. Leaving the tab, or ending the page, disposes the view and aborts its read.
A step is inserted as text, so markup in the guide stays markup, and each row is the
diff plugin’s, its code a span, which the shell’s highlighter, which takes `pre code`,
skips. Open full diff reaches the page’s own `openChangedFile`, which asks the route for
the file’s Changes address.
A guide stale only because GitHub reports a newer head says nothing, since the page’s
header already says new commits were pushed.
A guide whose head the local copy lacks marks no step, says some may not match, and says
in a reference’s place that its lines may have changed.
A guide whose cited files did not change says so in a quiet line.
A refused step keeps the step list, whose buttons survive the click that chose it, and
says why in the step’s place.
A core preview opens a guided pull request on its guide, which waits for the record, and
the record’s arrival reads the guide without changing tab.
On a guided front page, Guided Review’s link and key go to the page already shown, and
the description’s card on Conversation links the front page.

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
  "step 1: Step 1; rows context one, del <i>two</i>, add three",
  "a path outside the comparison says: This path is not in the comparison.",
  "Open full diff: files src/app.txt",
  "left for Conversation with step 2 on its way: read aborted true; guide gone",
  "its tab again: asked step 1",
  "the page ends: read aborted true",
  "opened on its tab: asked step 1",
  "a newer record arrives with the read on its way: old read aborted true; asked step 1, step 1",
  "the new read's answer: Overview",
  "a poll of the same record: asked step 1, step 1",
  "Guided Review opened and left before its import settled: guide not mounted; asked nothing",
  "the page ended before the import settled: asked nothing",
  "a guide behind a newer head on GitHub: none; > Overview | 1 Step 1 | 2 Step 2 | 3 Step 3",
  "a guide whose head this copy lacks: warning: This guide was written for an earlier version of this pull request, so some steps may not match it. Its author can update the guide.; > Overview | 1 Step 1 | 2 Step 2 | 3 Step 3",
  "and its step: Step 1; src/app.txt: no note | gone.txt: This file is no longer in the pull request's changes. | src/app.txt: These lines may have changed since the guide was written.",
  "a guide whose cited files did not change: quiet: This guide was written for an earlier version of this pull request, but the files it cites have not changed.",
  "a refused step: Step 2 of 3; Overview | 1 Step 1 | > 2 Step 2 | 3 Step 3; says This step could not be read. Choose it again to retry.",
  "chosen again: asked step 1, step 2, step 2",
  "and answered: Step 2 of 3; Step 2; says nothing",
  "back: Step 1 of 3; asked step 1, step 2, step 2",
  "a preview's front page: guide mounted; says The guide needs the full pull request.; asked nothing",
  "its record arrives: guide mounted; asked step 1",
  "the guided front page: Guided Review links /pull/7, Conversation /pull/7/conversation; its key opens nothing",
  "from Conversation, the description's card links /pull/7"
]
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
