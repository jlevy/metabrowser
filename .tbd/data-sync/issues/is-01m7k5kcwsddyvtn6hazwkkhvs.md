---
type: is
id: is-01m7k5kcwsddyvtn6hazwkkhvs
title: "PR #485 A5: Immutable releases and the O5 tag ruleset change failure handling, and the plan does not carry that into the docs"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7k1vctj6d370jg7hqdps4hk
hold: null
hold_until: null
created_at: 2026-11-16T21:53:20.792Z
updated_at: 2026-11-16T22:09:55.349Z
started_at: 2026-11-16T21:53:37.638Z
closed_at: 2026-11-16T22:09:55.348Z
close_reason: "Fixed in 83ef69fc3: Q3 and Risks state both consequences; docs/publishing.md Failure Handling rewritten (a version is spent once its tag exists; re-run for a transient or PyPI-side failure; next patch version for a code or workflow fix; same rule for macos-v tags); the README cites it."
resolution: null
duplicate_of: null
---
Medium. PLAN:410-412, :536-537, :554-556, :465-470; docs/publishing.md:178-186; .github/workflows/publish.yml:3-5. Under immutable releases a publish.yml failure that needs a code or workflow fix spends vX.Y.Z; with O5 a failed macos-v run also needs a new version. Fix: state both in Q3 and Risks; rewrite Failure Handling (new patch version after publication, re-run for a transient failure); the same rule for a failed macos-v run in the runbook. Review A (round 1) of PR #485: https://github.com/jlevy/metabrowser/pull/485#pullrequestreview-5928293258
