---
type: is
id: is-01m74xz507xg41wgcmnxkv5g0z
title: "PR #346 B2: Fetch/Retry changes painted while the page's own stale refresh is in flight, and a click is ignored"
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
created_at: 2026-11-11T09:10:35.270Z
updated_at: 2026-11-11T09:33:59.470Z
started_at: 2026-11-11T09:10:45.815Z
closed_at: 2026-11-11T09:33:59.470Z
close_reason: "Fixed in 4318e80a: model() hides Retry/Fetch changes while inFlightRefreshes > 0 and askForRefresh repaints when any refresh starts. Confirmed by the session's 'Changes without its address paints no Fetch changes during the page's own refresh' (button painted before the stale ask fires); mutations M7, M17 killed."
resolution: null
duplicate_of: null
---
Low. requestComparison returns while inFlightRefreshes > 0 (:1531) but model() hides the buttons only for refreshPending (:1214-1223). Fix: hide them while inFlightRefreshes > 0. Review: https://github.com/jlevy/metabrowser/pull/346#pullrequestreview-5856287761 (PR #346, review B, round 2).
