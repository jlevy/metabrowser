---
type: is
id: is-01m7kascwqcptg9j4rbqasg2ck
title: "PR #488 A1: PROBE_WAIT_MS comment says a missing probe fails by name well inside the 30 s budget, and quotes an unmaintained 72-305 ms baseline"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7k3fdgyayshmca073e9p811
hold: null
hold_until: null
created_at: 2026-11-16T23:24:00.278Z
updated_at: 2026-11-16T23:30:53.189Z
started_at: 2026-11-16T23:24:05.925Z
closed_at: 2026-11-16T23:30:53.187Z
close_reason: "Fixed in 446a2faac on PR #488: PROBE_WAIT_MS comment reworded (no 'well inside', no unmaintained baseline); a missing probe is named even past the budget. Confirmed by a never-committing commit view run (4 of 94 checks failed, each 'a commit's body is shown') and a passing run at the head."
resolution: null
duplicate_of: null
---
Low. tests/dom/prose-faces-chrome.mjs:35-38. PR #488, review A round 1: https://github.com/jlevy/metabrowser/pull/488#pullrequestreview-5929693679. A probe that never shows waits PROBE_WAIT_MS per pass, so four passes can carry the session past RUN_BUDGET_S; its failure is still named because check() writes it as found and the timeout assertion includes stderr. The comment's 'well inside the 30 s run budget' and its 72 to 305 ms baseline do not hold. Coordinator decision: fix with the first option (reword the comment, drop 'well inside' and the unmaintained baseline).
