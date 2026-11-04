---
type: is
id: is-01m6hn9r6c5ky1jek345fd78mz
title: Keep known PR totals during catalog identity and cursor restart
kind: bug
status: closed
priority: 3
version: 4
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6hkbt0t0qhvrhxhktgefe38
hold: null
hold_until: null
created_at: 2026-11-03T21:33:31.209Z
updated_at: 2026-11-04T17:14:29.784Z
started_at: 2026-11-03T21:34:50.754Z
closed_at: 2026-11-04T17:14:29.784Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Independent review reproduced an identity/cursor restart publishing exact zero totals even though its query already reported17 PRs. Publish known totals with a reset, or retain an explicitly unknown count; do not claim a false zero while a legitimate replacement catalog warms. Recheck the independent reset probe.

## Notes

2026-11-03 fix checkpoint: a repository-identity reset retains provider totals and count_at already received before clearing cursors. The intermediate real envelope reports the known total17 and zero cached rows rather than a false exact total0. Permanent regression added; unchanged independent probe passes.
