---
type: is
id: is-01m7k1tfbjprkhwep83e9xbzhh
title: "A commit's author has a profile icon: the GitHub avatar where the GitHub plugin can resolve it without sending an author's email anywhere, else a neutral glyph in the same box"
kind: feature
status: in_progress
priority: 1
version: 4
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7k1tdq21g63np2bkdr6fr29
child_order_hints:
  - is-01m7kbrbabfqkxv95e340xg8tj
hold: null
hold_until: null
created_at: 2026-11-16T20:47:18.385Z
updated_at: 2026-11-20T17:03:18.656Z
started_at: 2026-11-16T21:37:36.646Z
---
Resolve by commit oid in a GitHub-hosted repository (cached, bounded, off the paint path), through a documented SDK hook or route the core commit page reads; a local-only repository or unresolved commit shows the neutral glyph so the layout matches. Route parity row and golden per AGENTS.md.

## Notes

2026-11-20 audit: moved from in_progress back to open. No open PR and no active session since 2026-11-16. The glyph part merged in PR #487 (actorIdentity). The GitHub avatar resolved by commit oid is the child mb-rlp4 and is not started.
