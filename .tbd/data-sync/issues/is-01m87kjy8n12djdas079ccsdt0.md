---
type: is
id: is-01m87kjy8n12djdas079ccsdt0
title: Claim a .pdf only when its bytes are a PDF; no viewer in a diff
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-24-pdf-plugin-and-open-in-default-app.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m87bky1pb8rhr10p26bsp6w6
hold: null
hold_until: null
created_at: 2026-11-24T20:22:34.516Z
updated_at: 2026-11-24T22:14:43.642Z
started_at: 2026-11-24T21:44:48.038Z
closed_at: 2026-11-24T22:14:43.638Z
close_reason: "PR #796"
resolution: null
duplicate_of: null
---
A file named .pdf whose bytes do not start with %PDF- falls to the text or bytes view instead of a viewer that shows an error. The surfaces session asserts a mounted diff holds no embed, object, or iframe.
