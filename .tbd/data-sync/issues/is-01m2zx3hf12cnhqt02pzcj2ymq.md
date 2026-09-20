---
type: is
id: is-01m2zx3hf12cnhqt02pzcj2ymq
title: "HTML preview: offer the page as a full browser tab, outside the frame"
kind: feature
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-08-06-html-rendering-and-trust-model.md
labels:
  - release:v0.11.0
dependencies: []
parent_id: is-01kzcvm6cpe5b8sb9b9n3gb16g
created_at: 2026-09-20T17:16:31.071Z
updated_at: 2026-09-20T17:16:31.071Z
---
User request 2026-09-20. The HTML Preview view should offer an 'open as a full page' affordance that opens /raw/<path> in a new tab. The raw response already carries the sandbox CSP, so a top-level raw document has an opaque origin and the same containment as the framed preview; the spec acceptance criterion says so. Needs: the control in builtin_plugins/html, rel=noopener noreferrer, hidden when active_content is off exactly as Preview is, a browserless session test and golden, docs, CHANGELOG.
