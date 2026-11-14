---
type: is
id: is-01m7865ebjwb4xwp2zhtthxmh0
title: "PR page: first-paint key cost that grows with the conversation, and first-paint span entry kinds"
kind: task
status: open
priority: 4
version: 2
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies: []
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-12T15:31:33.361Z
updated_at: 2026-11-14T18:46:00.723Z
---
Deferred from review B (B6, Low) on #369. The PR page's first paint does work per text and per section that grows with the conversation: each text is hashed over its whole length (renderedKey in pull-page.js), and each conversation section is keyed by the JSON of everything it shows (paintConversation), so the page keeps a second copy of its conversation's text as map keys. Review B measured mount at 7.75 against 5.18 ms at 300 comments and 19.2 against 11.34 ms at 1,000, browserless. Measure at 1,000 comments in a browser first. A fix keeps each text's key with its element and keys a section by identity plus a short digest, never a digest alone, which could reuse the wrong card on a collision. Also from the addressing pass (B5): the githubPull:firstPaintHold span's mode does not tell a landing from a page replacing another, so bound-hit rates cannot be split by entry kind; add the entry kind to the span.
