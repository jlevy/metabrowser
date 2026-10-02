---
type: is
id: is-01m3zcr4trbfndm6fp8jr10q8d
title: Keep the 0.11.0-differential harnesses, and make their live counters deterministic
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels: []
dependencies: []
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
created_at: 2026-10-02T22:46:22.291Z
updated_at: 2026-10-02T22:46:22.291Z
---
The three landing-gate harnesses (evidence audit, data and modes, browser) live outside the repository in metabrowser-landing-gate-evidence/ beside the checkout. Decide whether they belong under explorations/ for the next release. Known harness issues: with --jobs 6 the data harness reported events.connections (2 against 0 in POST /api/diagnostics/pending-tallies and the shutdown log) and /_debug/inventory work counters as differences, and they vanish at --jobs 4, so they are live counters that need a normalization rule; the 14fcdb85 run made 20,095 comparisons where the f62c16b1 run made 20,234 and the reason is not established; the audit's two hover-prefetch rows and one size row are stale classifications of behavior #264 restored; 33 new test hunks from #264 and #267 are unclassified (27 are pure additions).
