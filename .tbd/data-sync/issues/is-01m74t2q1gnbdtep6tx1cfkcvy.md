---
type: is
id: is-01m74t2q1gnbdtep6tx1cfkcvy
title: "PR #346 A7: missing sessions for the new Changes state machine and a mislabeled golden table"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m74t21pvwps4wh189z73rspr
created_at: 2026-11-11T08:02:37.743Z
updated_at: 2026-11-11T08:21:21.423Z
closed_at: 2026-11-11T08:21:21.422Z
close_reason: "Fixed in 9c625f4e: the checkout comparison session adds the cold direct visit, its refused variant, unowned Changes, read errors, refusals and held outcomes; github-pull-pending-file-behavior.js adds a real-handle settledWalkJumpsOnce invariant; github-pull-page-session.js derives the no_store and checkout rows with tab files and comparisonAttempted (golden output unchanged)."
resolution: null
duplicate_of: null
---
Low. No session for a cold direct /pull/N/files visit to one automatic comparison POST or its refused variant; none for Changes without route ownership; settled-walk no-double-jump pinned only by a fake handle (tests/dom/navigation-route-behavior.js:579-592); tests/dom/github-pull-page-session.js:1104-1121 and :1141-1146 derive the no_store row with tab ''. Fix: add the sessions, a real-handle invariant, and derive or relabel the rows. Review: https://github.com/jlevy/metabrowser/pull/346#pullrequestreview-5855482052 (PR #346, review A, round 1).
