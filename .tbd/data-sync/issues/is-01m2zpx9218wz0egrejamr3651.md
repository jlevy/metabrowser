---
type: is
id: is-01m2zpx9218wz0egrejamr3651
title: "S209-6: resolve the nine-file merge conflict between PR 209 and the stack tip"
kind: task
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
  - stack:pr209
dependencies: []
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
created_at: 2026-09-20T15:28:14.388Z
updated_at: 2026-09-21T00:40:29.321Z
closed_at: 2026-09-21T00:40:29.313Z
close_reason: "Resolved during the restack: the nine-file conflict between PR 209 and the stack was resolved layer by layer when each branch merged the new main, and the security-critical raw_file conflict kept both the Git dispatch and the path-scoped sandbox layer, proven by a new wire test (e0cf4a20). All seven layers are green including stack-integration."
resolution: null
duplicate_of: null
---
Finding S209-6 from the v0.11 stabilization review. Owning layer: PR #209. Full evidence, path:line, and suggested fix are in the notes of mb-gacf under S209-6.

## Notes

After PR 209 lands and the stack restacks onto main: resolve the nine-file conflict, confirm git_revision_raw inherits the path-scoped raw trust layer, and add the wire test for an HTML/SVG blob under a Git subject (carried over from mb-gqmt).
