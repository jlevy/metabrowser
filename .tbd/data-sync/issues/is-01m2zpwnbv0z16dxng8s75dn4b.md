---
type: is
id: is-01m2zpwnbv0z16dxng8s75dn4b
title: "S216-3: map GitError including GitTimeoutError to typed envelopes on Git content routes"
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
created_at: 2026-09-20T15:27:54.233Z
updated_at: 2026-09-20T17:19:03.707Z
---
Finding S216-3 from the v0.11 stabilization review. Owning layer: PR #216. Full evidence, path:line, and suggested fix are in the notes of mb-gacf under S216-3.

## Notes

Fixed on stab/s216-core (pending restack integration and push to PR 216). Counter-based regression tests red before, green after; 190 focused tests pass. Measurements are in the commit bodies and beside the constants.
