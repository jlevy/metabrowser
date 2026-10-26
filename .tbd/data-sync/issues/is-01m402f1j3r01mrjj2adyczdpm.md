---
type: is
id: is-01m402f1j3r01mrjj2adyczdpm
title: "Review and finish PR #262, then decide its independent landing"
kind: task
status: closed
priority: 1
version: 4
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
hold: null
hold_until: null
created_at: 2026-10-03T05:05:52.706Z
updated_at: 2026-10-26T15:26:57.341Z
started_at: 2026-10-03T05:20:08.007Z
closed_at: 2026-10-26T15:26:57.340Z
close_reason: "Decided: PR #262 is superseded, not merged. Its fix was integrated into codex/v012-loose-ends and landed on main in #268; main's CHANGELOG carries it as the 'Page lifecycle' section, including the review's P1 (a filtered tree is reconciled without inserting unfiltered folder rows) and the conditional catalog request. PR #262 should be closed on GitHub as superseded by #268. The one piece its review raised that code cannot settle - real-browser bfcache acceptance on a platform, not simulated lifecycle events - stays open in mb-tdmd."
resolution: null
duplicate_of: null
---
PR #262 is held outside the stack. Stack #260 is now merged; timing hold is satisfied. Still NOT ready as-is: P1 filtered Back landing unfilters tree; P2 redundant large snapshot/catalog parsing; lifecycle session gaps. Address the recorded P1/P2/P3 findings, run browser and focused regression coverage plus make verify and CI, then recommend landing separately. Do not merge until all blockers are resolved and merge authorization exists.

## Notes

Read PR #262 and its full held review. Main contains #260, satisfying the timing hold. Original #262 remains unsafe as-is. Isolated candidate on codex/v012-loose-ends incorporates its implementation and fixes filtered snapshot painting, explicit catalog ETag revalidation, unchanged snapshot parse avoidance, duplicate pagehide, late tasks, per-resume exception isolation, control rebuilds and live-log missing/truncation handling. Focused tests pass; full verification and real bfcache acceptance remain pending. The in-app browser reloads on Back and cannot establish bfcache correctness. No merge performed.
