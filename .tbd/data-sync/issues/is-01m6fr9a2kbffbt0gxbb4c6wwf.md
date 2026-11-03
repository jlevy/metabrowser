---
type: is
id: is-01m6fr9a2kbffbt0gxbb4c6wwf
title: "PR #284 Qodo: early catalog opens can miss files (held feed drops changes; release fetch during indexing is partial)"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6fr829v5p0bx9wm4rr3z5wj
hold: null
hold_until: null
created_at: 2026-11-03T03:47:13.618Z
updated_at: 2026-11-03T03:52:31.427Z
started_at: 2026-11-03T03:47:30.638Z
closed_at: 2026-11-03T03:52:31.426Z
close_reason: "rebutted at f59cebd2: a feed is held only before its first fetch, so the release fetch is the whole membership so far and a change dropped while held names a file the index already holds; later changes are not held; driven in tests/dom/catalog-feed-behavior.js"
resolution: null
duplicate_of: null
---
Medium (bot). src/metabrowser/static/catalog-feed.js:438-441, 457-460, 515-529. https://github.com/jlevy/metabrowser/pull/284#discussion_r4450318502. Review D lists it as a false positive. Evaluated: a held feed has never fetched, so the fetch its release starts is the whole membership so far, and a change dropped while held names a file the index already holds; later changes are not held. Driven in tests/dom/catalog-feed-behavior.js.
