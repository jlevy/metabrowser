---
type: is
id: is-01m2zpwqfy7v676azc2mxx3g5s
title: "S216-5: --show ignores --plugins-dir because server is imported before plugin directories are set"
kind: bug
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
  - stack:pr216
dependencies: []
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
created_at: 2026-09-20T15:27:56.409Z
updated_at: 2026-09-20T17:19:05.009Z
---
Finding S216-5 from the v0.11 stabilization review. Owning layer: PR #216. Full evidence, path:line, and suggested fix are in the notes of mb-gacf under S216-5.

## Notes

Fixed on stab/s216-cli and/or stab/s216-core (pending restack integration and push to PR 216). Regression tests red before, green after.
