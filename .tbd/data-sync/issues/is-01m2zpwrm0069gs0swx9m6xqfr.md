---
type: is
id: is-01m2zpwrm0069gs0swx9m6xqfr
title: "S216-6: charts.py splitlines splits on U+2028 and drops the streaming memory bound"
kind: bug
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
  - stack:pr216
dependencies: []
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
created_at: 2026-09-20T15:27:57.560Z
updated_at: 2026-09-21T00:08:13.214Z
closed_at: 2026-09-21T00:08:13.212Z
close_reason: "Pushed 2026-09-20 in the restack of stack #218 onto main (through #209 and #220). Single pre-push gate on macOS: 3061 passed, 2 skipped, 145 golden transcripts. Awaiting CI."
resolution: null
duplicate_of: null
---
Finding S216-6 from the v0.11 stabilization review. Owning layer: PR #216. Full evidence, path:line, and suggested fix are in the notes of mb-gacf under S216-6.

## Notes

Fixed on stab/s216-cli and/or stab/s216-core (pending restack integration and push to PR 216). Regression tests red before, green after.
