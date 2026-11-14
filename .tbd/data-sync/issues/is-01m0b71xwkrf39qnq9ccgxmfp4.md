---
type: is
id: is-01m0b71xwkrf39qnq9ccgxmfp4
title: Anchor PR review threads in the Changes diff
kind: feature
status: deferred
priority: 3
version: 12
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels: []
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-08-18T19:54:57.298Z
updated_at: 2026-11-14T18:46:34.691Z
---
Deferred by the user's 2026-09-23 thin-mirror decisions (inline thread anchoring). Today Conversation lists each review comment with its file, line, and diff hunk, and Changes shows no threads. Place review threads at their lines in the Changes diff, with explicit outdated, resolved, and unmappable states: map a thread only when its commit and line context still match the comparison shown, and otherwise keep its original anchor without inventing a line. Cover file-level, single-line, and range comments, a deleted file, and a force-pushed head. The earlier Hosted Review Format design (ReviewThread, ReviewAnchor; plan-2026-08-27 Phase 4C) was removed in #246 and is background only. Re-plan against the thin mirror and the Pulls tab plan before starting.

## Notes

2026-09-30: deferred by the user's 2026-09-23 decision (thin-mirror plan, Decisions). Not part of v0.12; does not gate mb-n2ro. The design text predates the thin mirror (provider store, auth contexts, leases and SDK panels are retired); re-plan against the thin-mirror plan before starting.

2026-11-14 audit: rewritten in thin-mirror terms; the Hosted Review Format it first described was removed in #246 and survives only on draft #247. mb-1wk1's inventory line that says this bead is not the one for inline anchoring should be updated to point here.
