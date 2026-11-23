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
$ node tests/dom/github-guided-pr-session.js
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
address, shows a card where the description had its guided-pr block.
The guide opens on its overview, the description’s card as Conversation draws it, under
a list of its steps, and Next step goes to a step with no read, since the overview
already has its answer; each step is a card headed as a guided review.
A stale guide still shows its steps, under a notice at the top of the page that names
the revision it was written for, the commits since, and the steps that cite changed
files. A tab left while the import is on its way mounts nothing, and neither does a page
that ends there. A new record revision asks again for the step on screen and aborts the
read still on its way, whose late answer paints nothing, and a poll of the same record
asks for nothing. Leaving the tab, or ending the page, disposes the view and aborts its
read. A step is inserted as text, so markup in the guide stays markup, and each row is
the diff plugin’s, its code a span, which the shell’s highlighter, which takes
`pre code`, skips. Open full diff reaches the page’s own `openChangedFile`, which asks
the route for the file’s Changes address.
A guide stale only because GitHub reports a newer head says it may be out of date, and
that whether its steps match the newest commits is unknown.
Commits the server counted but could not list are counted.
A refused step keeps the step list, whose buttons survive the click that chose it, and
says why in the step’s place.
A core preview opens a guided pull request on its guide, which waits for the record, and
the record’s arrival reads the guide without changing tab.
On a guided front page, Guided Review’s link and key go to the page already shown, and
the description’s card on Conversation links the front page.

```console
$ node tests/dom/github-guided-pr-mount-behavior.js
[
  "the front page: guide mounted; asked step 1",
  "a stale guide opens on: Overview; > Overview | 1 Step 1 changed since the guide | 2 Step 2 | 3 Step 3 changed since the guide",
  "a stale guide's notice:  / This guide is out of date. / It was written for head bbbbbbb. The pull request is now at head ccccccc. / 12 commits since the guide: / ccccccc Count to <b>three</b>and 11 earlier commits / Steps 1 and 3 cite 1 file changed since: src/app.txt. The other steps still match; the changed ones are marked. Its author can update the guide's pins and ranges in the description.",
  "and its step, in a card: Guided ReviewStep 1 of 3 · cites files changed since the guide; Step 1; This file changed after the guide was written. The excerpt is from the guide's revision.",
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
  "a guide behind a newer head on GitHub: This guide may be out of date. / GitHub reports a newer head than this copy of the pull request. Reload it to compare the guide with the newest commits. / Whether its steps still match the newest commits is unknown.; > Overview | 1 Step 1 | 2 Step 2 | 3 Step 3",
  "commits counted and not listed: This guide is out of date. / It was written for head bbbbbbb. The pull request is now at head ccccccc. / 3 commits since the guide. / None of the files its steps cite changed, so every step still matches. Its author can update the guide's pins and ranges in the description.",
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
