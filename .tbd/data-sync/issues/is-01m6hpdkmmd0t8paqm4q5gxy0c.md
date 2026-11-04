---
type: is
id: is-01m6hpdkmmd0t8paqm4q5gxy0c
title: Resume incomplete catalog backfill when cached display rows are already fresh
kind: bug
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6hkbt0t0qhvrhxhktgefe38
hold: null
hold_until: null
created_at: 2026-11-03T21:53:06.192Z
updated_at: 2026-11-04T17:14:29.712Z
started_at: 2026-11-03T21:53:28.736Z
closed_at: 2026-11-04T17:14:29.712Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Independent controller probe reopens a fresh incomplete catalog with500 cached Open rows: the UI reads five cached windows but issues no POST to resume all-repository metadata, leaving Catalog paused. Resume incomplete background backfill independently of whether the visible display target is already satisfied, while retaining failure retry windows, rate holds, disposal and request ownership. Recheck the unchanged resume-partial probe and complete/failure/rate-limit controls.

## Notes

Fixed automatic askIfDue to resume incomplete paused catalogs independently of matching display fullness while retaining askedAt throttle and backend failure/rate stamps. Unchanged independent fresh500Open-of5000 catalog probe red zeroPOST, then green onePOST target500. Permanent repeat poll control proves no tight POST retry; production recorder now captures real resumed job acknowledgement and coherent later cached windows. Final29 affected tests/both browser type configs/9 scoped UI goldens pass. Exact hashes and raw evidence in catalog-ui-m13a/writer-report.json. Root owns final commit/full gate/closure.
