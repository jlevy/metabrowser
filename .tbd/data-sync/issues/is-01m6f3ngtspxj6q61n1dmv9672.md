---
type: is
id: is-01m6f3ngtspxj6q61n1dmv9672
title: PR prose ignores the reading width and has mismatched code sizes
kind: bug
status: in_progress
priority: 1
version: 2
delegate: claude-code@spud10
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m6f3nf55rm1sjpaagqaph6nr
hold: null
hold_until: null
created_at: 2026-11-02T21:46:53.656Z
updated_at: 2026-11-02T21:47:08.422Z
started_at: 2026-11-02T21:47:08.421Z
---
Reported by the owner. Reading Width requires --doc-measure, and code sizes belong to the document's ramp. PR text should read as the same Markdown does in a file; try reusing the md-body path. Proved by a table against the same Markdown in a file.
