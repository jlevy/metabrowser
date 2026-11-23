---
cwd: ../..
sandbox: false
---
# Guided PR step navigation

The production navigation waits for the cached PR, requests the selected step, and
discards late responses after a revision change or disposal.
An edited guide with fewer steps returns the reviewer to its first step.
A head GitHub reports past the cached record asks for the step again, and the server
answers a stale guide with its step, so a stale guide’s steps still move.

```console
$ node tests/dom/github-guided-pr-session.js
{
  "calls": [
    1,
    2,
    1,
    1,
    2,
    2,
    2,
    2,
    1,
    1,
    1
  ],
  "states": [
    "preview",
    "loading",
    "step 1 of 2",
    "loading",
    "step 2 of 2",
    "loading",
    "loading",
    "stale step 1 of 2",
    "loading",
    "stale step 2 of 2",
    "loading",
    "step 1 of 2",
    "loading",
    "step 2 of 2",
    "loading",
    "step 1 of 1",
    "loading",
    "updated",
    "loading"
  ]
}
? 0
```

# Guided PR on the pull page

The production page imports and mounts the guide only when its tab first paints, so
Conversation never reads it.
A pull request whose description has a guide opens on it, and Conversation, at its own
address, shows a card where the description had its guided-pr block.
The guide opens with the description’s card, as Conversation draws it, and each step is
a card headed as a guided review.
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

```console
$ node tests/dom/github-guided-pr-mount-behavior.js
[
  "the front page: guide mounted; asked step 1",
  "a stale guide's notice:  / This guide is out of date. / It was written for head bbbbbbb. The pull request is now at head ccccccc. / 12 commits since the guide: / ccccccc Count to <b>three</b>and 11 earlier commits / Steps 1 and 3 cite 1 file changed since: src/app.txt. The other steps still match; the changed ones are marked. Its author can update the guide's pins and ranges in the description.",
  "and its step, in a card: Guided review Step 1 of 3 · cites files changed since the guide; Step 1; This file changed after the guide was written. The excerpt is from the guide's revision.",
  "Conversation: guide not mounted; asked nothing",
  "its description's block: This description has a guided review. Open Guided PR",
  "its tab opens: guide mounted; asked step 1",
  "the guide's introduction: rendered",
  "step 1: Step 1; rows context one, del <i>two</i>, add three",
  "a path outside the comparison says: This path is not in the comparison.",
  "Open full diff: files src/app.txt",
  "left for Conversation with step 2 on its way: read aborted true; guide gone",
  "its tab again: asked step 1",
  "the page ends: read aborted true",
  "opened on its tab: asked step 1",
  "a newer record arrives with the read on its way: old read aborted true; asked step 1, step 1",
  "the new read's answer: Step 1",
  "a poll of the same record: asked step 1, step 1",
  "Guided PR opened and left before its import settled: guide not mounted; asked nothing",
  "the page ended before the import settled: asked nothing"
]
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
