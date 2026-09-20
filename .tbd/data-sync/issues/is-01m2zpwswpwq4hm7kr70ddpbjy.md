---
type: is
id: is-01m2zpwswpwq4hm7kr70ddpbjy
title: "S216-7: --show misparses tracked names starting with g1- and the tree renderer double-decodes display names"
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
created_at: 2026-09-20T15:27:58.868Z
updated_at: 2026-09-20T17:19:05.806Z
---
Finding S216-7 from the v0.11 stabilization review. Owning layer: PR #216. Full evidence, path:line, and suggested fix are in the notes of mb-gacf under S216-7.

## Notes

Fixed on stab/s216-cli and/or stab/s216-core (pending restack integration and push to PR 216). Regression tests red before, green after.
