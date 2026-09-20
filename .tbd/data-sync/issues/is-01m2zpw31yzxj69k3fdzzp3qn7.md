---
type: is
id: is-01m2zpw31yzxj69k3fdzzp3qn7
title: "S140-4: record or satisfy the same-origin evaluation gate against a populated cache before Phase 1B-a lands"
kind: task
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
  - stack:pr140
dependencies: []
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
created_at: 2026-09-20T15:27:35.485Z
updated_at: 2026-09-20T17:16:30.168Z
closed_at: 2026-09-20T17:16:30.166Z
close_reason: "Gate satisfied by order: PR 209 (raw sandbox plus /api same-origin proof) merged to main as fd65812b on 2026-09-20, before PR 217 lands."
resolution: null
duplicate_of: null
---
Finding S140-4 from the v0.11 stabilization review. Owning layer: PR #140. Full evidence, path:line, and suggested fix are in the notes of mb-gacf under S140-4.

## Notes

Decision 2026-09-20 (user): satisfy the gate by ORDER, not by a recorded evaluation: PR #209 lands on main before PR #217. Merging #209 still needs explicit approval at land time, after its fixes (mb-nisk, mb-gqmt, mb-qx42) are pushed and CI is green. After #209 lands, restack the stack onto main and do the integration beads mb-gqmt (Git /raw through the header layer), mb-99ub, mb-g5je, mb-rlt4.
