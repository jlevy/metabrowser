---
type: is
id: is-01m39kypk8gc88f4zdc5m0b86f
title: Heading anchors under the untrusted profile (GitHub-style user-content- ids)
kind: task
status: closed
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
hold: null
hold_until: null
created_at: 2026-09-24T11:48:59.623Z
updated_at: 2026-09-24T20:31:04.435Z
started_at: 2026-09-24T19:15:06.761Z
closed_at: 2026-09-24T20:31:04.434Z
close_reason: "PR #240: user-content- heading anchors, fragment mapping, inert TOC; security review fixed; CI green"
resolution: null
duplicate_of: null
---
The inert Markdown render (step 8, PR #234) strips all ids, so untrusted documents have no table of contents and in-page anchor links do not scroll. Add GitHub-compatible heading ids with a user-content- prefix (matching how github.com namespaces them to avoid clobbering), map #fragment links to them, and restore the table of contents for inert renders. Keep the prefix out of any app id namespace; tests for clobbering attempts.
