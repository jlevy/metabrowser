---
type: is
id: is-01m6tz4mcm7zgwd85mrhs1cpmc
title: Release retained PR preparation owners after coverage-only receipts
kind: bug
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6th4qn5b1s27zkw8rw3736h
hold: null
hold_until: null
created_at: 2026-11-07T12:18:39.123Z
updated_at: 2026-11-08T01:50:20.333Z
started_at: 2026-11-07T12:18:55.556Z
---
Confirmed ownership bug in public PR #324, review thread https://github.com/jlevy/metabrowser/pull/324#discussion_r4501662169. Both 200 ready and partial receipts describe coverage only and can leave the prior server window W1 retained. The frontend currently records the new demand W2 as coreHeld, so hide/dispose can release W2 while W1 remains owned.

Fix the frontend ownership bookkeeping without changing the backend wire contract or discarding valid coverage. Track ownership separately from cached/partial coverage, release the actual retained owner when it is abandoned, and preserve deferred retries and selection priority. Add production-controller regressions for both ready and partial receipts that preserve W1, followed by hide/dispose; retain ordinary admitted-window cleanup.

Owner PR: #324. Readiness is held until the fix is independently reviewed, forward-integrated, fully verified, and published with fresh CI. The earlier full gate at 11dbb8ba3 remains valid historical evidence: 4,916 tests passed, nine expected skips, 385 goldens, audits, distribution, and installed-package smoke checks. Existing 14 dispositions and the PR #327 status finding are resolved; this is the newly confirmed 16th finding in that review cycle.

## Notes

Implemented in c84d25f8 on the owning prefetch layer and forward-integrated. Only202started/joined establishes ownership; ready/partial clears the client owner handle and awaits release of its previous exact token before queue advancement. Three held-release production scenarios cover partial→hide, partial→dispose and ready→hide; all fail published11db and pass the correction. Root reviewed the interrupted agent's implementation, corrected two stale test/playbook labels, and resolved a documentation-only forward-merge conflict while preserving the current detailed playbook. Integrated13tests/eightgoldens/bothTS pass. Full gate/push/CI and thread disposition remain pending at6cf001cdf.
