---
type: is
id: is-01m7nnxrj9txmcjawfmkz6frad
title: "App: accept https GitHub URLs in AppDelegate.request and File > Open Location…"
kind: feature
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-17-open-anything-from-cli-and-app.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7nnxsky2r2jf9d5n3ac3vty
parent_id: is-01m7nnxhaqce1g2ewec3wbaf7e
created_at: 2026-11-17T21:17:06.505Z
updated_at: 2026-11-17T21:17:14.514Z
---
Phase 1, apps/macos. Today non-file URLs are dropped silently. Accept https from open -a/-b; Open Location sheet validates with metab --present --dry-run --json; show metab's reason for refused URLs. Join a matching session or start metab URL --no-open --exit-on-eof.
