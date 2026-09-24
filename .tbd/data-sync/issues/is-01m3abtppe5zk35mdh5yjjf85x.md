---
type: is
id: is-01m3abtppe5zk35mdh5yjjf85x
title: copyContent in static/app.js appears to be dead code
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
created_at: 2026-09-24T18:46:14.476Z
updated_at: 2026-09-24T18:46:14.476Z
---
Found in PR codex/v012-small-fixes: nothing in src calls copyContent in static/app.js; only test_browser_assets.py asserts it exists. Confirm and remove it with its assertion.
