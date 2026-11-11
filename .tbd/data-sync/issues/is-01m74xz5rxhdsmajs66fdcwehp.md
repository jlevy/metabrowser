---
type: is
id: is-01m74xz5rxhdsmajs66fdcwehp
title: "PR #346 B4: four new guards are not pinned by tests"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m74xysspjzemqnftp8y2rgb9
hold: null
hold_until: null
created_at: 2026-11-11T09:10:36.060Z
updated_at: 2026-11-11T09:34:00.146Z
started_at: 2026-11-11T09:10:46.455Z
closed_at: 2026-11-11T09:34:00.145Z
close_reason: "Fixed in 4318e80a: session steps for a retry that fails after a refusal (message null), a borrowing failure older than the record (sends), Changes opened during the page's own refresh (waits), and a reader's core preview before its first read (pending); comparisonHeld table in github-pull-manual-refresh-behavior.js. All four reviewer survivors (M1-M4) and 14 more mutations killed by attic/mutateB.sh (same mechanism as mutate.sh, base outputs refreshed for this head)."
resolution: null
duplicate_of: null
---
Low. Surviving mutations: comparisonRefusal = null in fetchComparison (:1504); the record-age test in comparisonHeld (:772-774); inFlightRefreshes === 0 in fetchSelectedChanges (:1520); fetchQueued's reader branch (:1191). Fix: add steps that kill each, proven with mutate.sh. Review: https://github.com/jlevy/metabrowser/pull/346#pullrequestreview-5856287761 (PR #346, review B, round 2).
