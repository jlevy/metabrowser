---
type: is
id: is-01m2zvd5k0t82m1ajtmknrdpa9
title: "Phase 1B-a: measured initial-acquisition stall bound"
kind: task
status: open
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m3617625k6h6qq4dq2hyxytb
parent_id: is-01kzsb4jnyd56wy89xmztkmz2m
created_at: 2026-09-20T16:46:49.439Z
updated_at: 2026-09-23T03:55:22.956Z
---
Phase 1B-a of docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md (heading at line 1774) still has this item unchecked: measure initial acquisition of a large or bitmap-less repository against a stalled or slow server and choose its low-speed bound. Until that bound is measured, user-driven job cancellation is the only guard.

## Notes

2026-09-22 (codex/v012-foundation-stabilization): decided by the user to move this to Phase 2A. A file:// origin cannot stall, so the bound is measured against a real HTTPS server with mb-s1lt. The spec now has a Phase 2A checklist item for it; the Phase 1B-a item is ticked as moved (064c51dd). Interim guards: the 900 s acquisition timeout and user cancellation, both of which now kill the whole Git process group (mb-lp89, d83beb9b). mb-s1lt now depends on this bead.
