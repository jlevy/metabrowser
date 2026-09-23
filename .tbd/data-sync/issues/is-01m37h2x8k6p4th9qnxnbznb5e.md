---
type: is
id: is-01m37h2x8k6p4th9qnxnbznb5e
title: "Show GitHub line anchors (#L10, #L10-L20, #L10C5-L20C8) in source views"
kind: feature
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
created_at: 2026-09-23T16:20:22.920Z
updated_at: 2026-09-23T16:20:22.920Z
---
Step 5 (codex/v012-github-url-open) parses GitHub line anchors into the selection and prints them in the CLI, but no source view scrolls to or highlights a #L fragment today (checked static/ and plugins). Add line-range highlighting and scroll-to-line in the source view for a pinned file, reachable from a GitHub blob URL, with a browserless session and golden per AGENTS.md parity.
