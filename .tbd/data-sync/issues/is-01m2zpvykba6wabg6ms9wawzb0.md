---
type: is
id: is-01m2zpvykba6wabg6ms9wawzb0
title: "S140-1: cache preflight swallows PrivateStorageError and mutates the home before refusing"
kind: bug
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
  - stack:pr140
dependencies: []
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
created_at: 2026-09-20T15:27:30.898Z
updated_at: 2026-09-20T17:18:58.876Z
---
Finding S140-1 from the v0.11 stabilization review. Owning layer: PR #140. Full evidence, path:line, and suggested fix are in the notes of mb-gacf under S140-1.

## Notes

Fixed on stab/s140 (pending restack integration and push to PR 140). See the mb-gacf notes; regression tests red before and green after; 384 focused tests pass.
