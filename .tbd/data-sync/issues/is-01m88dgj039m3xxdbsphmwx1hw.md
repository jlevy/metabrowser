---
type: is
id: is-01m88dgj039m3xxdbsphmwx1hw
title: "PR #811 A1: switching Full and Concise in a long file puts the reader up to a chunk from where they were"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m88dfdf96exb192c9gb46hfz
hold: null
hold_until: null
created_at: 2026-11-25T03:55:39.393Z
updated_at: 2026-11-25T03:59:29.537Z
started_at: 2026-11-25T03:59:29.536Z
---
Medium. diff-view.js drawnRows/find (3466-3484), drawnBlock (3539-3557); diff-markdown.js paint (1309-1323), fillRegion (1344-1372). After a view switch the anchor block is undrawn; find() falls back to the chunk spacer, and once the spacer mounts the chunk's first block takes the reader's place. Review A of PR #811: https://github.com/jlevy/metabrowser/pull/811#pullrequestreview-6051579395
