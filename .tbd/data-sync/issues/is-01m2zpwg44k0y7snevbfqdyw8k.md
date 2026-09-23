---
type: is
id: is-01m2zpwg44k0y7snevbfqdyw8k
title: "S217-7: acquisition Lows: stores-by-sources reclaim scan, late detached-HEAD refusal, child-only kill on timeout"
kind: bug
status: in_progress
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - stack:pr217
  - release:v0.12.0
dependencies: []
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
created_at: 2026-09-20T15:27:48.863Z
updated_at: 2026-09-23T00:21:42.634Z
---
Finding S217-7 from the v0.11 stabilization review. Owning layer: PR #217. Full evidence, path:line, and suggested fix are in the notes of mb-gacf under S217-7.

## Notes

Two of three fixed on stab/s217 (181b0216): detached-HEAD origin refused before the fetch; reclaim reads each alias once plus once per candidate. NOT done: process-group kill on timeout, because start_new_session changes how Ctrl-C reaches children; needs its own decision.
