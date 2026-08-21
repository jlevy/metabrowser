---
type: is
id: is-01m0k3ns7dh5qtb3p5erjnqsvf
title: Load Mermaid lazily and add kpressInitDiagrams to the plugin SDK
kind: task
status: open
priority: 1
version: 7
spec_path: docs/project/specs/active/plan-2026-08-21-mermaid-diagram-rendering.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0k3nsp5dq8cehgxvwq0t82z
parent_id: is-01m0k3nbmdvy9x8g3r8t9ckzjt
created_at: 2026-08-21T21:29:49.037Z
updated_at: 2026-08-21T22:08:25.833Z
---
Mirror _loadKpressTocModule in plugin_sdk.js: dynamically import the vendored Mermaid entry, assign window.mermaid so kpress's hostMermaid() succeeds, then import /kpress-static/<ver>/js/diagrams.js and capture its initKpressDiagrams export. Expose mb.kpressInitDiagrams(container) alongside kpressInitToc and declare it in static/types.d.ts.

Trigger the import from the presence of [data-kpress-diagram="mermaid"] in the mounted container. Do NOT add Mermaid to optional_script_assets in server.py: that chain loads eagerly on every page and measured 3,572,296 bytes and 449 ms.

Keep kpress's securityLevel strict. Additive SDK change; do not bump PLUGIN_SDK_VERSION, whose gate is exact-match and would force an edit to every built-in manifest for nothing.
