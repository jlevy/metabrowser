---
type: is
id: is-01m6hnp2j641tnmwmw0ep18t4r
title: Refuse altered SQLite catalog schemas before reads and publication
kind: bug
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6hkbt0t0qhvrhxhktgefe38
hold: null
hold_until: null
created_at: 2026-11-03T21:40:15.045Z
updated_at: 2026-11-04T17:14:29.858Z
started_at: 2026-11-03T21:41:09.612Z
closed_at: 2026-11-04T17:14:29.858Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Independent cache-admission probe used a private user_version1 catalog with an extra trigger. Publication accepted it and reported two cached rows after the trigger deleted one. Admit only the bounded exact schema of the two known tables and required index; reject extra triggers/views, missing or changed objects before checkpoint use or writes, with typed refusal and no GET repair. Preserve the independent before/fix probe and ordinary publication controls.

## Notes

2026-11-03 fix checkpoint: catalog admission now compares at most four sqlite_schema rows against the exact two tables and required index, before reading a checkpoint or publishing a page. Initialization shares those DDL constants. Extra triggers/views/tables and a missing index refuse without cache mutation. Permanent regressions and unchanged independent schema probe pass. Optional enable_load_extension call removed; default-disabled extension loading remains unchanged. Evidence: catalog-backend-author/schema-successor.log; final independent recheck pending.
