---
type: is
id: is-01m2zpwm7b0ns673t2jyje7fdg
title: "S216-2: memoize whole-index chrome, rollup, and filter tallies per pinned tree and add a node budget"
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
created_at: 2026-09-20T15:27:53.066Z
updated_at: 2026-09-20T17:19:03.233Z
---
Finding S216-2 from the v0.11 stabilization review. Owning layer: PR #216. Full evidence, path:line, and suggested fix are in the notes of mb-gacf under S216-2.

## Notes

Fixed on stab/s216-core (pending restack integration and push to PR 216). Counter-based regression tests red before, green after; 190 focused tests pass. Measurements are in the commit bodies and beside the constants.
