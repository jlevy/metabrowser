---
type: is
id: is-01m6gm8jmy63yqmzcqrvhahnra
title: "PR #283 G1: bypass persisted manifests when their bank cannot invalidate corruption"
kind: bug
status: closed
priority: 2
version: 5
labels: []
dependencies: []
parent_id: is-01m6g59qm4ewjgek4vjmndcxrj
created_at: 2026-11-03T11:56:09.750Z
updated_at: 2026-11-03T20:17:09.743Z
closed_at: 2026-11-03T20:17:09.743Z
close_reason: "Completed by forward commits in the PR-support stack; independent reviews, rechecks and dispositions are published on the owning PRs. Final integration ea771741211193a387c1771e04df29b5a9698100 passed make verify (4712 Python, 9 expected skips, 373 transcripts), 8 public live tests, installed-wheel Chrome (22 actions, 25 unchanged checkout/Git fingerprints), and all 171 CI jobs across 19 current-head runs on 14 PRs. Final clean review: https://github.com/jlevy/metabrowser/pull/288#pullrequestreview-5758664799 . No PR merged."
resolution: null
duplicate_of: null
---
Independent real-route probe at58270d69: a forged blob creates persisted wrong exact totals; actual owner-readable/non-writable0500 bank makes corruption-time invalidation fail safely409. Restore genuine blob and reset process state while bank remains0500: GET200 returns genuine patches but stale exact+24/-1 rather than+2/-0. Refuse adoption of a persisted manifest when its bank cannot support invalidation; recompute disposable metadata without network or checkout writes. Preserve normal writable-bank hit performance, private-path checks, and owner permissions. Add actual-permission regression and negative control. This is a newly reproduced lifecycle gap beyond Review F fixes, not a reverted prior finding. Root stopped push before source publication and stopped dependent final acceptance; all exact-head gates and CI must rerun after forward propagation.

## Notes

G1 read-only manifest invalidation checkpoint

Commit: ea891a57b2d7ef5e1319ceee8658e0879777a102
Base: 3cb490152e15df1eab01f886b42bea150265bfc9
Branch: codex/pr-manifest-readonly-01a1a051
Worktree: isolated worktree `metabrowser-overlay-healing-01a1a051` (clean)
Bead: mb-4vsk (implemented, independent review pending; coordinator owns sync/closure)

Reproduction: independent production-route probe at base3cb reproduced the actual0500
bank defect: corruption409, then backing repair + process reset yielded200 genuine
patches with false exact+24/-1 totals instead of+2/-0. Bypassing disk adoption alone
returned the exact genuine response; the stale slot remained unchanged.

Implementation:
- Descriptor-validated private-directory admission checks owner write/search bits,
  effective OS access and read-only mount state without permission widening or writes.
- Read-only banks remain usable via recomputation, with no network or checkout writes.
- Every corruption invalidation attempts atomic exact-slot clearing, then advances that
  slot's64hex epoch beside the bank. At most16 fixed epoch paths; no growing registry,
  bank scan, unchecked unlink or cache-wide lock.
- Epoch advancement also occurs when exact-slot clearing succeeds, so an older in-flight
  computation cannot republish an apparently current slot. Other slots retain disk hits.
- Schema2 manifests require an epoch captured before computation. Missing epochs are
  exclusively initialized with a new token; malformed, unreadable or symlink epochs
  disable persistence. Older/mismatched manifest records are disposable cache misses.
- If the epoch cannot be persisted, the409 explicitly requires clearing the affected
  repository cache before retrying. A successful admission check is not a guarantee
  against later ACL/mount/disk failure; no impossible durability claim is made.

Validation:
- Full manifest/private-storage modules:184 passed in26.19s at final production source.
  The isolation test was then made independent of incidental slot collisions; that
  changed test passed separately. All production source was unchanged by that test edit.
- Actual0500 and0400 corruption/restart/restored0700 cases; resumed healthy disk-hit
  negative control; both invalidation locations unwritable; writable/readonly bank
  in-flight stale writes; missing/invalid/symlink epoch; other real PR slot preservation.
- Actual macOS owner-deny ACL and preserved modes/ACLs; private symlink/shared-directory
  refusals; read-only mount flag simulated at the OS boundary (no real RO mount claim).
- Final `make -o install lint-check` passed using existing external locked dependencies:
  formatting, lint, Python/browser types, public hygiene, contracts, parity and goldens.
- Normal pre-commit hooks passed. Makefile and dependency locks unchanged.
- Author review only; independent review, forward integration, full verify and CI remain
  with coordinator. No push, sync, public posting, history rewrite or user-checkout write.

Healthy disk-hit measurement (not end-to-end rendering): nine alternating paired batches,
20 validated reads per batch, genuine two-file fixture, every manifest equal to the route.
Final median with guard+epoch+parser:0.64334165ms/read.
Same parser with only new checks bypassed:0.26274165ms/read.
Increment:0.38060ms/read. No Chrome/large-PR performance claim.
The first harness compared model nulls to omitted wire fields; corrected by model parsing.
A later invocation omitted PYTHONPATH and failed before timing; both logs are retained.

Durable files: red-probe.log; focused/per-slot logs; final-lint-check.log;
healthy-hit-cost.py and final-healthy-hit-cost.log; commit.log; diff.patch.
