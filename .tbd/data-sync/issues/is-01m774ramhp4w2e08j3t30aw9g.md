---
type: is
id: is-01m774ramhp4w2e08j3t30aw9g
title: Detached LRU of file surfaces with a suspend and resume view contract
kind: task
status: open
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7exbshjz1sx7r322nye458d
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-12T05:47:40.559Z
updated_at: 2026-11-15T06:12:34.230Z
---
Retain recently viewed file surfaces detached, keyed by path, envelope ETag, and active view, budgeted by DOM nodes, with optional suspend() and resume() view hooks. The hooks are additive, so PLUGIN_SDK_VERSION does not change unless an implementation breaks the contract (the plan's API Changes); CHANGELOG.md notes them for plugin authors. Measured as revisit painted-ready and requests, plus memory (H98).
