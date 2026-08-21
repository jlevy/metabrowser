---
type: is
id: is-01m0k3nbmdvy9x8g3r8t9ckzjt
title: Render Mermaid diagrams in rendered Markdown, GitHub-equivalent or better
kind: feature
status: open
priority: 1
version: 8
labels: []
dependencies: []
child_order_hints:
  - is-01m0k3nrtdd1dhyj0bvnf440s2
  - is-01m0k3ns7dh5qtb3p5erjnqsvf
  - is-01m0k3nsp5dq8cehgxvwq0t82z
  - is-01m0k3nt2p2f43sq23950xv6g4
  - is-01m0k3ntgjst99y1trtyebv0q6
  - is-01m0k3ntypp20smgz56xxw8ak5
created_at: 2026-08-21T21:29:35.117Z
updated_at: 2026-08-21T21:29:50.805Z
---
Epic for Mermaid support. Research: docs/project/research/research-2026-08-21-mermaid-diagram-support.md.

KPress 0.3.3 already emits <figure data-kpress-diagram="mermaid" data-kpress-diagram-status="source"> for a mermaid fence, ships js/diagrams.js, and lists it as an asset entry point that plugin_sdk.js already loads. It no-ops because globalThis.mermaid is never defined. Missing inputs: a vendored Mermaid library and a per-mount initKpressDiagrams call.

Recommendation: vendor the Mermaid 11.17.0 ESM build, load it lazily from the Markdown plugin mount path only when the container holds a diagram figure, keep securityLevel strict. Measured in Chromium 141: eager UMD costs 3,572,296 bytes and 449 ms on every document; lazy ESM costs 754 KB and 101 ms only on documents that have a diagram, then ~34 ms per additional diagram of the same type.
