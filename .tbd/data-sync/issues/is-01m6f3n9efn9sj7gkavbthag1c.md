---
type: is
id: is-01m6f3n9efn9sj7gkavbthag1c
title: Back from a file loses the reader's place in a long pull request
kind: bug
status: in_progress
priority: 1
version: 2
delegate: claude-code@spud10
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-02T21:46:46.094Z
updated_at: 2026-11-02T21:47:04.605Z
started_at: 2026-11-02T21:47:04.603Z
---
Fixed in 7d5339ff on claude/v012-pr-review-workflows: history.state.pullPlace keeps block and offset. Measured in Chrome with the back/forward cache off on 34-file, 137-file, and 120-text pages. Not verified outside Chrome; Safari lacks scroll anchoring. Close when it merges.
