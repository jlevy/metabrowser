---
type: is
id: is-01m0k3nsp5dq8cehgxvwq0t82z
title: Write the Mermaid renderer and mount it from rendered and transcluded Markdown
kind: task
status: closed
priority: 1
version: 15
spec_path: docs/project/specs/active/plan-2026-08-21-mermaid-diagram-rendering.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0k3nt2p2f43sq23950xv6g4
  - type: blocks
    target: is-01m0k3ntgjst99y1trtyebv0q6
  - type: blocks
    target: is-01m0k3ntypp20smgz56xxw8ak5
  - type: blocks
    target: is-01m7rq6mmbcf51bwhyswgpmvcw
  - type: blocks
    target: is-01m7rq6nb765kp3wkacedx6qts
parent_id: is-01m0k3nbmdvy9x8g3r8t9ckzjt
created_at: 2026-08-21T21:29:49.509Z
updated_at: 2026-11-19T02:37:06.612Z
closed_at: 2026-11-19T02:37:06.611Z
close_reason: Done on branch claude/mermaid-diagram-rendering-441fe6 (commit 4e0bc6391)
resolution: null
duplicate_of: null
---
builtin_plugins/markdown/diagrams.js: mountDiagrams(root, mb, {mode}) finds KPress figures (trusted) or pre[lang=mermaid] (inert), loads Mermaid via ensureModule, initializes GitHub's observable config with securityLevel strict, renders in document order yielding between diagrams, keeps Mermaid's error message visible with the source, and returns {dispose, ready}. Never sets globalThis.mermaid; plugin-sdk.js loadKpressAssets skips KPress js/diagrams.js. rendered.js and transclusion.js import it on demand only when the root holds a diagram, and dispose with the view.
