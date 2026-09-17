---
type: is
id: is-01m2p1prnv5sdvx5atj08ckqn2
title: "Shared repository/provider mirror design review: publish formal stacked PR"
kind: task
status: closed
priority: 1
version: 9
spec_path: docs/project/architecture/arch-repository-sources-and-provider-mirrors.md
delegate: codex@spud10
labels:
  - release:v0.11.0
  - design
  - stack:publication
dependencies:
  - type: blocks
    target: is-01m2nz8zzgxsw9yzsgekxy82sr
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-16T21:24:31.034Z
updated_at: 2026-09-17T02:55:50.612Z
started_at: 2026-09-16T21:24:54.275Z
closed_at: 2026-09-17T02:55:50.611Z
close_reason: "PR #138 published at head 1a5188eec8cbb4870c700de8abe0e942f2eeb958 on exact base b907bb27 (PR #136), stack layer 8. Credential-boundary review closed with no actionable findings; make verify and all seven GitHub checks green. PR description updated and review record posted: https://github.com/jlevy/metabrowser/pull/138#issuecomment-5707765503. Not merged; landing remains with mb-n2ro."
resolution: null
duplicate_of: null
---
Independently review the corrected repository-subject, shared worktree-free store, provider-mirror, capability, locking, lease, and phased-delivery architecture. Resolve every finding through the review shortcut, run make verify, and publish one formal GitHub PR with gh stacked on exact green Phase 0C.2 PR #136 head. Record PR URL, base/head branches and immutable OIDs, formal stack view, review evidence, and final green CI. Do not merge; mb-n2ro alone owns explicit-approval landing and retargeting.

## Notes

Formal PR #138: https://github.com/jlevy/metabrowser/pull/138. Exact base codex/v011-hosted-review-phase0c2@b907bb2734929cd0858207ba5d73639aee168636; head codex/v011-shared-repository-mirror-design@1a5188eec8cbb4870c700de8abe0e942f2eeb958 (amended from dc91cd2d6dbfd670aa28b7d148fbb88ee79379b9 with a lease-protected force-push). gh stack layer 8 after PRs #125, #130, #132, #133, #134, #135, and #136; only the #138 branch moved.

Review evidence: two architecture reviews and two bead-graph audits resolved to zero findings on dc91cd2d. The final independent PR review then found provider-selected private Git fetches could fall back to ambient Git credentials. Resolution rounds: (1) non-secret AuthorizationContextRef to ProviderPrincipal plus opaque GitFetchCredentialLease; (2) ambient config and helper isolation, and mb-s123 wired to block mb-k7lc, with mb-k7lc's base corrected to Phase 2C; (3) the reviewer's live Git 2.50.1 experiments confirmed .netrc, template and repository-local config, trace, and cross-host redirect channels, plus registry-backed unforgeable leases, AuthorizationContextRef moving into core in mb-jlon, a Phase 2B pre-Git refusal, joining-request validation, single ownership (jlon registry and conversion, y1ax issuance, s123 askpass and isolation), and deleted-fork base pull refs; (4) leases bound to an authorization-context key rather than a session, core-armed askpass answers, Git credential-URL normalization, the GIT_CONFIG_NOSYSTEM exception, and an accurate alternate-config claim. Final re-audit: all findings fixed, no new actionable contradiction.

Validation on the final diff: make verify passed with 2349 tests, 1 skipped, and 124 goldens, plus every lint, type, parity, audit, build, and distribution gate; the Lefthook pre-push gate passed. All seven GitHub checks are green on 1a5188ee: lint, distribution, Python 3.12, 3.13, 3.14, 3.14t, and stack-integration. No merge performed.

Remaining before close, both outward-facing and awaiting the user: update the PR #138 description (the draft names the credential redesign and the new head; the gh pr edit attempt was denied by the permission check), and post the independent review disposition on the PR.
