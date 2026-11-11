---
type: is
id: is-01m75a28bg9x2ezwyyv88dbvrc
title: "PR #351 A8: a hidden chooser leaves the bar in the Markdown layout"
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
created_at: 2026-11-11T12:41:59.919Z
updated_at: 2026-11-11T12:46:29.330Z
started_at: 2026-11-11T12:42:15.752Z
closed_at: 2026-11-11T12:46:29.329Z
close_reason: "fixed in 8b52a1b8: drawControl toggles diff-file-bar-markdown and hides progress with the chooser; headless Chrome 41px wrapped before, 24px one line after"
resolution: null
duplicate_of: null
---
Low. diff-markdown.js:424, diff/styles.css:412-418. Toggle diff-file-bar-markdown with the chooser; check in headless Chrome. PR #351, review A (https://github.com/jlevy/metabrowser/pull/351#pullrequestreview-5855489961).
