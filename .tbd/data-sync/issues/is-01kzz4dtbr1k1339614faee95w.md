---
type: is
id: is-01kzz4dtbr1k1339614faee95w
title: "Route D: Publish the navigation SDK and migrate bundled callers"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-13-markdown-link-navigation.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzz4dtn4pw3my7gf9wsr9ebh
parent_id: is-01kzz03fmd769zawq6gf5d1hd7
created_at: 2026-08-14T03:18:07.992Z
updated_at: 2026-08-14T03:18:08.291Z
---
Expose window.metabrowser.navigation.href(target), open(target, {viewId?}), and current() with one JSDoc and types.d.ts definition. Keep viewId as a presentation option outside canonical resource identity. Migrate folder views and every bundled caller atomically, remove openPath and metabrowser:open-path without a compatibility shim, and add SDK runtime and declaration-parity tests.
