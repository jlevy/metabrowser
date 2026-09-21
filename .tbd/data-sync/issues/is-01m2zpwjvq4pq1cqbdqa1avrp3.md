---
type: is
id: is-01m2zpwjvq4pq1cqbdqa1avrp3
title: "S216-1: R1 fix made nested tree listings quadratic (reparent every sibling per child)"
kind: bug
status: closed
priority: 0
version: 4
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
  - stack:pr216
dependencies: []
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
created_at: 2026-09-20T15:27:51.669Z
updated_at: 2026-09-21T00:08:11.012Z
closed_at: 2026-09-21T00:08:11.011Z
close_reason: "Pushed 2026-09-20 in the restack of stack #218 onto main (through #209 and #220). Single pre-push gate on macOS: 3061 passed, 2 skipped, 145 golden transcripts. Awaiting CI."
resolution: null
duplicate_of: null
---
Finding S216-1 from the v0.11 stabilization review. Owning layer: PR #216. Full evidence, path:line, and suggested fix are in the notes of mb-gacf under S216-1.

## Notes

Fixed on stab/s216-core (pending restack integration and push to PR 216). Counter-based regression tests red before, green after; 190 focused tests pass. Measurements are in the commit bodies and beside the constants.
