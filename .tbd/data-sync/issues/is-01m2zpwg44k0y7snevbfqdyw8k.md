---
type: is
id: is-01m2zpwg44k0y7snevbfqdyw8k
title: "S217-7: acquisition Lows: stores-by-sources reclaim scan, late detached-HEAD refusal, child-only kill on timeout"
kind: bug
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - stack:pr217
  - release:v0.12.0
dependencies: []
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
created_at: 2026-09-20T15:27:48.863Z
updated_at: 2026-09-23T03:55:19.972Z
closed_at: 2026-09-23T03:55:19.970Z
close_reason: "All three parts done. Detached-HEAD refusal before the fetch and single-pass alias reclaim landed in the stack as aa05db72 (same change as 181b0216 on stab/s217). Process-group kill: on codex/v012-foundation-stabilization d83beb9b, decided by the user 2026-09-22. ACQUISITION_POLICY and FETCH_POLICY set own_process_group, so Git starts in a new session, and terminate_git_process kills the group. Read, store and batch policies keep the caller's group, so terminal Ctrl-C reaches them directly; for acquisition it arrives through cancellation, which kills the group. tests/test_git_process_group.py: a forked helper dies on timeout and on cancellation (both failed before the fix)."
resolution: null
duplicate_of: null
---
Finding S217-7 from the v0.11 stabilization review. Owning layer: PR #217. Full evidence, path:line, and suggested fix are in the notes of mb-gacf under S217-7.

## Notes

Two of three fixed on stab/s217 (181b0216): detached-HEAD origin refused before the fetch; reclaim reads each alias once plus once per candidate. NOT done: process-group kill on timeout, because start_new_session changes how Ctrl-C reaches children; needs its own decision.
