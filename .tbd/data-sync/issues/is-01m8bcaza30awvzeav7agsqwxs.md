---
type: is
id: is-01m8bcaza30awvzeav7agsqwxs
title: "Changes tab: content shifts 43 px when a Markdown layer lands after the first-screen hold"
kind: bug
status: in_progress
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-26T07:32:51.138Z
updated_at: 2026-11-26T09:04:29.118Z
started_at: 2026-11-26T08:20:29.692Z
---
Review A of #872, A2: pull-page.js:149 shows the diff after CHANGES_FIRST_SCREEN_MS whether or not a rendered Markdown layer is in; when it lands, its card grows (75 to 118 px in the stand-in) and everything below moves, so a reader's press can miss. Hold its height or reserve room so nothing moves.

## Notes

PR https://github.com/jlevy/metabrowser/pull/878 (open, not merged). No room can be reserved for a rendered document before its answer, so a file near the first screen keeps waiting past the bound with Source hidden (release() only settles firstScreen), its section carries WAITING_CLASS, and one style rule keeps everything after it in the diff out of sight. Applies to every host of the diff view. Measured in headless Chrome with the rendered answer held 1.5 s on pull 7's Changes: page shown at 271 ms with docs/new.md's bar alone (31 px) and src/app.txt unseen; at 1,657 ms the body drew (118 px) and src/app.txt first showed at its final top. Guarded by the Markdown session's invariant and a check added to tests/dom/diff-file-bar-chrome.mjs.
