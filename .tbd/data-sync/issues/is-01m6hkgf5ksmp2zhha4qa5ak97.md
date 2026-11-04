---
type: is
id: is-01m6hkgf5ksmp2zhha4qa5ak97
title: Audit PR request payload sizes and review lazy detail and Git diff fetching
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6hkbt0t0qhvrhxhktgefe38
hold: null
hold_until: null
created_at: 2026-11-03T21:02:14.194Z
updated_at: 2026-11-04T17:14:30.002Z
started_at: 2026-11-03T21:05:42.366Z
closed_at: 2026-11-04T17:14:30.002Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---

## Notes

Read-only payload audit at ea771741 completed. Four matching 100-row REST/GraphQL page pairs from public repositories showed 39.68–47.07 times smaller decoded catalog payloads (1.90–2.21 MB versus 46–49 KB), including current row fields and exact all/open/closed counts. Single latency samples overlap; no general latency claim.

Public PR288's REST file list was 378,998 bytes, including 331,757 bytes of discarded patch text. Minimal GraphQL was 5,605 bytes but omits previous filenames. The coordinator declined a hybrid to preserve progressive listing and rename semantics. mb-0cr3 remains an open follow-up; no product changes were made.

The exact production metadata API stage used six requests: cold 347,257 bytes in 1.534 seconds; warm all six returned 304 with zero body bytes in 1.463 seconds. In-memory record fitting and serialization took about 3.9 ms. This does not justify a main pipeline rewrite.

Durable evidence is under catalog-payload-ea771741: design-audit.json, metrics.json, supplement.json, detail-conditional.json, and three reproducible probes. Provisional catalog design observations were sent to the author and saved separately. Formal independent code review awaits a settled immutable pin.
