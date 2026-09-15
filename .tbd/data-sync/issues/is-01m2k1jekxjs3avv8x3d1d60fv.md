---
type: is
id: is-01m2k1jekxjs3avv8x3d1d60fv
title: "Hosted review Phase 0A.6: prove packaging, dormancy, and architecture status"
kind: task
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - stack:pr125
dependencies:
  - type: blocks
    target: is-01m2k1jg4afz39zgz5ktt49m2b
parent_id: is-01m10vgw6vhq82cd495kvhh9gf
created_at: 2026-09-15T17:24:26.361Z
updated_at: 2026-09-15T18:47:04.323Z
---
Update devtools/check_distribution.py and its focused tests so the wheel and sdist contain the hosted-review Python package, browser model, and portable corpus while installed plugin discovery remains exactly the existing set. Update arch-hosted-review-model.md and arch-views-models-routes.md to say the format kernel is implemented but has no registered kind, view, route, or functional UI surface. Run common documentation formatting and leave proposed UI/parity rows planned.

## Notes

Wired wheel and sdist suffix checks, imported and validated the packaged corpus from the isolated installed wheel, and retained the exact nine-plugin discovery assertion to prove dormancy. Updated architecture status and the format map; no manifest, route, kind, view, or parity surface was registered.
