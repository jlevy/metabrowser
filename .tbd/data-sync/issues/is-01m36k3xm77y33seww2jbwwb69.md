---
type: is
id: is-01m36k3xm77y33seww2jbwwb69
title: "GitHub URL open: reducer plugin, HTTPS with gh helper, ref/path split, line anchors"
kind: task
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m36k3y0t6fvtqhskx3cqxx95
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
created_at: 2026-09-23T07:36:38.789Z
updated_at: 2026-09-23T07:57:32.058Z
---
Delivery step 5 of the thin-mirror plan. GitHub reducer in builtin_plugins/github through classify_root_argument(reducers=), with the URL grammar, canonical identity and refusals from the plan and network-free goldens for every shape. HTTPS fetch with the scoped gh credential helper when gh is present; error classification; measured stall bound (mb-rati); ref and path split without rev-parse (branch, tag, commit ID precedence); line anchors; SIGHUP handling (mb-163x); size check before a first clone. Opt-in live smoke on a public repository. Independent review, make verify, green CI.
