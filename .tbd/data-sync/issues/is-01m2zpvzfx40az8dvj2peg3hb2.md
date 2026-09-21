---
type: is
id: is-01m2zpvzfx40az8dvj2peg3hb2
title: "S140-2: startup sweep rmtree handler raises TypeError and fails every open_cache"
kind: bug
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
  - stack:pr140
dependencies: []
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
created_at: 2026-09-20T15:27:31.833Z
updated_at: 2026-09-21T00:08:08.325Z
closed_at: 2026-09-21T00:08:08.324Z
close_reason: "Pushed 2026-09-20 in the restack of stack #218 onto main (through #209 and #220). Single pre-push gate on macOS: 3061 passed, 2 skipped, 145 golden transcripts. Awaiting CI."
resolution: null
duplicate_of: null
---
Finding S140-2 from the v0.11 stabilization review. Owning layer: PR #140. Full evidence, path:line, and suggested fix are in the notes of mb-gacf under S140-2.

## Notes

Fixed on stab/s140 (pending restack integration and push to PR 140). See the mb-gacf notes; regression tests red before and green after; 384 focused tests pass.
