---
type: is
id: is-01m0k4p1mdy4m20chsyds7c7yw
title: Publish a tiered asset descriptor from server.py instead of the inline chain
kind: task
status: closed
priority: 1
version: 7
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0k4p20yey7mb3h4t9z4w94j
  - type: blocks
    target: is-01m0k4p2d6xf80tn8qxhx6qavc
  - type: blocks
    target: is-01m0k3ns7dh5qtb3p5erjnqsvf
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-21T21:47:26.220Z
updated_at: 2026-08-21T22:26:44.996Z
closed_at: 2026-08-21T22:26:44.996Z
close_reason: server.py now splits optional_script_assets (prefetched) from on_demand_script_bundles, published as window.METABROWSER_ASSET_BUNDLES. The optional-asset events still fire so late arrival re-enhances.
---
