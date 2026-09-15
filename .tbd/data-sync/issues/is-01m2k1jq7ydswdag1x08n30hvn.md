---
type: is
id: is-01m2k1jq7ydswdag1x08n30hvn
title: "Hosted review Phase 0C.1: compile enforced SoftSchema contracts in both runtimes"
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
    target: is-01m2k1jrywxceb6n3r0pbadegx
parent_id: is-01m10vgw6vhq82cd495kvhh9gf
created_at: 2026-09-15T17:24:35.192Z
updated_at: 2026-09-15T17:24:36.954Z
---
After mb-4gnu lands the reviewed first-party SoftSchema foundation, add contracts.py, the packaged hosted-review format inventory and deterministic compiled schemas, validate_artifact, validate_record, and compile_contracts check mode. Bind every contract ID to its envelope, frontmatter-md or pure-yaml profile, enforced maturity, model, schema digest, producer, consumer, and fixture. Extend hosted-review-model.js and the same corpus tests so every browser-consumed record passes identical Python and JavaScript validity outcomes. Do not select schemas from artifact paths.
