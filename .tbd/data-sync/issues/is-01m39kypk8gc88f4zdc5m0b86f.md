---
type: is
id: is-01m39kypk8gc88f4zdc5m0b86f
title: Heading anchors under the untrusted profile (GitHub-style user-content- ids)
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
created_at: 2026-09-24T11:48:59.623Z
updated_at: 2026-09-24T11:48:59.623Z
---
The inert Markdown render (step 8, PR #234) strips all ids, so untrusted documents have no table of contents and in-page anchor links do not scroll. Add GitHub-compatible heading ids with a user-content- prefix (matching how github.com namespaces them to avoid clobbering), map #fragment links to them, and restore the table of contents for inert renders. Keep the prefix out of any app id namespace; tests for clobbering attempts.
