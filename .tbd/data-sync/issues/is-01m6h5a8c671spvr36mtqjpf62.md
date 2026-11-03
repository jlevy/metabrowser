---
type: is
id: is-01m6h5a8c671spvr36mtqjpf62
title: "PR #283 Qodo4457437377: manifest invalidation key invariant"
kind: bug
status: closed
priority: 1
version: 4
labels: []
dependencies: []
parent_id: is-01m6g59qm4ewjgek4vjmndcxrj
created_at: 2026-11-03T16:54:10.566Z
updated_at: 2026-11-03T20:17:10.523Z
closed_at: 2026-11-03T20:17:10.522Z
close_reason: Review disposition completed and published, with independent controls supporting the rebuttal or decline. The reviewer-visible threads remain open; this closure records completed triage rather than an unimplemented source fix. Final stack gates passed at ea771741; no PR merged.
resolution: null
duplicate_of: null
---
High review https://github.com/jlevy/metabrowser/pull/283#discussion_r4457437377 at04f8b202. Proposed rebuttal pending coordinator approval: invalidate_pull_manifest receives a RepositoryStoreTarget plus full40/64hex endpoints validated by pull_comparison_handler before its only production call. comparison_cache_key returns None only for a non-store or non-full endpoint. Upper288 recovery uses validated Comparison records or explicitly validated issued recovery pairs. Internal assertion is not a request or security boundary. Optimized Python caller/lifecycle checks and durable triage report forthcoming; do not close before coordinator decision.

## Notes

Coordinator approved rebuttal on2026-11-03: key is an internal invariant after RepositoryStoreTarget/full40-or64hex endpoint validation, including validated upper recovery pairs. Actual optimized-Python tests10pass15.30s cover SHA1/SHA256, corrupt invalidation/restart, queue and shutdown; normal focused30pass35.93s. Source excerpts and raw logs in agent-evidence/metabrowser-pr-stack-01a1a051/bot-triage-281-283. No code change for assertion; rebutted thread stays open. Root owns publication/sync/closure.
