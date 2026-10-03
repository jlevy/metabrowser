---
type: is
id: is-01m404yq5wyjd4tha1p66x5y9a
title: Define and document independent cache and config roots
kind: task
status: in_progress
priority: 2
version: 3
spec_path: docs/project/architecture/arch-repository-sources-and-provider-mirrors.md
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m404jrt4sm3rndr1kznbpr6v
hold: null
hold_until: null
created_at: 2026-10-03T05:49:23.515Z
updated_at: 2026-10-03T06:04:44.212Z
started_at: 2026-10-03T06:04:43.894Z
---

## Notes

Approved: breaking v0.12 XDG cache/config split matching uv/fdu on Linux/macOS. No METABROWSER_HOME alias, old-path fallback, or automatic migration. Updated architecture, original active design, CLI docs, QA isolation, and changelog. Configuration is initialized independently and preserved byte-for-byte through cache recreation; validation in progress.
