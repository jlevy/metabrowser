---
type: is
id: is-01m37h2x8k6p4th9qnxnbznb5e
title: "Show GitHub line anchors (#L10, #L10-L20, #L10C5-L20C8) in source views"
kind: feature
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
hold: null
hold_until: null
created_at: 2026-09-23T16:20:22.920Z
updated_at: 2026-09-24T19:05:51.921Z
started_at: 2026-09-24T18:04:54.493Z
closed_at: 2026-09-24T19:05:51.919Z
close_reason: "Line anchors: PR #235 (codex/v012-line-anchors, head e0384e2a, above #234). Line numbers and GitHub-style #L anchors in source views, placed by measured pitch. Independent review; all findings fixed. CI green on all nine checks. Leftovers are in mb-gkrr."
resolution: null
duplicate_of: null
---
Step 5 (codex/v012-github-url-open) parses GitHub line anchors into the selection and prints them in the CLI, but no source view scrolls to or highlights a #L fragment today (checked static/ and plugins). Add line-range highlighting and scroll-to-line in the source view for a pinned file, reachable from a GitHub blob URL, with a browserless session and golden per AGENTS.md parity.
