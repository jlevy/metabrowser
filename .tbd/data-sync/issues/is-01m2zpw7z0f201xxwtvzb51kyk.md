---
type: is
id: is-01m2zpw7z0f201xxwtvzb51kyk
title: "S217-3: build isolated Git environments from an allowlist (GIT_ALLOW_PROTOCOL, GIT_DEFAULT_REF_FORMAT)"
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
created_at: 2026-09-20T15:27:40.510Z
updated_at: 2026-09-20T17:19:00.803Z
---
Finding S217-3 from the v0.11 stabilization review. Owning layer: PR #217. Full evidence, path:line, and suggested fix are in the notes of mb-gacf under S217-3.

## Notes

Fixed on stab/s217 (pending restack integration and push to PR 217). Every new test seen failing on the unfixed code; 263 focused tests pass.
