---
type: is
id: is-01m2k1jrywxceb6n3r0pbadegx
title: "Hosted review Phase 0C.2: close format inventory, distribution, and parity gates"
kind: task
status: open
priority: 1
version: 8
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - stack:pr125
dependencies:
  - type: blocks
    target: is-01m10vgw6vhq82cd495kvhh9gf
  - type: blocks
    target: is-01m2ktkve5n2fztx8smd6n9vja
  - type: blocks
    target: is-01m2ktnwpapx26rybv4w3pbshk
  - type: blocks
    target: is-01m2kvemzp183vrykz849c0s5a
parent_id: is-01m10vgw6vhq82cd495kvhh9gf
child_order_hints:
  - is-01m2krxqqcrn84sje77js6e1vx
  - is-01m2kry0g3g8hbnhr896wvqeve
created_at: 2026-09-15T17:24:36.954Z
updated_at: 2026-09-16T00:56:48.588Z
---
Coordinate one formal Phase 0C.2 pull request stacked on the exact green Phase 0C.1 head. mb-vors owns the format inventory checker, installed-wheel smoke coverage, parity evidence, and architecture-map updates without premature UI registration; mb-ci0t owns independent review, make verify, bead sync, gh publication, and final green CI. Close this phase only after both children are complete and its PR is registered with mb-n2ro. This bead does not merge the stack; mb-n2ro alone owns explicit-approval landing and retargeting.
