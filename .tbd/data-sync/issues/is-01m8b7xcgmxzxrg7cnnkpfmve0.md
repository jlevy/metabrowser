---
type: is
id: is-01m8b7xcgmxzxrg7cnnkpfmve0
title: "Guided review: each file excerpt has the diff view's collapse chevron"
kind: feature
status: closed
priority: 1
version: 5
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-26T06:15:31.600Z
updated_at: 2026-11-26T08:43:39.949Z
started_at: 2026-11-26T06:15:36.371Z
closed_at: 2026-11-26T08:43:39.948Z
close_reason: "Merged in #872"
resolution: null
duplicate_of: null
---
Owner 2026-11-26: inside guided reviews, each file diff should toggle open/closed with a chevron exactly like the Changes tab's file cards, reusing the diff view's design components, not a second implementation.

## Notes

PR https://github.com/jlevy/metabrowser/pull/872 (branch claude/guide-diff-toggles), open, not merged. Both places build the bar from fileDisclosure in builtin_plugins/diff/diff-view.js: Changes' renderFileSection calls it, and the guide takes it as disclose on the diff plugin's guidePatchDrawer (after merging main's #871, whose mountExcerptDisclosure, bindFileDisclosure and fileChevron it replaces). Every guide card is built on it, a sentence card too; a plain bar remains only where the diff plugin did not load. One type, DiffFileDisclosure in static/types.d.ts. Chrome check (tests/dom/github-guided-review-fold-chrome.mjs) is the small one the owner asked for and covers a pull request's guide, not a stack's. Review A, A1 mechanism: a press on Changes' file missed when a Markdown file above it got its rendered layer (pull-rendered-diff) between the measurement and the press, moving every card under it down 43 px; the check now measures Changes only once no .diff-markdown-progress.mb-delayed-loading is in the document. Shown by hand with the answer held through Fetch.requestPaused: 3 of 3 missed without the wait, 3 of 3 passed with it; nothing committed for it. A second cause found under load: a bar measured while its chevron turned read a larger box; a bar is now measured only at rest. The earlier open question on fold lifetime is answered by mb-ez0x.
