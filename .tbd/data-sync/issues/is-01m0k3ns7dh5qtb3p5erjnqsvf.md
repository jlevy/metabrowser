---
type: is
id: is-01m0k3ns7dh5qtb3p5erjnqsvf
title: Add module bundles to the asset loader and publish the mermaid bundle
kind: task
status: closed
priority: 1
version: 11
spec_path: docs/project/specs/active/plan-2026-08-21-mermaid-diagram-rendering.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m0k3nsp5dq8cehgxvwq0t82z
parent_id: is-01m0k3nbmdvy9x8g3r8t9ckzjt
hold: null
hold_until: null
created_at: 2026-08-21T21:29:49.037Z
updated_at: 2026-11-19T02:37:06.233Z
started_at: 2026-11-19T01:37:39.852Z
closed_at: 2026-11-19T02:37:06.232Z
close_reason: Done on branch claude/mermaid-diagram-rendering-441fe6 (commit 4e0bc6391)
resolution: null
duplicate_of: null
---
static/asset-loader.js gains module entries ({module: url}) and ensureModule(name), which imports once and resolves to the namespace, sharing in-flight imports. server.py publishes a mermaid bundle at the vendored entry's stamped URL so relative chunk imports resolve under the stamp. Expose through the SDK (mb.ensureModule) and types.d.ts. Do not add Mermaid to eager or prefetched tiers.
