---
type: is
id: is-01m2k1jrywxceb6n3r0pbadegx
title: "Hosted review Phase 0C.2: close format inventory, distribution, and parity gates"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - stack:pr125
dependencies:
  - type: blocks
    target: is-01m10vgw6vhq82cd495kvhh9gf
parent_id: is-01m10vgw6vhq82cd495kvhh9gf
created_at: 2026-09-15T17:24:36.954Z
updated_at: 2026-09-15T17:24:49.462Z
---
Add the format inventory checker and installed-wheel smoke coverage for every hosted-review contract, schema, digest, producer, consumer, and fixture. Update architecture maps without registering premature UI surfaces, run make verify and a fresh technical review, land the no-network format/plugin boundary, and close mb-63ym only after Phase 0A through 0C evidence is green.
