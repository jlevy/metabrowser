---
type: is
id: is-01m7k1tfbjprkhwep83e9xbzhh
title: "A commit's author has a profile icon: the GitHub avatar where the GitHub plugin can resolve it without sending an author's email anywhere, else a neutral glyph in the same box"
kind: feature
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m7k1tdq21g63np2bkdr6fr29
created_at: 2026-11-16T20:47:18.385Z
updated_at: 2026-11-16T20:47:18.385Z
---
Resolve by commit oid in a GitHub-hosted repository (cached, bounded, off the paint path), through a documented SDK hook or route the core commit page reads; a local-only repository or unresolved commit shows the neutral glyph so the layout matches. Route parity row and golden per AGENTS.md.
