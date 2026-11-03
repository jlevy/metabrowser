---
type: is
id: is-01m6g4q0q0dvzhxj3yesx7qayg
title: "Diff view: report the file at the top of the pane, for the Pulls nav"
kind: feature
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-03T07:24:25.696Z
updated_at: 2026-11-03T07:24:25.696Z
---
Requested by the Pulls tab's step 4 (mb-zx9q): 'the selection follows a reader who scrolls the diff by hand' needs the diff view to say which file is at the top of the pane, as an event or a fileAtTop() on the page handle beside scrollToFile and fileForPath (docs/large-content-rendering.md). Build it on PR 284's diff view after E1 (mb-ivvw) lands, because E1 changes which rows are drawn: the answer must name the file whose bar or reserved block is at the top, drawn or not, and must not force a draw. Pin it in tests/dom/diff-file-jump-session.js.
