---
type: is
id: is-01m74w0sqc6whmk8mqxxrn41ws
title: "PR #348 A14: snapshot-route changes belong in the lower layer #347"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m74w003xk59spnxy95gr9dss
hold: null
hold_until: null
created_at: 2026-11-11T08:36:32.107Z
updated_at: 2026-11-11T10:57:54.132Z
started_at: 2026-11-11T09:24:55.944Z
closed_at: 2026-11-11T10:57:54.131Z
close_reason: "Fixed by moving down: #347 now carries the admission recheck in admitted_snapshot, the Markdown bounding, and the code-controls doc table; this layer took #347's versions in merge 0208bdf0 and keeps only the render-bound replacement that C1/A4 assign here (eb71cdc7)."
resolution: null
duplicate_of: null
---
Low. pull_snapshot.py:162-217, 276-285; docs/reviewing-pull-requests.md:187-198. Review A https://github.com/jlevy/metabrowser/pull/348#pullrequestreview-5855514600
