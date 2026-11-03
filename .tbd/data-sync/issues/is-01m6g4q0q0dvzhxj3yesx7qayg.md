---
type: is
id: is-01m6g4q0q0dvzhxj3yesx7qayg
title: "Diff view: report the file at the top of the pane, for the Pulls nav"
kind: feature
status: in_progress
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-03T07:24:25.696Z
updated_at: 2026-11-03T08:05:59.084Z
started_at: 2026-11-03T08:05:59.084Z
---
Requested by the Pulls tab's step 4 (mb-zx9q): 'the selection follows a reader who scrolls the diff by hand' needs the diff view to say which file is at the top of the pane, as an event or a fileAtTop() on the page handle beside scrollToFile and fileForPath (docs/large-content-rendering.md). Build it on PR 284's diff view after E1 (mb-ivvw) lands, because E1 changes which rows are drawn: the answer must name the file whose bar or reserved block is at the top, drawn or not, and must not force a draw. Pin it in tests/dom/diff-file-jump-session.js.

## Notes

2026-11-03: after E1 (9b624b3a), a ready file past the first screen settles lines one or two frames after a jump and can come back superseded (docs/large-content-rendering.md); a file-at-top answer has to work over held files too.
