---
type: is
id: is-01m2zpwvxd9vp6vpn587bsz6p7
title: "S216-9: decide and reconcile the plugin content-reader API with the spec, plugins doc, and architecture map"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
  - stack:pr216
dependencies: []
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
created_at: 2026-09-20T15:28:00.933Z
updated_at: 2026-09-20T15:37:50.343Z
---
Finding S216-9 from the v0.11 stabilization review. Owning layer: PR #216. Full evidence, path:line, and suggested fix are in the notes of mb-gacf under S216-9.

## Notes

Decision 2026-09-20 (user): BUILD the bounded, source-agnostic content reader through plugin_api and move the built-in binary/structured/agent-log/diff sidekicks onto it; then make the spec box, docs/plugins.md, the architecture doc, and the parity map agree. Starts after the S216 core and CLI fix branches are integrated, because it edits the same sidekick files.
