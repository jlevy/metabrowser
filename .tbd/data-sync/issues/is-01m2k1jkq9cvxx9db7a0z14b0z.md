---
type: is
id: is-01m2k1jkq9cvxx9db7a0z14b0z
title: "Hosted review Phase 0B.2: complete review, signal, and activity records"
kind: task
status: open
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - stack:pr125
dependencies:
  - type: blocks
    target: is-01m2k1jnf5t6bgg340skd537hn
  - type: blocks
    target: is-01m2k1jq7ydswdag1x08n30hvn
parent_id: is-01m10vgw6vhq82cd495kvhh9gf
child_order_hints:
  - is-01m2krvmvxvt6vhgq260mw7v8x
  - is-01m2krvwqaynstjykh0m9k90vr
created_at: 2026-09-15T17:24:31.585Z
updated_at: 2026-09-16T00:12:56.358Z
---
Coordinate one formal Phase 0B.2 pull request stacked on the exact green Phase 0B.1 head. mb-n9fo owns the complete review, signal, and activity record implementation and portable evidence; mb-qpbu owns independent review, make verify, bead sync, gh publication, and final green CI. Close this phase only after both children are complete and its PR is registered with the stack landing coordinator mb-n2ro.
