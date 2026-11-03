---
type: is
id: is-01m6gqtjg4ebm3h0w7hz9gyd46
title: "PR #281: preserve documented attended-PR API aliases from current main"
kind: bug
status: closed
priority: 2
version: 8
labels: []
dependencies: []
parent_id: is-01m6g59qm4ewjgek4vjmndcxrj
child_order_hints:
  - is-01m6gxtzv1r91gq61dcn6nzz75
created_at: 2026-11-03T12:58:25.151Z
updated_at: 2026-11-03T19:30:55.960Z
closed_at: 2026-11-03T15:35:21.960Z
close_reason: "Owner superseded this compatibility requirement: bundled local frontend/backend needs one current explicit-number contract, with no old-client compatibility. The prototype was forward-reverted; current contract and core browsing stability are tracked under mb-ow6w."
resolution: canceled
duplicate_of: null
---
The owner requires an additive stack. Native installed-wheel probes confirm documented c934a0b4 PR-URL calls regress at8dedc142: GET pull and GET pull-markdown?part=body without number return200 on current main but400 on the stack; POST pull-refresh{} previously forces a manual refresh and now400. Repo-URL/no-attended legacy absence/error contracts also differ. Preserve omitted-number aliases using only the existing in-memory attended companion, with no GET acquisition or network. Restore legacy empty-body manual retry only when number and retry are omitted; keep explicit-number and explicit retry semantics, rate policy, job bounds and validation unchanged. Missing keys alone select legacy mode; explicit invalid/duplicate-present inputs never fall back. Preserve old no-attended envelope/status/ETag and Markdown part validation. Canonical new clients continue naming a PR. This is a new compatibility requirement checked against current main, not a reopening of the earlier implementation reviews. Add nonvacuous request/provider-call regressions, update narrow docs, independent review, then forward propagation and exact-head gates.

## Notes

Attended-PR API compatibility checkpoint

Commit: 6d956e454388e7f8e7a4ee2785879769f88b4f52
Base: 9e5d6dd9896886a44e7e71546d3039ba312e90d7 (owning PR281)
Branch: codex/pr-attended-api-compat-01a1a051
Worktree: isolated worktree `metabrowser-checkout-files-01a1a051` (clean)
Bead: mb-c5cf; independent review and coordinator forward integration pending.

Confirmed consumer: published one-shot --api commands opened on a PR URL. Independent
installed current-main probes found omitted-number pull/markdown200 and refresh{}202
regressed to400. Four added production-route regressions reproduced the failure before
implementation; red.log preserves those failures.

The omitted key alone addresses the existing MirrorSession.companion number. Reads
never create a companion, select a PR, run Git or gh, or start work. Canonical explicit
number validation and error precedence remain unchanged, including existing duplicate
last-value parsing. Empty/null/boolean/malformed explicit numbers never fall back.

A refresh omitting number and retry defaults to a manual reader action even when fresh.
Explicit retry:false stays automatic, and explicit-number default remains automatic.
Both forms use unchanged coordinator joins, job bounds, error recording, and rate-limit
policy. Existing manual retry bypass of a reset wait is intentionally preserved;
automatic retries remain gated. No-attended reads retain200 absent/no_pull_request,
ETag/no-store/304; valid-part markdown retains409 no_pull_request and no-store;
refresh{} retains409 same error without cache-control. Invalid Markdown part stays400.
Responses retain the additive pin_ref field; refresh status_route names the explicit
selected number so follow-up remains bound to that job even if attendance changes.

Validation:
- Initial focused new/validation/rate/job-bound regressions:16 passed in18.56s.
- Real fresh legacy{} refresh: exactly8 fake-gh calls and same complete record afterward;
  omitted GET/Markdown aliases and explicit automatic requests make0 calls.
- Existing CLI golden now includes actual omitted GET, Markdown, and empty POST with
  real local-origin/fake-gh calls. Golden regeneration passed; transcript inspected.
- Five affected modules:153 passed and1 failed in134.05s. Failure is the inherited
  tests/fixtures/github-pull-page-responses.json generic comparison URL, not an alias.
- Baseline proof temporarily restored all3 changed product files to9e5, asserted src
  and the selected test/fixture match HEAD exactly, reproduced the same stale fixture
  failure in6.71s, and restored owned edits byte-for-byte. The coordinator assigned the
  owning284 fixture correction separately. baseline-stale-fixture.log preserves this.
- Final parser spelling and bounded-job tests after lint corrections:4 passed in6.90s.
- Full make -o install lint-check passed with installed locked external dependencies:
  lint/format, Python/browser types, hygiene, supply chain, artifact contracts, parity,
  goldens and startup budget. Initial lint caught1style/1test-type issue, both fixed.
- make format / pinned Flowmark, git diff --check, and all normal pre-commit hooks passed.
- Makefile, dependency locks, frontend assets and other owned branches unchanged.

Ten changed files:3 product Python modules,2 test modules,1 CLI golden,4 narrow docs.
No new framework/state/network path, no push/sync/public posting/history rewrite.
Author review is not independent review. Coordinator owns independent review, lower
fixture propagation, full exact-head verify and CI. Source hooks/lint passed; the known
baseline fixture failure is not claimed green.

OWNER SUPERSESSION (2026-11-03): Owner clarified there are no backward-compatibility constraints for the co-shipped local frontend/backend. The compatibility-only requirement and its validation are cancelled. Authorized forward reverts of e11595d4 and6d956e45 restore one current API requiring an explicit pull-request number; no attended-number fallback or nullable legacy envelope. Prior findings/results remain historical evidence, not requirements for the new candidate. Work is on codex/pr-required-number-01a1a051 from e11595d4; unrelated481 fixture and lower cache/recovery work are preserved. Focused validation and immutable handoff pending; coordinator owns propagation, final gates, closure and sync. No push/sync by worker.

OWNER-SUPERSEDED REQUIREMENT: forward cleanup committed a30750dce910502593e81229d431b59e092c44e9, direct child e11595d4, clean codex/pr-required-number-01a1a051. Both compatibility commits are reverted without rewriting history. Three production files equal pre-alias6d^; explicit-number contract is the sole API. 132 focused tests/32 pull transcript checks/full lint and normal hooks passed. Current docs use explicit numbers; unrelated481 fixture/G1/recovery/frontend/locks unchanged. Independent review requested; coordinator owns upper288 composition, forward integration, final gates and closure. No worker push/sync. Durable evidence: required-number-e11595d4/checkpoint.txt.
