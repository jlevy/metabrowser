---
type: is
id: is-01m2zpx4d15neap9x8fcf36tq4
title: "S209-2: Git /raw bypasses the sandbox headers; move them to a path-scoped layer with a Git wire test"
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
  - stack:pr209
dependencies: []
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
created_at: 2026-09-20T15:28:09.630Z
updated_at: 2026-09-20T17:04:17.481Z
closed_at: 2026-09-20T17:04:17.480Z
close_reason: "PR 209 half done and pushed in 1c1eb1ad (head 04534249): raw trust headers now come from a path-scoped ASGI layer covering every status and return path, with a wire test that a new return path cannot miss them. The Git-side wire test for an HTML blob under a Git subject moves to the post-#209 restack and is tracked on mb-rlt4."
resolution: null
duplicate_of: null
---
Finding S209-2 from the v0.11 stabilization review. Owning layer: PR #209. Full evidence, path:line, and suggested fix are in the notes of mb-gacf under S209-2.
