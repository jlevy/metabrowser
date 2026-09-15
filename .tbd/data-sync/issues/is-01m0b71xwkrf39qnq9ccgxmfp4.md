---
type: is
id: is-01m0b71xwkrf39qnq9ccgxmfp4
title: "Hosted review Phase 4: anchored review threads over comparisons"
kind: feature
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
dependencies: []
parent_id: is-01m10vgwqwn8gjdv8fm183vztr
created_at: 2026-08-18T19:54:57.298Z
updated_at: 2026-09-14T23:59:09.172Z
---
Implement the provider-neutral ReviewThread and ReviewComment view layer over immutable comparison anchors: change-request and file-change IDs, side, content identity, byte/line range, original/current revision IDs, and context fingerprint. GitHub review threads are the first producer. Map only when Git identity and line context are sufficient; otherwise render the provider's original anchor as outdated or unresolved. Threads arrive as Hosted Review Format data and never extend File Diff Format or become renderer-specific provider objects.
