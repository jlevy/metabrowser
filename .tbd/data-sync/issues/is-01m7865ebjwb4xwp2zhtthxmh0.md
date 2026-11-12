---
type: is
id: is-01m7865ebjwb4xwp2zhtthxmh0
title: "PR page: kept conversation sections keyed by digest alone, and first-paint span modes"
kind: task
status: open
priority: 4
version: 1
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies: []
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-12T15:31:33.361Z
updated_at: 2026-11-12T15:31:33.361Z
---
Deferred from review B (B6) on jlevy/metabrowser#369: kept sections are keyed by content digest only, so a hash collision could reuse a node, and their cost is measured only browserless; measure in a browser and key by identity plus digest if cheap. Also from the addressing pass: the githubPull:firstPaintHold span's mode does not tell a landing from a page replacing another, so bound-hit rates cannot be split by entry kind; add the entry kind to the span.
