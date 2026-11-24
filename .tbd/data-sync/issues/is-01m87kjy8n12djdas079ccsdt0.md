---
type: is
id: is-01m87kjy8n12djdas079ccsdt0
title: Claim a .pdf only when its bytes are a PDF; no viewer in a diff
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-24-pdf-plugin-and-open-in-default-app.md
labels: []
dependencies: []
parent_id: is-01m87bky1pb8rhr10p26bsp6w6
created_at: 2026-11-24T20:22:34.516Z
updated_at: 2026-11-24T20:22:34.516Z
---
A file named .pdf whose bytes do not start with %PDF- falls to the text or bytes view instead of a viewer that shows an error. The surfaces session asserts a mounted diff holds no embed, object, or iframe.
