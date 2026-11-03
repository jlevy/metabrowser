---
type: is
id: is-01m6h5a9vdhrjr479p67xy5wxr
title: "PR #281 Qodo4457444601: pull-state assertion lifecycle"
kind: bug
status: closed
priority: 1
version: 4
labels: []
dependencies: []
parent_id: is-01m6g59qm4ewjgek4vjmndcxrj
created_at: 2026-11-03T16:54:12.076Z
updated_at: 2026-11-03T20:17:10.534Z
closed_at: 2026-11-03T20:17:10.534Z
close_reason: Review disposition completed and published, with independent controls supporting the rebuttal or decline. The reviewer-visible threads remain open; this closure records completed triage rather than an unimplemented source fix. Final stack gates passed at ea771741; no PR merged.
resolution: null
duplicate_of: null
---
High review https://github.com/jlevy/metabrowser/pull/281#discussion_r4457444601 at3dd12b0b. Proposed rebuttal pending coordinator approval: only MirrorSession.__init__ assigns pull_requests; pull_host returns no host unless it is ServedPulls before exposing request_pull_refresh callback. Attended refresh checks companion, which attend creates only from the existing set. Shutdown clears the app reference then cancels/awaits jobs without nulling session.pull_requests. No valid request or lifecycle reaches these internal assertions with None. Optimized Python queue/attended/shutdown checks forthcoming; do not close before coordinator decision.

## Notes

Coordinator approved rebuttal on2026-11-03: PullHost refuses absent set before exposing callback; MirrorSession only assigns set at construction; attended route requires companion created from that set; shutdown unpublishes app session then cancels/awaits jobs without nulling the set. Actual optimized-Python queue/attended/shutdown plus manifest caller tests10pass15.30s. Source excerpts/raw logs retained in bot-triage-281-283. No guard/style edit; rebutted thread stays open. Root owns publication/sync/closure.
