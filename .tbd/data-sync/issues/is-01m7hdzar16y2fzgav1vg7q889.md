---
type: is
id: is-01m7hdzar16y2fzgav1vg7q889
title: "PR #464 A7: carry the file's path into the Files reveal, or say the address is the source"
kind: bug
status: in_progress
priority: 3
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjm7dvfsqanbt2jtdyxfy
hold: null
hold_until: null
created_at: 2026-11-16T05:41:11.552Z
updated_at: 2026-11-16T05:41:19.733Z
started_at: 2026-11-16T05:41:19.731Z
---
Suggestion. Review A on PR #464 (https://github.com/jlevy/metabrowser/pull/464#pullrequestreview-5915452177). app.js:8966-8972 revealAddressedItem ignores path once the tab controller loads; app.js:8975-8982 addressedFilePath.
