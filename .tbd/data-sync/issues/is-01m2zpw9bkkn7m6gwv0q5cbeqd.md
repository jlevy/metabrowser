---
type: is
id: is-01m2zpw9bkkn7m6gwv0q5cbeqd
title: "S217-4: ls-remote reads an enclosing repository's config via cwd=home discovery"
kind: bug
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
  - stack:pr217
dependencies: []
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
created_at: 2026-09-20T15:27:41.938Z
updated_at: 2026-09-20T17:19:01.191Z
---
Finding S217-4 from the v0.11 stabilization review. Owning layer: PR #217. Full evidence, path:line, and suggested fix are in the notes of mb-gacf under S217-4.

## Notes

Fixed on stab/s217 (pending restack integration and push to PR 217). Every new test seen failing on the unfixed code; 263 focused tests pass.
