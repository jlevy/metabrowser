---
type: is
id: is-01m0k3ntypp20smgz56xxw8ak5
title: Mermaid session, goldens, parity rows, Chrome evidence, docs, changelog
kind: task
status: open
priority: 1
version: 7
spec_path: docs/project/specs/active/plan-2026-08-21-mermaid-diagram-rendering.md
labels: []
dependencies: []
parent_id: is-01m0k3nbmdvy9x8g3r8t9ckzjt
created_at: 2026-08-21T21:29:50.805Z
updated_at: 2026-11-19T01:37:28.769Z
---
tests/dom/markdown-diagrams-session.js + cli-ui-markdown-diagrams.tryscript.md over the production renderer with a stub Mermaid (lazy gate, status transitions, error, theme re-render, disposal, replacement, inert image, toolbar, zoom/pan). Parity rows in arch-parity-registry.md, including a paint-exempt row for Mermaid layout with tests/dom/markdown-diagrams-chrome.mjs as evidence (trusted SVG, untrusted image under CSP, no Mermaid request for diagram-free docs). User docs, views/models/routes map, changelog fragment.
