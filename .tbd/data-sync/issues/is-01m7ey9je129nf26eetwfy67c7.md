---
type: is
id: is-01m7ey9je129nf26eetwfy67c7
title: server.py keeps compatibility shims AGENTS.md forbids
kind: bug
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-14-documentation-from-first-principles.md
labels: []
dependencies: []
parent_id: is-01m7ey9fq9v53mp3c974mg2d89
created_at: 2026-11-15T06:28:41.024Z
updated_at: 2026-11-15T06:28:41.024Z
---
server.py carries __all__ re-exports and a ROOT_DIR proxy kept for compatibility. AGENTS.md forbids speculative compatibility layers; name the consumer or remove them.
