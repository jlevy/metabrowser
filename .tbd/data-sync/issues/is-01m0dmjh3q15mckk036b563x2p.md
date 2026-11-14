---
type: is
id: is-01m0dmjh3q15mckk036b563x2p
title: "Diff view: mark file as viewed"
kind: feature
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-08-19T18:29:41.613Z
updated_at: 2026-11-14T18:45:11.246Z
---
GitHub-parity review flow on the per-file bar: a viewed toggle that collapses the section and dims the bar, so a reader can walk a long diff hiding what they have finished. State keyed by comparison_id plus file id. The storage decision (localStorage or server) is part of the work. Viewed state must invalidate when the comparison goes stale (the generation-token rule). Builds on the collapsible per-file bar in builtin_plugins/diff/diff-view.js. Deferred by review: toggle first, viewed later. This is the 'local viewed state' piece of mb-k0x3's review surface.
