---
type: is
id: is-01m7hdjrhmwvwrdnfxhz3bqckd
title: "PR #461 A1: rhythm's visible-space checks measure the commit row's box, not its text"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjhzg676034x3900gjvgd
hold: null
hold_until: null
created_at: 2026-11-16T05:34:19.699Z
updated_at: 2026-11-16T06:45:46.575Z
started_at: 2026-11-16T05:34:29.118Z
closed_at: 2026-11-16T06:45:46.574Z
close_reason: "Fixed in 5c3f961 (PR #461 A1): glyphs from text nodes; line-height:2 probe fails 26 checks. Disposition: https://github.com/jlevy/metabrowser/pull/461#issuecomment-6909470016"
resolution: null
duplicate_of: null
---
Medium. tests/dom/github-pull-timeline-chrome.mjs:323-331, :554-590. textTop/textEnd come from a Range over the whole row, whose client rects include flex items' border boxes, so they equal the row box; a line-height: 2 probe passes. Fix: union of per-text-node rects (TreeWalker SHOW_TEXT, width > 0), keep +/-1 px. PR #461, review A: https://github.com/jlevy/metabrowser/pull/461#pullrequestreview-5915431885
