---
type: is
id: is-01m2p1pshr699c6pf8xqeer16j
title: "Repository library Phase 1B-a review: publish worktree-free acquisition PR"
kind: task
status: closed
priority: 1
version: 21
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: claude-code@spud10.local
labels:
  - stack:publication
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
  - type: blocks
    target: is-01m2nz8q666pwqcbxbn7d5jr6x
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-16T21:24:31.927Z
updated_at: 2026-09-23T06:18:32.044Z
started_at: 2026-09-16T21:24:54.760Z
closed_at: 2026-09-23T06:18:32.043Z
close_reason: "Review and acceptance obligations are met. #217 was reviewed in the stabilization pass (S217-1..8 closed), and its remaining acceptance landed in PR #226 (codex/v012-foundation-stabilization, head f68c3045f40ee28aa3eb37b010511cf8923ccc0d, all nine checks green: https://github.com/jlevy/metabrowser/actions/runs/35825617023): mb-sumg, mb-pkho, mb-d1za, mb-oueh, mb-dg00, mb-lp89, mb-e32d, with mb-rati moved to 2A. #226 had two independent reviews, all findings fixed or filed (mb-163x). #217 is published and ready for review; not merged."
resolution: null
duplicate_of: null
---
Independently review GitCommandTarget, file:// local-origin sources under the untrusted profile (mb-dxmb), worktree-free acquisition, source/store alias publication, ref/object validation, crash recovery, cross-process CAS behavior, CLI parity, and acquisition goldens. Resolve every finding, run make verify, and publish one formal GitHub PR with gh stacked on the exact green Phase 1A head. Record exact stack evidence and final green CI. Do not merge.

## Notes

2026-09-22 follow-up: no work is held on tbd. All eight current stack PRs are ready for review; #217/#216 draft flags were removed at the user’s request after live ancestry, mergeability and green-CI checks. This changes mechanical mergeability, not feature completion or landing authorization. #217 is ready for review at 4d25dc9a. Acquisition acceptance and review obligations remain; do not close them merely because GitHub can merge the branch.

Earlier history:
Survivor PR is draft #217 https://github.com/jlevy/metabrowser/pull/217
Parent: #140 claude/v011-cache-format-foundation.
Head: cursor/v011-cache-acquire-cli-bd04 @ b09c01e0 (plus later spec-status commit on the tip only).
Folds #208 and #210. CI green. Still draft. Do not merge. Review this layer, then the stack.

2026-09-20: the head cited above (b09c01e0) is stale. PR #217 is OPEN with head 70091d81
(gh pr view 217 --json headRefOid), CI green on that head (gh pr checks 217: distribution,
lint, stack-integration and test 3.12/3.13/3.14/3.14t all pass). Further stabilization
fixes for this layer are in progress under mb-gacf.

2026-09-22 state reconciliation: published #217 head is 4d25dc9a1c18a757d6dda03d06fc19343364db09, based on #140 93f19061, draft and seven checks green. Prior substantive review/disposition through 6dc2617c; later commits are propagated merges. Do not close while Phase 1B-a acceptance remains: converging online/offline reads mb-pkho, minimum admitted Git CI mb-d1za (supported live runner mb-oueh), stalled-acquisition bound mb-rati, distribution-backport policy mb-e32d, remaining golden work mb-dg00 and cancellation decision mb-lp89. HTTPS/SSH acquisition is mb-bi2c and is not delivered by this PR.
