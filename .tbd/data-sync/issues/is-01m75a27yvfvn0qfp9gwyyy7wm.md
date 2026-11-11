---
type: is
id: is-01m75a27yvfvn0qfp9gwyyy7wm
title: "PR #351 A7: chooser focus target found by position; retry path never asserts chooser visible"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m75a1p5xdgrc0v0e1pxfpct9
hold: null
hold_until: null
created_at: 2026-11-11T12:41:59.514Z
updated_at: 2026-11-11T12:46:29.014Z
started_at: 2026-11-11T12:42:15.420Z
closed_at: 2026-11-11T12:46:29.013Z
close_reason: "fixed in 8b52a1b8: add() takes the disclosure (toggle) from diff-view.js, places the chooser after it and focuses it; behavior test with a leading decoy and retry-path chooser assertions"
resolution: null
duplicate_of: null
---
Low. diff-markdown.js:256, 423; tests/dom/diff-markdown-behavior.js:278-285. Pass toggle into add(); assert control.hidden false after a rejected load. PR #351, review A (https://github.com/jlevy/metabrowser/pull/351#pullrequestreview-5855489961).
