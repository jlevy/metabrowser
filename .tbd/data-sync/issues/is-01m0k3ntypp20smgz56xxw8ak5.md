---
type: is
id: is-01m0k3ntypp20smgz56xxw8ak5
title: Cover Mermaid lazy mount, replacement, disposal, and theme change in tests/dom
kind: task
status: open
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-21-mermaid-diagram-rendering.md
labels: []
dependencies: []
parent_id: is-01m0k3nbmdvy9x8g3r8t9ckzjt
created_at: 2026-08-21T21:29:50.805Z
updated_at: 2026-11-14T18:47:33.045Z
---
tests/dom coverage from the Mermaid plan's testing strategy: a document with a Mermaid fence mounts and reaches data-kpress-diagram-status="rendered"; a document without one never requests the Mermaid entry; navigating away disposes; navigating between two diagram documents replaces rather than accumulates; a theme change re-renders; a malformed diagram reaches the error state with its source visible.
