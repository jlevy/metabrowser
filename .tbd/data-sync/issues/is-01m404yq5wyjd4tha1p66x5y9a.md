---
type: is
id: is-01m404yq5wyjd4tha1p66x5y9a
title: Define and document independent cache and config roots
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/project/architecture/arch-repository-sources-and-provider-mirrors.md
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m404jrt4sm3rndr1kznbpr6v
hold: null
hold_until: null
created_at: 2026-10-03T05:49:23.515Z
updated_at: 2026-10-04T22:11:18.195Z
started_at: 2026-10-03T06:04:43.894Z
closed_at: 2026-10-04T22:11:18.181Z
close_reason: Design and implementation completed in cbb92dc9, draft PR https://github.com/jlevy/metabrowser/pull/268. Local 4005 tests and 278 golden checks passed; all GitHub Python/Git/distribution checks passed. Remaining dependency audit and manual release acceptance are tracked separately under mb-19fc, mb-i6ze, and the release stability epic.
resolution: null
duplicate_of: null
---

## Notes

Approved: breaking v0.12 XDG cache/config split matching uv/fdu on Linux/macOS. No METABROWSER_HOME alias, old-path fallback, or automatic migration. Updated architecture, original active design, CLI docs, QA isolation, and changelog. Configuration is initialized independently and preserved byte-for-byte through cache recreation; validation in progress.
