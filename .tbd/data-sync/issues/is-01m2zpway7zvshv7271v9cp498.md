---
type: is
id: is-01m2zpway7zvshv7271v9cp498
title: "S217-5: map GitError to path-free CLI errors and bound the filter-honored rev-list"
kind: bug
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
  - stack:pr217
dependencies: []
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
created_at: 2026-09-20T15:27:43.555Z
updated_at: 2026-09-21T00:08:10.364Z
closed_at: 2026-09-21T00:08:10.363Z
close_reason: "Pushed 2026-09-20 in the restack of stack #218 onto main (through #209 and #220). Single pre-push gate on macOS: 3061 passed, 2 skipped, 145 golden transcripts. Awaiting CI."
resolution: null
duplicate_of: null
---
Finding S217-5 from the v0.11 stabilization review. Owning layer: PR #217. Full evidence, path:line, and suggested fix are in the notes of mb-gacf under S217-5.

## Notes

Fixed on stab/s217 (pending restack integration and push to PR 217). Every new test seen failing on the unfixed code; 263 focused tests pass.
