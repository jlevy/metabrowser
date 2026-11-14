---
type: is
id: is-01m0k3nsp5dq8cehgxvwq0t82z
title: Call kpressInitDiagrams from the Markdown rendered view with disposal
kind: task
status: open
priority: 1
version: 11
spec_path: docs/project/specs/active/plan-2026-08-21-mermaid-diagram-rendering.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0k3nt2p2f43sq23950xv6g4
  - type: blocks
    target: is-01m0k3ntgjst99y1trtyebv0q6
  - type: blocks
    target: is-01m0k3ntypp20smgz56xxw8ak5
parent_id: is-01m0k3nbmdvy9x8g3r8t9ckzjt
created_at: 2026-08-21T21:29:49.509Z
updated_at: 2026-11-14T18:44:50.290Z
---
In builtin_plugins/markdown/rendered.js, call mb.kpressInitDiagrams(container) beside the existing kpressInitToc call, only when the container holds a [data-kpress-diagram="mermaid"] figure, and store its disposer beside disposeToc so replacement and navigation away dispose it. Phase 1 of docs/project/specs/active/plan-2026-08-21-mermaid-diagram-rendering.md.
