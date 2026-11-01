---
type: is
id: is-01m6c49bswke636nw42dzte5m0
title: An anchored address on a .jsonl file gets no highlight and no notice
kind: bug
status: open
priority: 4
version: 1
labels: []
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
created_at: 2026-11-01T18:00:00.571Z
updated_at: 2026-11-01T18:00:00.571Z
---
Found 2026-11-01, 2 of 2 in headless Chrome. JSONL has no Source view, so #L10 silently does nothing, where other files show a notice when an anchor cannot be honored.
