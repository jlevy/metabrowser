---
type: is
id: is-01m6hryve021ndx04tt967a6a9
title: Audit PR performance reporting, cache semantics, and end-to-end gh sessions
kind: task
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6hkbt0t0qhvrhxhktgefe38
hold: null
hold_until: null
created_at: 2026-11-03T22:37:28.377Z
updated_at: 2026-11-03T22:37:55.387Z
started_at: 2026-11-03T22:37:55.381Z
---
Owner explicitly requests consistent performance reporting for PR work, correct and understood caching behavior, and session-based end-to-end verification of gh usage. Audit repository performance/reporting and test guidelines; map each performance claim to exact commit/artifact, cache state, machine/load, repetitions and metric. Audit catalog backfill/delta/ETag/account/rate/cancellation ownership against observed gh calls and existing caches. Inspect existing real-CLI and browserless UI sessions and add narrowly scoped actual-server/session coverage if a meaningful gap remains. Preserve cold/warm and payload-vs-latency distinctions, no unsupported speedup claims, no private fixture names in public evidence. Work is additive above the catalog/setup stack, forward only, no owner merge.
