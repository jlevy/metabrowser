---
type: is
id: is-01m2zpwtxsex7zg035m9p3yvm7
title: "S216-8: JSONL Git blobs and diff sidekick filesystem calls run synchronously on the event loop"
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
created_at: 2026-09-20T15:27:59.919Z
updated_at: 2026-09-20T17:19:06.198Z
---
Finding S216-8 from the v0.11 stabilization review. Owning layer: PR #216. Full evidence, path:line, and suggested fix are in the notes of mb-gacf under S216-8.

## Notes

Fixed on stab/s216-cli and/or stab/s216-core (pending restack integration and push to PR 216). Regression tests red before, green after.
