---
type: is
id: is-01m2zpwenhppjpks39tf0nxkkb
title: "S217-6: move ad6e30f8 (below-floor refuse must not write the home) down to PR 217 and restack"
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
  - stack:pr217
dependencies: []
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
created_at: 2026-09-20T15:27:47.375Z
updated_at: 2026-09-21T00:08:10.693Z
closed_at: 2026-09-21T00:08:10.692Z
close_reason: "Pushed 2026-09-20 in the restack of stack #218 onto main (through #209 and #220). Single pre-push gate on macOS: 3061 passed, 2 skipped, 145 golden transcripts. Awaiting CI."
resolution: null
duplicate_of: null
---
Finding S217-6 from the v0.11 stabilization review. Owning layer: PR #217. Full evidence, path:line, and suggested fix are in the notes of mb-gacf under S217-6.

## Notes

Fixed on stab/s217 (pending restack integration and push to PR 217). Every new test seen failing on the unfixed code; 263 focused tests pass.
