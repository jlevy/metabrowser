---
type: is
id: is-01m3abtp09dg24eyarfw89fe1a
title: Markdown and wiki link resolvers should escape a backslash as %5C
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
created_at: 2026-09-24T18:46:13.769Z
updated_at: 2026-09-24T20:31:05.241Z
started_at: 2026-09-24T19:15:08.715Z
closed_at: 2026-09-24T20:31:05.240Z
close_reason: "PR #240: resolvers escape backslash as %5C consistent with #237; end-to-end test; CI green"
resolution: null
duplicate_of: null
---
After mb-yhso (PR codex/v012-small-fixes) inventory names escape a backslash as %5C on POSIX, but the Markdown and wiki link resolvers (links.js, project-adapters.js, wiki-resolver.js) only escape %, so a link whose target contains a backslash does not find the file. Escape it the same way and add tests.
