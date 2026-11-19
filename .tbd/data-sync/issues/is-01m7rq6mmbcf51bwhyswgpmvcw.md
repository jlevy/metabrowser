---
type: is
id: is-01m7rq6mmbcf51bwhyswgpmvcw
title: Carry Mermaid through the inert allowlist and render inert diagrams as images
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-mermaid-diagram-rendering.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0k3ntypp20smgz56xxw8ak5
parent_id: is-01m0k3nbmdvy9x8g3r8t9ckzjt
created_at: 2026-11-19T01:37:09.257Z
updated_at: 2026-11-19T01:37:29.252Z
---
inert_html.py and static/inert-html.js reduce a KPress mermaid figure to <pre lang="mermaid"><code>, allowing lang on pre only with the value mermaid. The renderer's inert mode renders those blocks with securityLevel strict and shows the SVG as <img src=data:image/svg+xml>, so it can run no script, load nothing, navigate nowhere. Verify under the untrusted CSP in Chrome (no violations; <style> in the measuring SVG is blocked, so measure in an inline-styled container). Pin the inert markup through /api/kpress/render in a golden.
