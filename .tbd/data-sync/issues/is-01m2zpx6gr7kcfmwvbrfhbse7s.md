---
type: is
id: is-01m2zpx6gr7kcfmwvbrfhbse7s
title: "S209-4: HTML preview on a Git source 404s and relative references cannot resolve"
kind: bug
status: open
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.12.0
  - stack:followup
dependencies: []
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
created_at: 2026-09-20T15:28:11.798Z
updated_at: 2026-09-23T03:56:18.605Z
---
Finding S209-4 from the v0.11 stabilization review. Owning layer: PR #209. Full evidence, path:line, and suggested fix are in the notes of mb-gacf under S209-4.

## Notes

2026-09-22 (codex/v012-foundation-stabilization 387385bf): foundation disposition. Pins now always run under the untrusted profile (mb-99ub), so HTML on a pin offers only the source view, the same as a filesystem root under --untrusted. The 404ing preview is never offered through --show or --api, and a test pins that honest refusal. Resolving relative references under a served Git /raw is reachable only once acquired Git is served over HTTP, which is Phase 2A (mb-ew38/mb-innz). Keep open for that.

Earlier notes:
2026-09-22 reconciliation: #209 is merged. This is a remaining Git-source HTML/raw addressing integration issue for a new stack layer, not a request to reopen the merged HTML PR. Coordinate with mb-99ub and URL serving; test relative references only for preview capabilities the acquired-source policy intentionally exposes, and otherwise prove honest capability refusal.
