---
type: is
id: is-01m6hryve021ndx04tt967a6a9
title: Audit PR performance reporting, cache semantics, and end-to-end gh sessions
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6hkbt0t0qhvrhxhktgefe38
child_order_hints:
  - is-01m6hsh8h8ts337bhn531he0xh
  - is-01m6hsvza8q7xmwa5q6m892kc9
hold: null
hold_until: null
created_at: 2026-11-03T22:37:28.377Z
updated_at: 2026-11-04T17:14:30.857Z
started_at: 2026-11-03T22:37:55.381Z
closed_at: 2026-11-04T17:14:30.857Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Owner explicitly requests consistent performance reporting for PR work, correct and understood caching behavior, and session-based end-to-end verification of gh usage. Audit repository performance/reporting and test guidelines; map each performance claim to exact commit/artifact, cache state, machine/load, repetitions and metric. Audit catalog backfill/delta/ETag/account/rate/cancellation ownership against observed gh calls and existing caches. Inspect existing real-CLI and browserless UI sessions and add narrowly scoped actual-server/session coverage if a meaningful gap remains. Preserve cold/warm and payload-vs-latency distinctions, no unsupported speedup claims, no private fixture names in public evidence. Work is additive above the catalog/setup stack, forward only, no owner merge.
