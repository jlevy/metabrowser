---
type: is
id: is-01m6gxtzv1r91gq61dcn6nzz75
title: Align no-attended PR CLI goldens with restored legacy API responses
kind: bug
status: closed
priority: 2
version: 6
delegate: checkout_design
labels: []
dependencies: []
parent_id: is-01m6gqtjg4ebm3h0w7hz9gyd46
hold: null
hold_until: null
created_at: 2026-11-03T14:43:30.268Z
updated_at: 2026-11-03T15:35:22.240Z
started_at: 2026-11-03T14:43:46.162Z
closed_at: 2026-11-03T15:35:22.239Z
close_reason: "Owner superseded this compatibility requirement: bundled local frontend/backend needs one current explicit-number contract, with no old-client compatibility. The prototype was forward-reverted; current contract and core browsing stability are tracked under mb-ow6w."
resolution: canceled
duplicate_of: null
---
Exact R5 full gate found two stale cli-github-pull tryscript blocks: omitted-number repository GET is200 absent/no_pull_request; omitted-number POST{} is409 no_pull_request. Regenerate only these recorded outputs and correct their adjacent required-number sentence on owning281045f9e5b. Product source remains byte-identical. Coordinator owns forward propagation, full gates, publication and sync.

## Notes

Committed e11595d46d5242ff7a76591b253f1be90a2db9f7 as a direct child of owning281045f9e5b on codex/pr-legacy-absence-goldens-01a1a051; clean worktree. Exactly one transcript file changed. Two recorded outputs now match independently verified legacy no-attended GET200 absent/no_pull_request exit0 and POST409 no_pull_request exit1. Two adjacent descriptions corrected; every command, other console block, wildcard, normalizer and fixture unchanged. Structural audit checks32blocks and onlyindices7/21changed. Exact baseline reproduced30pass/2fail; normal recorder updated both mismatches; final full target32passed75.18s. Full make lint-check and normal hooks passed. Git object identities prove src, Makefile, manifests and locks unchanged. Independent reviewer has exact pin. No push/sync/publication/history rewrite. Coordinator owns independent disposition, forward propagation, final gates and closure.

OWNER SUPERSESSION (2026-11-03): Owner clarified there are no backward-compatibility constraints for the co-shipped local frontend/backend. The compatibility-only requirement and its validation are cancelled. Authorized forward reverts of e11595d4 and6d956e45 restore one current API requiring an explicit pull-request number; no attended-number fallback or nullable legacy envelope. Prior findings/results remain historical evidence, not requirements for the new candidate. Work is on codex/pr-required-number-01a1a051 from e11595d4; unrelated481 fixture and lower cache/recovery work are preserved. Focused validation and immutable handoff pending; coordinator owns propagation, final gates, closure and sync. No push/sync by worker.

OWNER-SUPERSEDED REQUIREMENT: forward cleanup committed a30750dce910502593e81229d431b59e092c44e9, direct child e11595d4, clean codex/pr-required-number-01a1a051. Both compatibility commits are reverted without rewriting history. Three production files equal pre-alias6d^; explicit-number contract is the sole API. 132 focused tests/32 pull transcript checks/full lint and normal hooks passed. Current docs use explicit numbers; unrelated481 fixture/G1/recovery/frontend/locks unchanged. Independent review requested; coordinator owns upper288 composition, forward integration, final gates and closure. No worker push/sync. Durable evidence: required-number-e11595d4/checkpoint.txt.
