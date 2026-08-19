---
type: is
id: is-01m0dmjh3q15mckk036b563x2p
title: "Diff view: mark file as viewed"
kind: feature
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-08-19T18:29:41.613Z
updated_at: 2026-08-19T18:29:41.613Z
---
GitHub-parity review flow on the per-file bar: a viewed toggle that collapses the section and dims the bar, so a reader can walk a long diff hiding what they have finished. State keyed by comparison_id + file id; storage decision (localStorage vs server) is part of the work; viewed state must invalidate when the comparison goes stale (the generation-token rule). Builds on the collapsible per-file bar (landing on claude/diff-core). Explicitly deferred by review: toggle first, viewed later.
